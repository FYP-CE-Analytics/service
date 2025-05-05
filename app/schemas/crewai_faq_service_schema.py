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
    start_date: str = Field(
        ...,
        title="Start Date",
        description="The start date for the analysis.",
        example="2023-01-01"
    )
    end_date: str = Field(
        ...,
        title="End Date",
        description="The end date for the analysis.",
        example="2023-12-31"
    )

    assessment: str = Field(
        default="",
        title="Assessment",
        description="The assessment of the unit.",
        example="This unit provides a comprehensive overview of CrewAI."

    )
