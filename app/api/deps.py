from typing import Generator
from app.db.session import MongoDatabase
from fastapi import Depends, HTTPException
from app.services.ed_forum_service import EdService
from motor.core import AgnosticDatabase


def get_db() -> Generator:
    try:
        db = MongoDatabase()
        yield db
    finally:
        pass


async def get_user_ed_service(email: str, db: AgnosticDatabase = Depends(get_db)) -> EdService:
    """
    Get user ed service
    """
    user = await db.user.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Assuming user object has api_key attribute
    return EdService(api_key=user["api_key"])
