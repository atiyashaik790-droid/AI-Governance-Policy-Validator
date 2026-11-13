from fastapi import APIRouter
from sqlalchemy.orm import Session
from ..dependencies import DB, USER
from ..security import Identity
from ..integration_verification import Integration, VerificationRequest, verify

router = APIRouter(tags=["Integration verification"])


@router.post("/api/integrations/{integration}/verify")
async def verify_integration(integration: Integration, payload: VerificationRequest,
                             db: Session = DB, user: Identity = USER):
    return await verify(db, user, integration)
