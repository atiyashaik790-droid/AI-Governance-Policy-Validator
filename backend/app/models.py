"""Portable relational records. Content is intentionally excluded from audit storage."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, ForeignKey, UniqueConstraint, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# Generate an opaque primary key.
def new_id() -> str:
    return str(uuid.uuid4())


# Return a timezone-independent ISO timestamp.
def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(120))
    draft: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    row_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": row_version}


class Version(Base):
    __tablename__ = "policy_versions"
    __table_args__ = (UniqueConstraint("policy_id", "number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    policy_id: Mapped[str] = mapped_column(ForeignKey("policies.id"), index=True)
    tenant: Mapped[str] = mapped_column(String(80), index=True)
    number: Mapped[int] = mapped_column(Integer)
    document: Mapped[str] = mapped_column(Text)
    created: Mapped[str] = mapped_column(String(40), default=now)


class Assignment(Base):
    __tablename__ = "active_policy_assignments"
    tenant: Mapped[str] = mapped_column(String(80), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("policy_versions.id"))


class Audit(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant: Mapped[str] = mapped_column(String(80), index=True)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    resource: Mapped[str] = mapped_column(String(80))
    created: Mapped[str] = mapped_column(String(40), default=now)


class Execution(Base):
    __tablename__ = "validation_executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant: Mapped[str] = mapped_column(String(80), index=True)
    actor: Mapped[str] = mapped_column(String(80))
    policy_id: Mapped[str] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer)
    model: Mapped[str] = mapped_column(String(120))
    decision: Mapped[str] = mapped_column(String(20), index=True)
    metadata_json: Mapped[str] = mapped_column(Text)
    created: Mapped[str] = mapped_column(String(40), default=now)


class Review(Base):
    __tablename__ = "human_review_cases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant: Mapped[str] = mapped_column(String(80), index=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("validation_executions.id"))
    status: Mapped[str] = mapped_column(String(40), default="PENDING")
    created: Mapped[str] = mapped_column(String(40), default=now)

    row_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": row_version}


class Feedback(Base):
    __tablename__ = "feedback_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant: Mapped[str] = mapped_column(String(80), index=True)
    execution_id: Mapped[str] = mapped_column(ForeignKey("validation_executions.id"))
    rating: Mapped[int] = mapped_column(Integer)


class Export(Base):
    __tablename__ = "evaluation_exports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    path: Mapped[str] = mapped_column(String(300), default="")
    created: Mapped[str] = mapped_column(String(40), default=now)


# Prevent application code from changing append-only history.
def prevent_history_mutation(mapper, connection, target) -> None:
    raise ValueError("Historical records are append-only")


for historical_model in (Version, Audit):
    event.listen(historical_model, "before_update", prevent_history_mutation)
    event.listen(historical_model, "before_delete", prevent_history_mutation)
