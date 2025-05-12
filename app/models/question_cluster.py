from odmantic import Field, Model
from datetime import datetime
from typing import List, Dict, Any, Optional


class QuestionClusterModel(Model):
    """
    Store the question clusters generated from analysis
    """
    theme: str = Field(...)
    question_ids: List[str] = Field(default_factory=list)  # Store thread IDs
    unit_id: Optional[str] = Field(default=None)  # Make unit_id optional
    transaction_ids: List[str] = Field(default_factory=list)  # Store related transaction IDs
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Store additional metadata
