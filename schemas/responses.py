from pydantic import BaseModel


class AckResponse(BaseModel):
    status: str
    message: str


class ChatTextResponse(BaseModel):
    text: str | None = None
