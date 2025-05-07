from pydantic import BaseModel


class APIKeyTestRequest(BaseModel):
    apiKey: str
