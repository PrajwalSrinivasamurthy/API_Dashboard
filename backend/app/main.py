from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")

from app.logging_config import configure_logging

configure_logging()

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import engine
from app.middleware.audit_http import AuditHttpMiddleware
from app.middleware.project_key import ProjectKeyValidationMiddleware
from app.middleware.request_timing import RequestTimingMiddleware
from app.routers import admin, auth, proxy, reveal


def _cors():
    raw = get_settings().cors_origins.strip()
    if raw == "*":
        return (["*"], False)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return (parts if parts else ["*"], True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="API-Dashboard",
    description="OpenAI chat proxy with project keys and usage tracking.",
    version="1.0.0",
    lifespan=lifespan,
)

_origins, _creds = _cors()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ProjectKeyValidationMiddleware)
app.add_middleware(AuditHttpMiddleware)
app.add_middleware(RequestTimingMiddleware)

app.include_router(proxy.router, prefix="/v1")
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(reveal.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


def _validation_body_for_json(body):
    if body is None:
        return None
    if isinstance(body, (bytes, bytearray)):
        return body.decode("utf-8", errors="replace")
    return body


@app.exception_handler(RequestValidationError)
async def validation_exc(_request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": _validation_body_for_json(exc.body),
        },
    )
