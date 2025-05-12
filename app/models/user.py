from odmantic import Field, EmbeddedModel, Model
from pydantic.networks import EmailStr
from typing import List
from datetime import datetime


class CourseInfoEmbededModel(EmbeddedModel):
    id: int = Field(...)
    code: str = Field(...)
    name: str = Field(...)
    year: str = Field(...)
    session: str = Field(...)
    status: str = Field(...)
    created_at: str = Field(...)
    status: str = Field(...)

class UserModel(Model):
    name: str = Field(...)
    email: EmailStr = Field(unique=True)
    api_key: str = Field(...)
    selected_units: List[CourseInfoEmbededModel] = Field(default_factory=list)
    available_units: List[CourseInfoEmbededModel] = Field(default_factory=list)  # Direct CourseInfo from Ed API
    previous_units: List[CourseInfoEmbededModel] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
