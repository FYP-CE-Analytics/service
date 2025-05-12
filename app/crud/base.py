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
        returns Odmantic Model instance

        **Parameters**

        * `model`: A Odmatic model class direct output from db
        * `schema`: A Pydantic model (schema) class with validation
        """
        self.model = model
        self.engine: AIOEngine = get_engine()

    async def get(self, db: AgnosticDatabase, filter: Dict[str, Any]) -> ModelType | None:
        query_conditions = []
        for field_name, field_value in filter.items():
            if hasattr(self.model, field_name):
                model_field = getattr(self.model, field_name)
                query_conditions.append(model_field == field_value)
            else:
                raise ValueError(
                    f"Field {field_name} does not exist in model {self.model.__name__}")
        if len(query_conditions) == 0:
            raise ValueError("No valid query conditions provided")
        return await self.engine.find_one(self.model, *query_conditions)

    async def get_multi(
        self, 
        db: AgnosticDatabase, 
        filter: Dict[str, Any] = None,
        *, 
        page: int = 0, 
        page_break: bool = False
    ) -> list[ModelType]:
        """
        Get multiple objects with optional filtering
        """
        query_conditions = []
        if filter:
            for field_name, field_value in filter.items():
                if hasattr(self.model, field_name):
                    model_field = getattr(self.model, field_name)
                    if isinstance(field_value, dict) and "$in" in field_value:
                        query_conditions.append(model_field.in_(field_value["$in"]))
                    else:
                        query_conditions.append(model_field == field_value)
                else:
                    raise ValueError(
                        f"Field {field_name} does not exist in model {self.model.__name__}")

        offset = {"skip": page * settings.MULTI_MAX, "limit": settings.MULTI_MAX} if page_break else {}
        return await self.engine.find(self.model, *query_conditions, **offset)

    async def create(self, db: AgnosticDatabase, *, obj_in: CreateSchemaType) -> ModelType:  # noqa
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)  # type: ignore
        return await self.engine.save(db_obj)

    async def update(
        self, db: AgnosticDatabase, *, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]]  # noqa
    ) -> ModelType:
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.model_dump(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        # TODO: Check if this saves changes with the setattr calls
        await self.engine.save(db_obj)
        return db_obj

    async def remove(self, db: AgnosticDatabase, *, id: int) -> ModelType:
        obj = await self.model.get(id)
        if obj:
            await self.engine.delete(obj)
        return obj
