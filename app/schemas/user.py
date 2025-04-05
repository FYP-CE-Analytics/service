from pydantic import EmailStr, Field, ConfigDict
from edapi import CourseInfo
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
    selected_unit: List[UnitSyncInfo] = Field(
        default_factory=list,
        description="List of selected unit IDs for the user."
    )


class UserUpdate(BaseBSONModel):
    """Schema for updating an existing user"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    api_key: Optional[str] = None
    selected_units: Optional[List[UnitSyncInfo]] = None


class UserResponse(BaseBSONModel):
    id: ObjectId
    name: str
    email: EmailStr
    selected_units: List[UnitSyncInfo] = Field(default_factory=list)

    @classmethod
    def from_model(cls, user: UserModel):
        """Convert UserModel to UserResponse schema"""
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            selected_units=[
                UnitSyncInfo.from_model(unit) for unit in user.selected_units
            ]
        )


class UserEdCoursesResponse(BaseBSONModel):
    """Response schema for Ed courses"""
    active: list[CourseInfo]


class UnitIdsUpdate(BaseBSONModel):
    selectedId: List[int]
