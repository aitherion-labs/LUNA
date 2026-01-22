import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Simple middleware to ensure every request has an x-request-id.

    - If client provides x-request-id, it is propagated to the response.
    - Otherwise, a new UUID4 is generated and added to the response headers.
    """

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response
