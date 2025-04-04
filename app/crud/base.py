from typing import Any, Dict, Generic, Type, TypeVar, Union, Optional

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from motor.core import AgnosticDatabase
from odmantic import AIOEngine
from bson import ObjectId

from odmantic import Model as Base
from app.core.config import settings
from app.db.session import get_engine

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        """
        CRUD object with default methods to Create, Read, Update, Delete (CRUD).
        """
        self.model = model
        self.engine: AIOEngine = get_engine()

    def _prepare_for_serialization(self, obj: Optional[ModelType]) -> Optional[Dict[str, Any]]:
        """Convert ObjectId to string for serialization"""
        if obj is None:
            return None

        # Convert to dict
        if hasattr(obj, "dict"):
            obj_dict = obj.dict()
        else:
            obj_dict = jsonable_encoder(obj)

        # Convert ObjectId to string
        if "id" in obj_dict and isinstance(obj_dict["id"], ObjectId):
            obj_dict["id"] = str(obj_dict["id"])

        return obj_dict

    def _prepare_list_for_serialization(self, objs: list[ModelType]) -> list[Dict[str, Any]]:
        """Convert ObjectIds to strings for a list of objects"""
        return [self._prepare_for_serialization(obj) for obj in objs]

    async def get(self, db: AgnosticDatabase, id: Any) -> Optional[Dict[str, Any]]:
        """Get object by ID with ObjectId handling"""
        # Handle string IDs by converting to ObjectId if needed
        if isinstance(id, str) and ObjectId.is_valid(id):
            id = ObjectId(id)

        obj = await self.engine.find_one(self.model, self.model.id == id)
        return self._prepare_for_serialization(obj)

    async def get_multi(self, db: AgnosticDatabase, *, page: int = 0, page_break: bool = False) -> list[Dict[str, Any]]:
        offset = {"skip": page * settings.MULTI_MAX,
                  "limit": settings.MULTI_MAX} if page_break else {}
        objs = await self.engine.find(self.model, **offset)
        return self._prepare_list_for_serialization(objs)

    async def create(self, db: AgnosticDatabase, *, obj_in: CreateSchemaType) -> Dict[str, Any]:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)
        created_obj = await self.engine.save(db_obj)
        return self._prepare_for_serialization(created_obj)

    async def update(
        self, db: AgnosticDatabase, *, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> Dict[str, Any]:
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        updated_obj = await self.engine.save(db_obj)
        return self._prepare_for_serialization(updated_obj)

    async def remove(self, db: AgnosticDatabase, *, id: Any) -> Optional[Dict[str, Any]]:
        # Handle string IDs by converting to ObjectId if needed
        if isinstance(id, str) and ObjectId.is_valid(id):
            id = ObjectId(id)

        obj = await self.engine.find_one(self.model, self.model.id == id)
        if obj:
            await self.engine.delete(obj)
        return self._prepare_for_serialization(obj)
