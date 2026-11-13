"""Shared dependency declarations; preserve original callable identity and scope."""

from fastapi import Depends
from .database import get_database
from .security import authenticate

# Finish the transaction before sending success, including dependency commit failures.
DB = Depends(get_database, scope="function")
USER = Depends(authenticate)
