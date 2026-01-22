import os
from typing import Callable, Optional, Set

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()


def get_bearer_auth_dependency(
    env_var: str = "API_TOKEN", *, skip_paths: Optional[Set[str]] = None
) -> Callable[[HTTPAuthorizationCredentials], None]:
    """
    Returns a FastAPI dependency that validates an Authorization: Bearer <token>
    header against an environment variable-defined token. This is designed to be
    easily reused across projects with similar structure.

    Options:
      - skip_paths: conjunto de caminhos (ex.: {"/health"}) que devem ser ignorados pela autenticação.

    Usage:
      from fastapi import FastAPI, Depends
      from utils.auth import get_bearer_auth_dependency

      token_auth = get_bearer_auth_dependency()  # default expects API_TOKEN
      app = FastAPI(dependencies=[Depends(token_auth)])
    """
    security = HTTPBearer(auto_error=False)

    expected_token: Optional[str] = os.environ.get(env_var)
    skip_paths = skip_paths or set()

    def _dependency(
        request: Request,
        credentials: HTTPAuthorizationCredentials = Depends(security),
    ) -> None:
        # Allow listed paths to bypass auth (useful for /health and readiness probes)
        if request.url.path in skip_paths:
            return None

        # If token not configured, fail closed with clear 500 to avoid insecure default
        if not expected_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Server misconfiguration: {env_var} is not set.",
            )

        # If Authorization header missing or malformed
        if credentials is None or credentials.scheme.lower() != "bearer":
            # Challenge header hints proper auth method
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Validate token securely (constant-time comparison isn't critical here due
        # to single token, but we can still avoid early returns)
        provided = credentials.credentials or ""
        if not _secure_compare(provided, expected_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        # On success, simply return None so request proceeds
        return None

    return _dependency


def _secure_compare(a: str, b: str) -> bool:
    """Time-constant-ish comparison to avoid trivial timing differences."""
    if len(a) != len(b):
        # still iterate to keep timing similar
        result = 0
        for i, ch in enumerate(a):
            result |= ord(ch) ^ ord(b[i % len(b)]) if b else ord(ch)
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0


# Default dependency expecting env var API_TOKEN
# Import and use as: from utils.auth import token_auth
# Then: app = FastAPI(dependencies=[Depends(token_auth)])
# Mantemos compatibilidade: sem pular caminhos.
token_auth = get_bearer_auth_dependency("API_TOKEN")
