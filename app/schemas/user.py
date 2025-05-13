from pydantic import EmailStr, Field, ConfigDict
from typing import List, Optional
from bson import ObjectId
from odmantic.bson import BaseBSONModel, ObjectId
from app.models.user import UserModel
from edapi.models.course import CourseInfo

# exclude last_active from CourseInfo
class CourseInfoNoLastActive(CourseInfo):
    last_active: Optional[str] = None


class UserBase(BaseBSONModel):
    """Base class for user schemas with common fields"""
    name: str
    email: EmailStr


class UserCreate(UserBase):
    """Schema for creating a new user"""
    api_key: str


class UserUpdate(BaseBSONModel):
    """Schema for updating an existing user"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    api_key: Optional[str] = Field(None, alias="apiKey")
    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda x: ''.join(word.capitalize() if i else word for i, word in enumerate(x.split('_')))
    )

class UserUpdateSelectedUnits(BaseBSONModel):
    """Schema for updating the selected units of a user"""
    selected_units: List[int] = Field(default_factory=list, alias="selectedUnits")


class UserResponse(BaseBSONModel):
    id: ObjectId
    name: str
    email: EmailStr
    api_key: str = Field(alias="apiKey")
    selected_units: List[CourseInfoNoLastActive] = Field(default_factory=list, alias="selectedUnits")
    available_units: List[CourseInfoNoLastActive] = Field(default_factory=list, alias="availableUnits")
    previous_units: List[CourseInfoNoLastActive] = Field(default_factory=list, alias="previousUnits")

    model_config = ConfigDict(
        populate_by_name=True,
        alias_generator=lambda x: ''.join(word.capitalize() if i else word for i, word in enumerate(x.split('_')))
    )

    @classmethod
    def from_model(cls, user: UserModel):
        """Convert UserModel to UserResponse schema"""
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            api_key=user.api_key,
            selected_units=[
                CourseInfoNoLastActive(
                    **unit.model_dump(),
                ) for unit in user.selected_units
            ],
            available_units=[
                CourseInfoNoLastActive(**unit.model_dump())
                for unit in user.available_units
            ],
            previous_units=[
                CourseInfoNoLastActive(
                    **unit.model_dump(),
                ) for unit in user.previous_units
            ]
        )
