from app.crud.base import CRUDBase
from motor.core import AgnosticDatabase
from app.models import UnitModel
from app.schemas.user import CourseInfoNoLastActive
from app.schemas.unit import UpdateUnitRequest
from fastapi import HTTPException


class CRUDUnit(CRUDBase[UnitModel, CourseInfoNoLastActive, UpdateUnitRequest]):
    async def create(self, db: AgnosticDatabase, *, obj_in: CourseInfoNoLastActive) -> UnitModel:
        unit = {
            **obj_in.model_dump()
        }

        return await self.engine.save(UnitModel(**unit))


unit = CRUDUnit(UnitModel)
