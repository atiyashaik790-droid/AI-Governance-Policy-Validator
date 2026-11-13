"""Reuse established encrypted-review assertions on the additive 008 schema."""
import pytest
import test_multi_policy_phase_b as phase_b
import test_protected_reviews as reviews

protected = reviews.protected


@pytest.fixture(scope="module")
def template007(tmp_path_factory):
    path = tmp_path_factory.mktemp("execution008-review") / "008.db"
    phase_b.migrate(path, "008")
    return path


@pytest.mark.parametrize("multi", [False, True])
def test_encrypted_capture_reveal_on_008(protected, monkeypatch, multi):
    reviews.test_capture_exact_prompt_only_on_hold_and_reveal_is_separate(protected, monkeypatch, multi, None)


@pytest.mark.parametrize("actor", ["foreign", "user"])
def test_tenant_and_role_denied_on_008(protected, actor):
    reviews.test_only_explicitly_assigned_same_tenant_reviewer_session(protected, actor)


def test_session_assignment_resolution_on_008(protected):
    reviews.test_bearer_session_version_assignment_and_resolution(protected)


def test_expiry_and_cleanup_on_008(protected, monkeypatch):
    reviews.test_expiry_immediate_and_concurrent_cleanup_idempotent(protected, monkeypatch)


def test_ciphertext_and_tenant_fk_on_008(protected):
    reviews.test_ciphertext_cannot_be_updated_and_tenant_fk_is_enforced(protected)
