"""Explicit, session/CSRF-protected content reveal; never part of metadata APIs."""
from fastapi import APIRouter, Header, Response
from sqlalchemy.orm import Session
from ..dependencies import DB, USER
from ..security import Identity
from ..protected_reviews import RevealRequest, reveal

router = APIRouter(tags=["Protected human review"])


@router.post("/api/reviews/{review_id}/content")
def content(review_id: str, payload: RevealRequest, response: Response, db: Session = DB, user: Identity = USER,
            if_match: str | None = Header(None, alias="If-Match")):
    result = reveal(db, user, review_id, if_match)
    response.headers["Cache-Control"] = "no-store"
    return result
