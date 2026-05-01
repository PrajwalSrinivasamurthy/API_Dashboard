"""Pydantic API schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class CreateProjectKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class CreateProjectKeyResponse(BaseModel):
    id: int
    key: str
    name: str
    active: bool
    message: str = "Store this key securely; it will not be shown again."


class DisableKeyRequest(BaseModel):
    key: Optional[str] = None
    id: Optional[int] = None


class ProjectKeyAdminItem(BaseModel):
    id: int
    name: str
    active: bool
    used_tokens: int
    created_at: datetime


class UsagePerProject(BaseModel):
    project_key_id: int
    project_name: str
    total_tokens: int
    total_cost: Decimal
    last_used: Optional[datetime]


class AdminUsageResponse(BaseModel):
    per_project: List[UsagePerProject]
    total_cost: Decimal
    total_tokens: int


class ErrorEnvelope(BaseModel):
    error: Dict[str, Any]


class DashboardLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=72)


class DashboardTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DashboardChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=72)
    new_password: str = Field(..., min_length=8, max_length=72)


class CreateDashboardUserRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(default="password", min_length=1, max_length=72)


class DashboardUserListItem(BaseModel):
    """Whitelisted dashboard user (no password fields — only bcrypt hashes are stored)."""

    id: int
    email: str
    created_at: datetime
    updated_at: datetime


class DeleteDashboardUserRequest(BaseModel):
    id: Optional[int] = None
    email: Optional[str] = None

    @model_validator(mode="after")
    def require_id_or_email(self):
        if self.id is None and (self.email is None or not str(self.email).strip()):
            raise ValueError("Provide id or email")
        return self


class AdminUpdateDashboardUserPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=72)
    id: Optional[int] = None
    email: Optional[str] = None

    @model_validator(mode="after")
    def require_id_or_email(self):
        if self.id is None and (self.email is None or not str(self.email).strip()):
            raise ValueError("Provide id or email")
        return self
