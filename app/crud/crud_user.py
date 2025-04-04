from app.crud.base import CRUDBase
from motor.core import AgnosticDatabase
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from pymongo.errors import DuplicateKeyError


class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    async def create(self, db: AgnosticDatabase, *, obj_in: UserCreate) -> User:
        user = {
            **obj_in.model_dump()
        }

        return await self.engine.save(User(**user))

    async def get_user_by_email(self, db: AgnosticDatabase, *, email: str) -> User:
        user = await self.engine.find_one(User, User.email == email)

        if not user:
            raise DuplicateKeyError(f"User with email {email} already exists.")
        return self._prepare_for_serialization(user)


user = CRUDUser(User)
