from pydantic import BaseModel, Field
from typing import List
from datetime import datetime
from app.models.semester_schedule import SemesterPhaseType, SemesterModel
from pydantic import ConfigDict


class SemesterPhaseSchema(BaseModel):
    """
    Schema for a semester phase (e.g., teaching period, break).
    """
    type: SemesterPhaseType = Field(..., description="Phase type")
    start_date: datetime = Field(..., alias="startDate", description="Phase start date")
    end_date: datetime = Field(..., alias="endDate", description="Phase end date")

class SemesterCreate(BaseModel):
    """
    Schema for creating a semester.
    """
    year: int = Field(..., description="Academic year")
    semester: int = Field(..., description="Semester number")
    phases: List[SemesterPhaseSchema] = Field(..., description="List of semester phases")

class SemesterUpdate(BaseModel):
    """
    Schema for updating a semester.
    """
    year: int = Field(..., description="Academic year")
    semester: int = Field(..., description="Semester number")
    phases: List[SemesterPhaseSchema] = Field(..., description="List of semester phases")
    


class SemesterResponse(BaseModel):
    """
    Schema for semester schedule response.
    """
    id: int = Field(..., description="Semester ID")
    year: int = Field(..., description="Academic year")
    semester: int = Field(..., description="Semester number")
    phases: List[dict] = Field(default_factory=list, description="List of semester phases")

    @classmethod
    def from_model(cls, sem: SemesterModel):
        return cls(
            id=sem.id,
            year=sem.year,
            semester=sem.semester,
            phases=[{
                "type": phase.type,
                "startDate": phase.start_date,
                "endDate": phase.end_date
            } for phase in sem.phases]
        ) 