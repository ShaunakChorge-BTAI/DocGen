"""
DBAnalyser REST API — API-key authentication middleware.

The API key is set via:
  analysis_config.yaml  →  api.api_key: "mysecret"
  OR environment variable DBANALYSER_API_API_KEY=mysecret

If no key is configured the API runs open (suitable for localhost / internal use).
Pass the key in requests as:
  Header:   X-API-Key: mysecret
  OR query: ?api_key=mysecret
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery

_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)
_query_scheme  = APIKeyQuery(name="api_key",    auto_error=False)

_CONFIGURED_KEY: Optional[str] = None   # set by init_auth()


def init_auth(key: Optional[str]) -> None:
    """Call once at startup with the key from config."""
    global _CONFIGURED_KEY
    _CONFIGURED_KEY = key or os.getenv("DBANALYSER_API_API_KEY") or None


async def require_api_key(
    header_key: Optional[str] = Security(_header_scheme),
    query_key:  Optional[str] = Security(_query_scheme),
) -> None:
    """FastAPI dependency — raises 401 if the key is wrong."""
    if _CONFIGURED_KEY is None:
        # No key configured → open access (localhost/internal)
        return
    provided = header_key or query_key
    if provided != _CONFIGURED_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. "
                   "Pass X-API-Key header or ?api_key= query parameter.",
        )


# Convenience alias for use in route decorators
AuthDep = Depends(require_api_key)
