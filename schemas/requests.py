from pydantic import BaseModel


class ChatRequest(BaseModel):
    input: str
    chat_id: str
