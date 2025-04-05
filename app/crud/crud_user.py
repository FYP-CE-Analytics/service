from app.crud.base import CRUDBase
from motor.core import AgnosticDatabase
from app.models.user import UserModel
from app.schemas.user import UserCreate, UserUpdate
from fastapi import HTTPException


class CRUDUser(CRUDBase[UserModel, UserCreate, UserUpdate]):
    async def create(self, db: AgnosticDatabase, *, obj_in: UserCreate) -> UserModel:
        user = {
            **obj_in.model_dump()
        }

        return await self.engine.save(UserModel(**user))


user = CRUDUser(UserModel)
