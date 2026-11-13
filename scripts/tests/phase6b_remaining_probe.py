"""Short remaining review assertions; synthetic ORM setup, no generation calls."""
import json

from sqlalchemy import select


def check_remaining(client, engine, factory, secure, tenant, actor,
                    prompt="internal-only synthetic original"):
    from app.models import Audit, Execution, Policy, Review, Version
    from app.models_review_content import ProtectedReviewContent as Content

    checks = []
    with factory() as db:
        policy = Policy(tenant=tenant, name="Synthetic remaining probe", draft='{"name":"Synthetic remaining probe","rules":{}}', status="PUBLISHED")
        db.add(policy)
        db.flush()
        db.add(Version(tenant=tenant, policy_id=policy.id, number=1, document=policy.draft))
        db.flush()
        execution = Execution(tenant=tenant, actor=actor, policy_id=policy.id, version=1,
                              model="synthetic-no-provider", decision="HUMAN_REVIEW",
                              metadata_json=json.dumps({"input": {"decision": "HUMAN_REVIEW"}}))
        db.add(execution)
        db.flush()
        execution_id = execution.id

        def seed(created, original):
            review = Review(tenant=tenant, execution_id=execution_id)
            db.add(review)
            db.flush()
            content = secure.encrypt_prompt(original, tenant, review.id, execution_id, created)
            db.add(content)
            db.add(Audit(tenant=tenant, actor=actor, action="review.content.retained", resource=review.id))
            db.flush()
            return review.id

        rid = seed(secure.clock(db), prompt)
        db.commit()
        row = db.get(Content, (tenant, rid))
        assert row.expires_at - row.created_at == secure.RETENTION == 604800
        assert prompt.encode() not in row.ciphertext and len(row.nonce) == 12
        assert secure.decrypt_prompt(row, execution_id) == prompt
    checks.append("synthetic encrypted capture and seven-day retention")

    def reveal(version):
        return client.post(f"/api/reviews/{rid}/content", json={}, headers={"If-Match": f'"{version}"'})

    assert reveal(1).status_code == 403
    assigned = client.put(f"/api/reviews/{rid}/assignment",
                          json={"assigned_reviewer": actor, "reason": "Assigned for review"})
    assert assigned.status_code == 200, assigned.status_code
    with factory() as db:
        version = db.get(Review, rid).row_version
    assert reveal(version + 1).status_code == 412
    shown = reveal(version)
    assert shown.status_code == 200, shown.status_code
    assert shown.json()["original_prompt"] == prompt
    assert shown.headers["cache-control"] == "no-store"
    with factory() as db:
        assert db.scalar(select(Audit.id).where(Audit.tenant == tenant, Audit.resource == rid,
                                               Audit.action == "review.content.viewed"))
    checks.append("unassigned/stale denial, assignment, exact reveal and committed access audit")
    disposed = client.post(f"/api/reviews/{rid}/approve", json={"reason": "Resubmission required"})
    assert disposed.status_code == 200, disposed.status_code
    with factory() as db:
        assert db.get(Content, (tenant, rid)) is None
        assert db.scalar(select(Audit.id).where(Audit.tenant == tenant, Audit.resource == rid,
                                               Audit.action == "review.content.purged"))
    checks.append("disposition and audited ciphertext purge")

    with factory() as db:
        now = secure.clock(db)
        retained_id = seed(now, prompt)
        expired_id = seed(now - secure.RETENTION - 1, "expired synthetic")
        db.commit()
        cutoff = secure.clock(db)
        expired = db.get(Content, (tenant, expired_id))
        retained = db.get(Content, (tenant, retained_id))
        assert expired.expires_at <= cutoff and expired.expires_at - expired.created_at == 604800
        assert retained.expires_at > cutoff
        assert db.scalar(select(Content.review_id).where(Content.tenant == tenant,
                          Content.review_id == expired_id, Content.expires_at <= cutoff)) == expired_id
    print(json.dumps({"event": "cleanup.fixture", "created_at": expired.created_at,
                      "expires_at": expired.expires_at, "cutoff": cutoff,
                      "retained_expires_at": retained.expires_at, "eligible": True}), flush=True)
    cleaned = secure.cleanup_once(engine, factory)
    assert cleaned["healthy"] and cleaned["removed"] >= 1, cleaned
    with factory() as db:
        assert db.get(Content, (tenant, expired_id)) is None
        assert db.scalar(select(Audit.id).where(Audit.tenant == tenant, Audit.resource == expired_id,
                                               Audit.action == "review.content.expired"))
        retained = db.get(Content, (tenant, retained_id))
        assert retained is not None and secure.decrypt_prompt(retained, execution_id) == prompt
    assert secure.health.healthy(engine)
    checks.append("SQL-clock expiry eligibility, healthy actual cleanup, expiry audit and retained decryptability")
    return checks
