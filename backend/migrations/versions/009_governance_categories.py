"""Persist tenant categories and their policy associations."""

import json
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"

BUILTINS = (
    ("pii", "PII", "Personal information detection"),
    ("moderation", "Moderation", "Supported moderation classifications"),
    ("secret_detection", "Secret Detection", "API keys, tokens and private keys"),
    ("blocked_keywords", "Blocked Keywords", "Configured words and phrases"),
    ("financial_data", "Financial Data", "Financial information controls"),
    ("confidential_information", "Confidential Information", "Company confidentiality controls"),
    ("human_review", "Human Review", "Requests requiring authorized review"),
    ("output_protection", "Output Protection", "Controls on generated responses"),
)


def upgrade():
    category = op.create_table(
        "governance_categories",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False),
        sa.Column("builtin", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False),
        sa.Column("detector", sa.String(20), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("values_json", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant", "name", name="uq_governance_category_tenant_name"),
        sa.CheckConstraint("builtin IN (0,1) AND enabled IN (0,1) AND revision >= 1", name="ck_governance_category_state"),
    )
    op.create_index("ix_governance_categories_tenant", "governance_categories", ["tenant"])
    op.create_table(
        "policy_categories",
        sa.Column("tenant", sa.String(80), primary_key=True),
        sa.Column("policy_id", sa.String(36), primary_key=True),
        sa.Column("category_id", sa.String(64), sa.ForeignKey("governance_categories.id"), primary_key=True),
        sa.ForeignKeyConstraint(["tenant", "policy_id"], ["policies.tenant", "policies.id"], name="fk_policy_category_policy"),
    )
    op.create_index("ix_policy_categories_category", "policy_categories", ["category_id", "tenant"])
    op.bulk_insert(
        category,
        [
            {
                "id": identifier,
                "tenant": "*",
                "name": name,
                "description": description,
                "builtin": 1,
                "enabled": 1,
                "detector": "builtin",
                "action": "BLOCK",
                "values_json": "[]",
                "revision": 1,
            }
            for identifier, name, description in BUILTINS
        ],
    )
    connection = op.get_bind()
    known = {}
    rows = connection.execute(sa.text("SELECT id, tenant, draft FROM policies WHERE status <> 'DELETED'")).mappings().all()
    for policy in rows:
        document = json.loads(policy["draft"])
        changed = False
        for rule in document.get("custom_categories", []):
            legacy_id = rule["id"]
            category_id = str(uuid5(NAMESPACE_URL, f"gpv-category:{policy['tenant']}:{legacy_id}"))
            attributes = (
                rule["name"],
                rule.get("description", ""),
                int(rule.get("enabled", True)),
                rule.get("action", "BLOCK"),
                rule["detection"],
                json.dumps(rule["values"]),
            )
            if category_id not in known:
                connection.execute(
                    category.insert().values(
                        id=category_id,
                        tenant=policy["tenant"],
                        name=attributes[0],
                        description=attributes[1],
                        builtin=0,
                        enabled=attributes[2],
                        action=attributes[3],
                        detector=attributes[4],
                        values_json=attributes[5],
                        revision=1,
                    )
                )
                known[category_id] = attributes
            elif known[category_id] != attributes:
                raise RuntimeError("Conflicting embedded category definitions require operator review before migration 009")
            connection.execute(
                sa.text("INSERT INTO policy_categories (tenant, policy_id, category_id) VALUES (:tenant, :policy_id, :category_id)"),
                {"tenant": policy["tenant"], "policy_id": policy["id"], "category_id": category_id},
            )
            rule["id"] = category_id
            changed = True
        if changed:
            connection.execute(
                sa.text(
                    "UPDATE policies SET draft = :draft, revision = revision + 1, row_version = row_version + 1 "
                    "WHERE id = :policy_id AND tenant = :tenant"
                ),
                {"draft": json.dumps(document), "policy_id": policy["id"], "tenant": policy["tenant"]},
            )


def downgrade():
    raise RuntimeError("Category associations require a reviewed forward migration")
