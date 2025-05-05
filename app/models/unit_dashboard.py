from odmantic import Field, Model
from datetime import datetime
from typing import Dict, Any, Optional


class UnitModel(Model):
    """
    Model representing a unit in the system.
    """
    # make it the identifier
    id: int = Field(primary_field=True)
    name: str = Field()
    code: str = Field(default="")
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="active")
    # Additional metadata for the unit
    metadata: Dict[str, Any] = Field(default_factory=dict)
    content: str = Field(default="")  # Content of the unit
