from app.crud.base import CRUDBase
from motor.core import AgnosticDatabase
from app.models import UnitModel
from edapi.models.course import CourseInfo
from app.schemas.unit import UpdateUnitRequest
from fastapi import HTTPException


class CRUDUnit(CRUDBase[UnitModel, CourseInfo, UpdateUnitRequest]):
    async def create(self, db: AgnosticDatabase, *, obj_in: CourseInfo) -> UnitModel:
        unit = {
            **obj_in.model_dump()
        }

        return await self.engine.save(UnitModel(id=unit["id"], name=unit["name"], status=unit["status"], code=unit["code"],))


unit = CRUDUnit(UnitModel)
