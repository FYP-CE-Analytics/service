
from odmantic import Field, Model


class QuestionClusterModel(Model):
    unit_id: int = Field(default=None)
    summarized_question: str = Field(default=None)
    answer: str = Field(default=None)
    related_question_ids: list[id] = Field(default_factory=list)
    related_quesetions: list[str] = Field(default_factory=list)
