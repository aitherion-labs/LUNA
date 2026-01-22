import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Middleware to emit a single structured access log per request.

    Fields: method, path, status, duration_ms, client_ip, request_id.
    Relies on RequestIdMiddleware to set/propagate x-request-id.
    """

    async def dispatch(self, request: Request, call_next: Callable):
        start = time.perf_counter()
        # Try to get client IP (best-effort; do not trust in zero-trust envs)
        client_ip = request.client.host if request.client else "-"
        rid = request.headers.get("x-request-id")

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            # Use path without query string to reduce log cardinality
            path = request.url.path
            logger.info(
                f"access log | method={request.method} path={path} status={locals().get('status_code', '-') } "
                f"duration_ms={duration_ms} client_ip={client_ip} request_id={rid or '-'}"
            )
