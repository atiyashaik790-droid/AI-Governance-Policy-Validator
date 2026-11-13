"""Candidate-created ciphertext is readable unchanged by preserved rollback code."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from app.config import settings
import test_execution_008_application as application008
import test_protected_reviews as reviews

protected = application008.protected
template007 = application008.template007


@pytest.mark.parametrize("artifact_path,checksum", [
    ("artifacts/final-demo-readiness-2026-11-07/rollback-1.2-677a11e4b649fa7d.zip", "be1ab97768954fecb5cf26b255bfcecf2a22811848ca910536846b3784174ee9"),
    ("artifacts/master-repair-2026-11-07/rollback-cleanup-fixed.zip", "b52287bbf048a66a9f7233753a3fb95730397016f03074d4deb399c1e74c0d29"),
])
def test_distinct_rollback_preserves_candidate_ciphertext(protected, tmp_path, artifact_path, checksum):
    client, engine, _ = protected
    reviews.install(protected[2])
    reviews.submit(client, prompt="internal-only rollback synthetic fixture")
    root = Path(__file__).resolve().parents[2]
    out = root / "docs/evidence/final-demo-readiness-2026-11-07"
    artifact = root / artifact_path
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == checksum
    rollback = tmp_path / "independent-rollback"
    with zipfile.ZipFile(artifact) as archive:
        assert archive.testzip() is None
        archive.extractall(rollback)
    database = Path(engine.url.database)
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    code = '''
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from app.database import engine
from app.models import Review
from app.models_review_content import ProtectedReviewContent as Content
from app.protected_reviews import decrypt_prompt
with Session(engine) as db:
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == "008"
    rows = list(db.scalars(select(Content)))
    assert rows
    for row in rows:
        review = db.get(Review, row.review_id)
        assert decrypt_prompt(row, review.execution_id) == "internal-only rollback synthetic fixture"
engine.dispose()
print("PASS: distinct rollback reads candidate ciphertext at revision 008")
'''
    env = {"PATH": os.environ["PATH"], "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONPATH": str(out / "continued-guard") + ":" + str(rollback),
           "DATABASE_URL": "sqlite:///" + str(database), "PROVIDER_MODE": "fixture", "PII_MODE": "regex",
           "REVIEW_CONTENT_ACTIVE_KEY_ID": settings.review_content_active_key_id,
           "REVIEW_CONTENT_KEYS_JSON": settings.review_content_keys_json}
    result = subprocess.run([sys.executable, "-B", "-c", code], cwd="/tmp", env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, "Rollback ciphertext preservation failed; inspect sanitized local diagnostics"
    assert "PASS: distinct rollback" in result.stdout
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
