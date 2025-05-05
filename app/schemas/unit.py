from pydantic import BaseModel, Field


class UnitCreate(BaseModel):
    """
    Schema for creating a new unit
    """
    name: str = Field(..., description="Name of the unit")
    description: str = Field(..., description="Description of the unit")
    course_id: int = Field(...,
                           description="ID of the course to which the unit belongs")
    unit_id: int = Field(..., description="ID of the unit")
    created_at: str = Field(..., description="Creation date of the unit")
    updated_at: str = Field(..., description="Last update date of the unit")


class UpdateUnitRequest(BaseModel):
    """
    Schema for the request to update a unit.
    """
    description: str = Field(..., description="New description for the unit")
    content: str = Field(..., description="New content for the unit")
