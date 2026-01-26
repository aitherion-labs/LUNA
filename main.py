import logging
import warnings
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import router as api_router
from config.settings import settings
from services.agent_service import shutdown_executor
from utils.access_log import AccessLogMiddleware
from utils.auth import get_bearer_auth_dependency
from utils.request_id import RequestIdMiddleware

# Suppress DeprecationWarning originating from strands.experimental.* (third-party).
# Remove when upgrading strands-agents to a version where these events are stable.
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module=r"^strands\.experimental(\.|$)",
)

# -----------------------------------------------------------------------------
# Logging configuration (basic structured format)
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=settings.log_level,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s","logger":"%(name)s"}',
)
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Lifespan (startup/shutdown) using FastAPI lifespan context
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    if not settings.model_id:
        logger.error(
            "MODEL_ID is not configured. Set env var MODEL_ID or config settings."
        )
    logger.info("Application startup complete")
    try:
        yield
    finally:
        # Shutdown
        try:
            shutdown_executor(wait=True)
            logger.info("Background executor shutdown complete")
        except Exception as e:
            logger.warning(f"Error shutting down executor: {e}")
        logger.info("Application shutdown complete")


# -----------------------------------------------------------------------------
# App and security setup
# -----------------------------------------------------------------------------
# Build auth dependency allowing health endpoint without token
_token_auth = get_bearer_auth_dependency("API_TOKEN", skip_paths={"/health"})
app = FastAPI(dependencies=[Depends(_token_auth)], lifespan=lifespan)

# Request-ID middleware
app.add_middleware(RequestIdMiddleware)
# Access log middleware (per-request latency/status)
app.add_middleware(AccessLogMiddleware)

# Optional CORS setup from centralized settings
if settings.cors_allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# -----------------------------------------------------------------------------
# Exception handlers (basic)
# -----------------------------------------------------------------------------
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP {exc.status_code} at {request.url.path}: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error at {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# -----------------------------------------------------------------------------
# Healthcheck (public)
# -----------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok"}


# -----------------------------------------------------------------------------
# Routers
# -----------------------------------------------------------------------------
app.include_router(api_router)


####### Bloco p/ teste local #######
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
