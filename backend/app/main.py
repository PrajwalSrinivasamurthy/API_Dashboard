import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError
from sqlalchemy.exc import DBAPIError, IntegrityError, OperationalError, ProgrammingError

_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_BACKEND_DIR.parent / ".env", override=True)

logger = logging.getLogger(__name__)

from app.logging_config import configure_logging

configure_logging()

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import configure_database, engine
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
    configure_database()
    yield
    if engine is not None:
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


@app.exception_handler(ValidationError)
async def pydantic_validation_exc(_request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


def _db_error_detail(exc: Exception) -> str:
    msg = str(exc).lower()
    if "login failed" in msg or "18456" in msg:
        return (
            "SQL Server login failed for SQL authentication (DATABASE_URL with user:password). "
            "Your other app uses Windows auth — set MSSQL_CONN with Trusted_Connection=yes in .env "
            "and remove or comment out DATABASE_URL, then restart uvicorn. "
            "Or fix the SQL password / VPN."
        )
    if "hyt00" in msg or "timeout" in msg:
        return "Cannot reach SQL Server (timeout). Connect VPN or check host/firewall in DATABASE_URL."
    if "dashboard_users" in msg:
        return (
            "Table dashboard_users is missing. Run backend/sql/schema.sql on the database."
        )
    if "invalid object name" in msg:
        return "A required database table is missing. Run backend/sql/schema.sql."
    return "Database error. Check DATABASE_URL, connectivity, and that schema.sql was applied."


@app.exception_handler(ProgrammingError)
async def db_programming_exc(_request: Request, exc: ProgrammingError):
    logger.exception("Database programming error on %s", _request.url.path)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": _db_error_detail(exc)},
    )


@app.exception_handler(OperationalError)
async def db_operational_exc(_request: Request, exc: OperationalError):
    logger.exception("Database connection error on %s", _request.url.path)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Cannot reach the database. Check DATABASE_URL and network/VPN."},
    )


@app.exception_handler(IntegrityError)
async def db_integrity_exc(_request: Request, exc: IntegrityError):
    logger.warning("Database integrity error on %s: %s", _request.url.path, exc.orig)
    detail = "Database constraint violation"
    if "dashboard_users" in str(exc).lower() and "email" in str(exc).lower():
        detail = "Email already whitelisted"
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": detail},
    )


@app.exception_handler(DBAPIError)
async def db_api_exc(_request: Request, exc: DBAPIError):
    if exc.connection_invalidated:
        logger.exception("Database connection invalidated on %s", _request.url.path)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Database connection lost. Retry the request."},
        )
    logger.exception("Database error on %s", _request.url.path)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": _db_error_detail(exc)},
    )


@app.exception_handler(Exception)
async def unhandled_exc(_request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", _request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
