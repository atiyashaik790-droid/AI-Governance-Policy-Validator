"""Exact remaining Azure review fixture, on disposable revision 008."""
from sqlalchemy import select
from app.models import Audit, Review, ReviewAssignment
import test_execution_008_application as application008
import test_protected_reviews as reviews

protected = application008.protected
template007 = application008.template007


def test_real_assignment_fixture_rejects_invalid_reason_then_reveals_and_resolves(protected):
    client, _, factory = protected
    reviews.install(factory)
    held = reviews.submit(client)
    rid = held["review_id"]
    with factory() as db:
        initial_version = db.get(Review, rid).row_version
    response = client.put(f"/api/reviews/{rid}/assignment", json={"assigned_reviewer": "reviewer", "reason": "Synthetic test"})
    assert response.status_code == 422
    with factory() as db:
        assert db.get(Review, rid).row_version == initial_version
        assert db.get(ReviewAssignment, rid) is None
    response = client.put(f"/api/reviews/{rid}/assignment", json={"assigned_reviewer": "reviewer", "reason": "Assigned for review"})
    assert response.status_code == 200
    with factory() as db:
        version = db.get(Review, rid).row_version
        assert db.get(ReviewAssignment, rid).reason == "Assigned for review"
    reviews.login(client)
    shown = reviews.reveal(client, rid, version)
    assert shown.status_code == 200 and shown.headers["cache-control"] == "no-store"
    disposed = client.post(f"/api/reviews/{rid}/approve", json={"reason": "Resubmission required"})
    assert disposed.status_code == 200
    with factory() as db:
        actions = list(db.scalars(select(Audit.action).where(Audit.resource == rid)))
        assert {"review.assigned", "review.content.viewed"} <= set(actions)

