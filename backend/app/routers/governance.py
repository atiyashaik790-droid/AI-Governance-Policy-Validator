"""Usage HTTP handler; typed governance operation routes are registered in main."""

from sqlalchemy.orm import Session
from ..dependencies import DB, USER
from ..security import Identity, require_role
from .. import usage


def inference_usage(db: Session = DB, user: Identity = USER):
    require_role(user, "Admin", "Auditor")
    return usage.summary(db, user)
