from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date, datetime
from app.models import UnitModel


class WeekConfig(BaseModel):
    """
    Schema for week configuration
    """
    week_number: int = Field(...,
                             description="Week number in the unit", alias="weekNumber")
    start_date: datetime = Field(...,
                                 description="Start date of the week", alias="startDate")
    end_date: datetime = Field(...,
                               description="End date of the week", alias="endDate")
    content: str = Field(default="", description="Content for this week")


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
    weeks: List[WeekConfig] = Field(
        default_factory=list, description="Week configurations")


class UpdateUnitRequest(BaseModel):
    """
    Schema for the request to update a unit.
    """
    description: Optional[str] = Field(
        None, description="New description for the unit")
    content: Optional[str] = Field(
        None, description="New content for the unit")
    weeks: Optional[List[WeekConfig]] = Field(
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
    weeks: List[dict] = Field(
        default_factory=list, description="Week configurations")

    @classmethod
    def from_model(cls, unit: UnitModel):
        """Convert UserModel to UserResponse schema"""
        return cls(
            **unit.model_dump(exclude={"weeks"}),
            weeks=[{
                "weekNumber": week.week_number, "startDate": week.start_date, "endDate": week.end_date, "content": week.content} for week in unit.weeks]
        )
