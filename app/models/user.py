from odmantic import Field, Index, EmbeddedModel, Model
from pydantic.networks import EmailStr
from datetime import datetime
from typing import Optional


class UnitSyncInfoModel(EmbeddedModel):
    unit_id: int
    last_synced: Optional[datetime] = Field(default=None)


class UserModel(Model):
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    name: str = Field(default="")
    email: EmailStr = Field(unique=True)
    api_key: str = Field(default=None)
    selected_units: list[UnitSyncInfoModel] = Field(default_factory=list)
