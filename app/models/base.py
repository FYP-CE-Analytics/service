from odmantic import Model, Field
from datetime import datetime

from app.utils.shared import datetime_now_sec


class BaseModel(Model):
    created: datetime = Field(default_factory=datetime_now_sec)
    modified: datetime = Field(default_factory=datetime_now_sec)
