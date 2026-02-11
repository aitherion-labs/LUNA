from fastapi import APIRouter, BackgroundTasks

from config.settings import settings
from schemas.requests import ChatRequest
from schemas.responses import AckResponse, ChatTextResponse
from services.agent_service import process_agent_request, process_agent_request_async

router = APIRouter()


@router.get("/agentic-api/health", tags=["Health"])
async def health():
    return {"status": "ok"}


@router.post("/agentic-api/agent", response_model=AckResponse)
def handle_request(request: ChatRequest, background_tasks: BackgroundTasks):
    """Schedules agent processing in background and returns immediately."""
    background_tasks.add_task(
        process_agent_request,
        chat_id=request.chat_id,
        input_text=request.input,
        model_id=settings.model_id,
    )
    return AckResponse(
        status="received",
        message="Request received. Processing will be done in the background.",
    )


@router.post("/agentic-api/chat", response_model=ChatTextResponse)
async def handle_chat(request: ChatRequest):
    """Processes chat and returns the text output, without blocking the event loop."""
    response = await process_agent_request_async(
        request.chat_id, request.input, settings.model_id
    )
    return ChatTextResponse(text=response)
