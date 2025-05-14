from app.crud.base import CRUDBase
from app.models.semester_schedule import SemesterModel
from app.schemas.semester_schedule import SemesterCreate, SemesterUpdate

class CRUDSemester(CRUDBase[SemesterModel, SemesterCreate, SemesterUpdate]):
    """
    CRUD operations for SemesterModel.
    """
    pass

semester = CRUDSemester(SemesterModel) 