from pydantic import EmailStr, Field, BaseModel
from typing import List, Optional
from bson import ObjectId
from odmantic.bson import BaseBSONModel, ObjectId
from datetime import datetime
from app.models.user import UserModel, UnitSyncInfoModel


class UserBase(BaseBSONModel):
    """Base class for user schemas with common fields"""
    name: str
    email: EmailStr


class UnitSyncInfo(BaseBSONModel):
    unit_id: int
    last_synced: Optional[datetime] = Field(default=None)

    @classmethod
    def from_model(self, unit: UnitSyncInfoModel):
        """Convert UnitSyncInfoModel to UnitSyncInfo schema"""
        return self(
            unit_id=unit.unit_id,
            last_synced=unit.last_synced
        )


class UserCreate(UserBase):
    """Schema for creating a new user"""
    api_key: str
    # Make selected_unit_ids optional during creation
    # selected_unit: Optional[List[UnitSyncInfo]] = Field(
    #     default_factory=list,
    #     description="List of selected unit IDs for the user."
    # )


class CourseInfo(BaseModel):
    id: int
    code: str
    name: str
    year: str
    session: str
    status: str


class UserUpdate(BaseBSONModel):
    """Schema for updating an existing user"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    api_key: Optional[str] = Field(None, alias="apiKey")
    selected_units: Optional[List[UnitSyncInfo]] = Field(
        default_factory=list,
        description="List of selected unit IDs for the user.",
        alias="selectedUnits"
    )

    class Config:
        populate_by_name = True  # Important to make aliases work


class UserEdCoursesResponse(BaseBSONModel):
    """Response schema for Ed courses"""
    active: list[CourseInfo]


class UserResponse(BaseBSONModel):
    id: ObjectId
    name: str
    email: EmailStr
    selectedUnits: List[UnitSyncInfo] = Field(default_factory=list)
    availableUnits: List[CourseInfo] = Field(default_factory=list)

    @classmethod
    def from_model(cls, user: UserModel):
        """Convert UserModel to UserResponse schema"""
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            selectedUnits=[
                UnitSyncInfo.from_model(unit) for unit in user.selected_units
            ],
            availableUnits=[
                CourseInfo(**unit.model_dump()) for unit in user.available_units
            ]
        )
