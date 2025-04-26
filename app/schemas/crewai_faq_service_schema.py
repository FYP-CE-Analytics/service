from pydantic import BaseModel, Field


class CrewAIFAQInputSchema(BaseModel):
    """
    Schema for CrewAI FAQ Service
    """
    unit_id: str = Field(
        ...,
        title="Unit ID",
        description="The unique identifier for the unit.",
        example="12345"
    )
    unit_name: str = Field(
        ...,
        title="Unit Name",
        description="The name of the unit.",
        example="Introduction to CrewAI"
    )
    questions: list[dict] = Field(
        ...,
        title="Questions",
        description="List of questions to be answered.",
        example=["What is CrewAI?", "How does it work?"]
    )
    content: str = Field(
        ...,
        title="Content",
        description="The unit contents",

    )

    # assessment: Otional = Field(
