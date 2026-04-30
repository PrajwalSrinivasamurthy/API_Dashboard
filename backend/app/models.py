"""ORM models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProjectKey(Base):
    __tablename__ = "project_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    allowed_client_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    budget_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=Decimal("25.00")
    )
    budget_warn_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    used_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    usage_logs: Mapped[List["UsageLog"]] = relationship(
        "UsageLog", back_populates="project_key", cascade="all, delete-orphan"
    )
    reveal_tokens: Mapped[List["ProjectKeyReveal"]] = relationship(
        "ProjectKeyReveal", back_populates="project_key", cascade="all, delete-orphan"
    )
    security_events: Mapped[List["ProjectKeySecurityEvent"]] = relationship(
        "ProjectKeySecurityEvent", back_populates="project_key", cascade="all, delete-orphan"
    )


class ProjectKeySecurityEvent(Base):
    """Security / limit events for audit and Teams notifications."""

    __tablename__ = "project_key_security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_key_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project_keys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    client_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    project_key: Mapped["ProjectKey"] = relationship("ProjectKey", back_populates="security_events")


class HmacNonce(Base):
    __tablename__ = "hmac_nonces"
    __table_args__ = (UniqueConstraint("project_key_id", "nonce", name="UQ_hmac_nonces_key_nonce"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_key_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project_keys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class ProjectKeyReveal(Base):
    """One-time opaque token to reveal a project key via a shareable URL."""

    __tablename__ = "project_key_reveals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    project_key_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project_keys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project_key: Mapped["ProjectKey"] = relationship("ProjectKey", back_populates="reveal_tokens")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_key_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("project_keys.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False, default=Decimal("0"))
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    project_key: Mapped["ProjectKey"] = relationship("ProjectKey", back_populates="usage_logs")


class DashboardUser(Base):
    __tablename__ = "dashboard_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
