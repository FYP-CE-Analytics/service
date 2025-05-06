from odmantic import Field, Index, EmbeddedModel, Model
from pydantic.networks import EmailStr
from datetime import datetime
from typing import Optional
from pydantic import field_validator


class UnitSyncInfoModel(EmbeddedModel):
    unit_id: int
    last_synced: Optional[datetime] = Field(default=None)


class UnitInfoModel(EmbeddedModel):
    id: int
    name: str
    code: str
    year: str
    session: str
    status: str = Field(default="active")


class UserModel(Model):
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    name: str = Field(default="")
    email: EmailStr = Field(unique=True)
    api_key: str = Field(default=None)
    selected_units: list[UnitSyncInfoModel] = Field(default_factory=list)
    available_units: list[UnitInfoModel] = Field(default_factory=list)
