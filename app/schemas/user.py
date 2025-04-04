from pydantic import BaseModel, EmailStr, Field, ConfigDict
from edapi import CourseInfo
from typing import List, Optional
from bson import ObjectId


class UserBase(BaseModel):
    """Base class for user schemas with common fields"""
    name: str
    email: EmailStr


class UserCreate(UserBase):
    """Schema for creating a new user"""
    api_key: str
    # Make selected_unit_ids optional during creation
    selected_unit_ids: List[int] = Field(
        default_factory=list,
        description="List of selected unit IDs for the user."
    )


class UserUpdate(BaseModel):
    """Schema for updating an existing user"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    api_key: Optional[str] = None
    selected_unit_ids: Optional[List[int]] = None


class UserInDB(UserBase):
    """Schema for user as stored in database"""
    id: str
    api_key: str
    selected_unit_ids: List[int] = Field(
        default_factory=list,
        description="List of selected unit IDs for the user."
    )


def objectid_to_str(obj: ObjectId) -> str:
    return str(obj)


class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    selected_unit_ids: List[int] = Field(default_factory=list)


class UserEdCoursesResponse(BaseModel):
    """Response schema for Ed courses"""
    active: list[CourseInfo]


class UnitIdsUpdate(BaseModel):
    selectedId: List[int]
