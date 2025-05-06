from odmantic import Field, Model, EmbeddedModel
from datetime import datetime
from typing import Dict, Any, Optional, List


class UnitWeeks(EmbeddedModel):
    """
    Model representing the weeks of a unit.
    """
    week_number: int = Field(default=1)
    start_date: datetime = Field(default_factory=datetime.now)
    end_date: datetime = Field(default_factory=datetime.now)
    content: str = Field(default="")


class UnitModel(Model):
    """
    Model representing a unit in the system.
    """
    # make it the identifier
    id: int = Field(primary_field=True)
    name: str = Field()
    code: str = Field(default="")
    description: str = Field(default="")
    content: str = Field(default="")
    year: int = Field(default=datetime.now().year)
    session: str = Field(default="")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    status: str = Field(default="active")
    weeks: List[UnitWeeks] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
