from odmantic import Field, Model, EmbeddedModel
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import field_validator


class UnitStatus(str, Enum):
    ACTIVE = "active"  # Currently selected by user
    PAST = "past"      # Previously selected but now removed
    AVAILABLE = "available"  # Available but not selected
    ARCHIVED = "archived"    # No longer available in Ed


class UnitWeeks(EmbeddedModel):
    """
    Model representing the weeks of a unit.
    """
    week_id: int = Field(default=1)
    teaching_week_number: int = Field(default=1)
    start_date: datetime = Field(default_factory=datetime.now)
    end_date: datetime = Field(default_factory=datetime.now)
    content: str = Field(default="")
    thread_count: int = Field(default=0)
    week_type: str = Field(default="teaching")  # Can be "teaching", "break", "exam", etc.
    category_counts: Dict[str, int] = Field(default_factory=dict)  # Store counts of threads by category for this week



class ThreadMetadata(EmbeddedModel):
    """
    Model representing thread metadata stored in unit
    """
    id: str = Field(...)
    title: str = Field(default="")
    content: str = Field(default="")
    created_at: str = Field(default="")  # Store as ISO format string
    updated_at: str = Field(default="")  # Store as ISO format string
    is_answered: bool = Field(default=False)
    needs_attention: bool = Field(default=False)  # Simple flag for attention
    themes: List[str] = Field(default_factory=list)  # Multiple themes per thread
    last_sync_at: str = Field(default="")  # Store as ISO format string
    
    # Additional metadata fields
    vote_count: int = Field(default=0)
    thread_type: str = Field(default="")
    category: str = Field(default="")



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
    year: str = Field(...)
    session: str = Field(default="")
    created_at: str = Field(default="")  # Store as ISO format string
    updated_at: str = Field(default="")  # Store as ISO format string
    status: UnitStatus = Field(default=UnitStatus.ACTIVE)
    weeks: List[UnitWeeks] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    last_sync_at: str = Field(default="")  # Store as ISO format string
    thread_count: int = Field(default=0)
    threads: List[ThreadMetadata] = Field(default_factory=list)  # Store thread metadata
    question_cluster_ids: List[str] = Field(default_factory=list)  # Reference to question clusters