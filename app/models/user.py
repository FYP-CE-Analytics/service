from odmantic import Field, Index
from pydantic.networks import EmailStr
from app.models.base import BaseModel


class User(BaseModel):
    name: str = Field(default="")
    email: EmailStr
    api_key: str = Field(default=None)
    selected_unit_ids: list[int] = Field(default_factory=list)

    model_config = {
        "collection": "users",
        "indexes": lambda: [
            Index(User.email, unique=True),

        ]
    }
