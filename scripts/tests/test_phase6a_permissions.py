"""Static least-privilege proposal checks; never execute SQL."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("revision,expected", [
    ("006", {"workspace_policy_states": {"SELECT", "INSERT", "UPDATE", "VIEW DEFINITION"},
             "workspace_policy_assignments": {"SELECT", "INSERT", "UPDATE", "VIEW DEFINITION"},
             "workspace_policy_assignment_events": {"SELECT", "INSERT", "VIEW DEFINITION"},
             "execution_policy_evidence": {"SELECT", "INSERT", "VIEW DEFINITION"}}),
    ("007", {"review_protected_content": {"SELECT", "INSERT", "DELETE", "VIEW DEFINITION"}}),
])
def test_proposals_are_guarded_and_object_scoped(revision, expected):
    source = (ROOT / f"deployment/phase6a-runtime-{revision}-grants.REVIEW_ONLY.sql").read_text()
    grants = {}
    for operations, table in re.findall(r"GRANT ([A-Z, ]+) ON OBJECT::dbo\.(\w+) TO \[governance_validator_web_runtime\];", source):
        grants.setdefault(table, set()).update(part.strip() for part in operations.split(","))
    assert grants == expected
    assert "DECLARE @explicit_approval bit = 0" in source
    assert "REPLACE_WITH_RECONFIRMED_CONTAINED_MI_CLIENT_ID" in source
    assert f"version_num=N'{revision}'" in source
    assert "DB_NAME() <> N'sqldb-governance-validator-dev'" in source
    statements = "\n".join(line for line in source.splitlines() if not line.startswith("--"))
    assert not re.search(r"\b(CREATE|ALTER|DROP|REVOKE|DENY)\b", statements)
    assert "GRANT CONTROL" not in source and "ON SCHEMA::" not in source


def test_permission_verification_contains_no_mutation_or_impersonation():
    source = (ROOT / "deployment/phase6a-runtime-permissions.READ_ONLY.sql").read_text()
    statements = "\n".join(line for line in source.splitlines() if not line.startswith("--"))
    assert not re.search(r"\b(GRANT|REVOKE|DENY|EXECUTE|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b", re.sub(r"N'[^']*'", "", statements))
    assert "USER_NAME()" in statements and "HAS_PERMS_BY_NAME" in statements
