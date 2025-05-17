from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime
from app.models import UnitModel


class WeekDetails(BaseModel):
    """
    Schema for week configuration
    """
    week_id: int = Field(..., description="Week number in the unit", alias="weekId")
    teaching_week_number: int = Field(..., description="Teaching week number in the unit", alias="teachingWeekNumber")
    week_type: str = Field(..., description="Week type in the unit", alias="weekType")
    start_date: datetime = Field(..., description="Start date of the week", alias="startDate")
    end_date: datetime = Field(..., description="End date of the week", alias="endDate")
    content: str = Field(default="", description="Content for this week")

    class Config:
        populate_by_name = True
        allow_population_by_field_name = True


class UnitCreate(BaseModel):
    """
    Schema for creating a new unit
    """
    name: str = Field(..., description="Name of the unit")
    description: str = Field(default="", description="Description of the unit")
    code: str = Field(..., description="Unit code")
    unit_id: int = Field(..., description="ID of the unit")
    year: int = Field(..., description="Academic year")
    session: str = Field(...,
                         description="Academic session (e.g., Semester 1)")
    content: str = Field(default="", description="Content of the unit")
    created_at: Optional[str] = Field(
        None, description="Creation date of the unit")
    updated_at: Optional[str] = Field(
        None, description="Last update date of the unit")
    weeks: List[WeekDetails] = Field(
        default_factory=list, description="Week configurations")


class UpdateUnitRequest(BaseModel):
    """
    Schema for the request to update a unit.
    """
    description: Optional[str] = Field(
        None, description="New description for the unit")
    content: Optional[str] = Field(
        None, description="New content for the unit")
    weeks: Optional[List[WeekDetails]] = Field(
        None, description="Week configurations", alias="weeks")


class UnitResponse(BaseModel):
    """
    Schema for unit response
    """
    id: int = Field(..., description="Unit ID")
    name: str = Field(..., description="Name of the unit")
    code: str = Field(..., description="Unit code")
    description: Optional[str] = Field(
        None, description="Description of the unit")
    content: str = Field(default="", description="Content of the unit")
    year: int = Field(..., description="Academic year")
    session: str = Field(..., description="Academic session")
    weeks: List[WeekDetails] = Field(
        default_factory=list, description="Week configurations")

    @classmethod
    def from_model(cls, unit: UnitModel):
        """Convert UserModel to UserResponse schema"""
        return cls(
            **unit.model_dump(exclude={"weeks"}),
            weeks=[WeekDetails.model_validate(week.model_dump()) for week in unit.weeks]
        )


class ThreadRequest(BaseModel):
    """
    Schema for thread request
    """
    user_id: int = Field(..., description="User ID")
    course_id: int = Field(..., description="Course ID")
    limit: Optional[int] = Field(..., description="Limit")
    offset: Optional[int] = Field(..., description="Offset")

    
