"""Isolated 007 metadata: never add protected tables to frozen 005/006 contracts."""
from sqlalchemy import (MetaData, Table, Column, String, Integer, LargeBinary, BigInteger,
                        ForeignKeyConstraint, CheckConstraint, Index)
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import DeclarativeBase
from .models_multi_policy import MultiPolicyBase


class ReviewContentBase(DeclarativeBase):
    metadata = MetaData()


for table in MultiPolicyBase.metadata.tables.values():
    copied = table.to_metadata(ReviewContentBase.metadata)
    # SQLAlchemy's metadata copy does not retain conditional CHECK dialects.
    for constraint in table.constraints:
        for target in copied.constraints:
            if constraint.name == target.name and str(getattr(constraint, "sqltext", "")) == str(getattr(target, "sqltext", "")):
                target._ddl_if = constraint._ddl_if
parent = ReviewContentBase.metadata.tables["human_review_cases"]
Index("ux_review_cases_tenant_id", parent.c.tenant, parent.c.id, unique=True)


class ProtectedReviewContent(ReviewContentBase):
    __table__ = Table(
        "review_protected_content", ReviewContentBase.metadata,
        Column("tenant", String(80), primary_key=True),
        Column("review_id", String(36), primary_key=True),
        Column("content_kind", String(20), nullable=False),
        Column("format_version", Integer, nullable=False),
        Column("key_id", String(64), nullable=False),
        Column("nonce", LargeBinary(12).with_variant(mssql.VARBINARY(12), "mssql"), nullable=False),
        Column("ciphertext", LargeBinary().with_variant(mssql.VARBINARY(None), "mssql"), nullable=False),
        Column("created_at", BigInteger, nullable=False),
        Column("expires_at", BigInteger, nullable=False),
        ForeignKeyConstraint(["tenant", "review_id"], ["human_review_cases.tenant", "human_review_cases.id"], name="fk_rpc_review_tenant"),
        CheckConstraint("content_kind = 'original_prompt' AND format_version = 1", name="ck_rpc_format"),
        CheckConstraint("expires_at > created_at AND expires_at <= created_at + 604800", name="ck_rpc_retention"),
        CheckConstraint("length(nonce) = 12 AND length(ciphertext) >= 16 AND length(ciphertext) <= 48016", name="ck_rpc_bytes").ddl_if(dialect="sqlite"),
        CheckConstraint("DATALENGTH(nonce) = 12 AND DATALENGTH(ciphertext) >= 16 AND DATALENGTH(ciphertext) <= 48016", name="ck_rpc_bytes").ddl_if(dialect="mssql"),
        Index("ux_rpc_key_nonce", "key_id", "nonce", unique=True),
        Index("ix_rpc_expiry", "expires_at", "tenant", "review_id"),
    )
