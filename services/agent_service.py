import asyncio
import logging
import random
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from functools import partial
from typing import Optional

from agents.agent import default_agent
from config.settings import settings

logger = logging.getLogger(__name__)

# A small threadpool for blocking agent calls (boto3/LLM libs are sync)
_executor: Optional[ThreadPoolExecutor] = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-worker")
    return _executor


def shutdown_executor(wait: bool = True):
    """Gracefully shutdown the internal ThreadPoolExecutor."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=wait, cancel_futures=True)
        _executor = None


def _extract_final_text(agent_response) -> str:
    final_response_text = ""
    if agent_response and hasattr(agent_response, "message"):
        message_dict = agent_response.message
        if "content" in message_dict:
            content_list = message_dict["content"]
            for block in content_list:
                if "text" in block:
                    final_response_text = block["text"]
                    break
    if not final_response_text:
        raise ValueError("Could not extract 'message.content[0].text' from response.")
    return final_response_text


def _call_agent_blocking(chat_id: str, input_text: str, model_id: str) -> str:
    agent = default_agent(chat_id, model_id)
    agent_response = agent(input_text)
    return _extract_final_text(agent_response)


def _compute_backoff_delay(attempt: int) -> float:
    base = settings.agent_retry_backoff_base_sec
    maxb = settings.agent_retry_backoff_max_sec
    # exponential backoff with jitter
    delay = min(maxb, base * (2**attempt))
    jitter = random.uniform(0, delay * 0.2)
    return delay + jitter


def process_agent_request(chat_id: str, input_text: str, model_id: str | None):
    """
    Synchronous processing with retries and timeout. Suitable for BackgroundTasks.
    """
    if not model_id:
        logger.error(
            "MODEL_ID is not configured. Set env var MODEL_ID or config settings."
        )
        return None

    logger.info(f"Starting processing for chat_id={chat_id}")

    max_retries = max(0, settings.agent_max_retries)
    timeout_s = max(1.0, settings.agent_call_timeout_sec)

    last_exc: Optional[Exception] = None
    for attempt in range(0, max_retries + 1):
        try:
            executor = _get_executor()
            fut = executor.submit(_call_agent_blocking, chat_id, input_text, model_id)
            result = fut.result(timeout=timeout_s)
            logger.info(f"Processing complete for chat_id={chat_id}")
            return result
        except FuturesTimeout as e:
            last_exc = e
            logger.warning(
                f"Agent call timed out after {timeout_s}s (attempt {attempt+1}/{max_retries+1}) for chat_id={chat_id}"
            )
        except Exception as e:
            last_exc = e
            logger.warning(
                f"Agent call failed (attempt {attempt+1}/{max_retries+1}) for chat_id={chat_id}: {e}",
                exc_info=True,
            )
        if attempt < max_retries:
            delay = _compute_backoff_delay(attempt)
            try:
                # blocking sleep here is fine in background thread context
                import time

                time.sleep(delay)
            except Exception:
                pass

    logger.error(f"Agent processing failed for chat_id={chat_id}: {last_exc}")
    return None


async def process_agent_request_async(
    chat_id: str, input_text: str, model_id: str | None
):
    """
    Async processing that offloads blocking work to a threadpool, with retries and timeout.
    Designed for use in async routes to avoid blocking the event loop.
    """
    if not model_id:
        logger.error(
            "MODEL_ID is not configured. Set env var MODEL_ID or config settings."
        )
        return None

    logger.info(f"Starting async processing for chat_id={chat_id}")

    max_retries = max(0, settings.agent_max_retries)
    timeout_s = max(1.0, settings.agent_call_timeout_sec)

    loop = asyncio.get_running_loop()
    last_exc: Optional[Exception] = None

    for attempt in range(0, max_retries + 1):
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(
                    _get_executor(),
                    partial(_call_agent_blocking, chat_id, input_text, model_id),
                ),
                timeout=timeout_s,
            )
            logger.info(f"Async processing complete for chat_id={chat_id}")
            return result
        except asyncio.TimeoutError as e:
            last_exc = e
            logger.warning(
                f"Agent call timed out after {timeout_s}s (attempt {attempt+1}/{max_retries+1}) for chat_id={chat_id}"
            )
        except Exception as e:
            last_exc = e
            logger.warning(
                f"Agent call failed (attempt {attempt+1}/{max_retries+1}) for chat_id={chat_id}: {e}",
                exc_info=True,
            )
        if attempt < max_retries:
            delay = _compute_backoff_delay(attempt)
            await asyncio.sleep(delay)

    logger.error(f"Async agent processing failed for chat_id={chat_id}: {last_exc}")
    return None
