"""
DBAnalyser — FastAPI REST Application
======================================
Start with:
    dbanalyser api                          (via CLI)
    uvicorn dbanalyser.api.main:app --reload (direct)

Swagger UI:  http://localhost:8000/docs
ReDoc:       http://localhost:8000/redoc
OpenAPI JSON:http://localhost:8000/openapi.json
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dbanalyser.api.auth          import init_auth
from dbanalyser.api.routes        import databases, findings, reports, runs, trend
from dbanalyser.api.routes        import auth as auth_routes
from dbanalyser.api.routes        import schema as schema_routes
from dbanalyser.api.routes        import ai as ai_routes
from dbanalyser.api.routes        import audit as audit_routes
from dbanalyser.api.routes        import pipeline as pipeline_routes
from dbanalyser.api.routes        import schedules as schedules_routes
from dbanalyser.api.routes        import metadata as metadata_routes
from dbanalyser.api.routes        import live_metrics as live_metrics_routes

# ── Global config reference (set by start_api) ────────────────────────────────
_cfg = None


def _get_cfg():
    if _cfg is None:
        from dbanalyser.config import load_config
        return load_config()
    return _cfg


# ── Startup / shutdown ────────────────────────────────────────────────────────

@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Initialise DB pool and auth on startup; clean up on shutdown."""
    import logging
    _log = logging.getLogger("dbanalyser.api")
    cfg = _get_cfg()
    try:
        from dbanalyser.db.connection import init_pool
        init_pool(cfg.postgres)
        _log.info("PostgreSQL pool initialised successfully.")
    except Exception as exc:
        _log.error(
            "PostgreSQL pool init FAILED at startup: %s\n"
            "  → Persistence endpoints will return 500 until the pool is available.\n"
            "  → Check postgres.host / port / dbname in analysis_config.yaml.",
            exc,
        )
    yield
    try:
        from dbanalyser.db.connection import close_pool
        close_pool()
    except Exception:
        pass


# ── App factory ───────────────────────────────────────────────────────────────

def create_app(config_path: Optional[str] = None, api_key: Optional[str] = None) -> FastAPI:
    global _cfg
    if config_path:
        from dbanalyser.config import load_config
        _cfg = load_config(config_path)

    # Auth key: prefer explicit param → config → env var
    key = api_key
    if key is None and _cfg is not None:
        key = getattr(getattr(_cfg, "api", None), "api_key", None)
    init_auth(key)

    app = FastAPI(
        title       = "DBAnalyser REST API",
        description = (
            "Enterprise SQL Server code-quality & performance analyser.\n\n"
            "**Authentication**: Pass `X-API-Key` header or `?api_key=` query param.\n"
            "If no key is configured the API is open (suitable for local use)."
        ),
        version     = "2.0.0",
        lifespan    = _lifespan,
        docs_url    = "/docs",
        redoc_url   = "/redoc",
    )

    # CORS — allow all origins for internal/local use
    app.add_middleware(
        CORSMiddleware,
        allow_origins     = ["*"],
        allow_credentials = True,
        allow_methods     = ["*"],
        allow_headers     = ["*"],
    )

    # ── Include routers ──────────────────────────────────────────────────────
    app.include_router(databases.router)
    app.include_router(runs.router)
    app.include_router(findings.router)
    app.include_router(trend.router)
    app.include_router(reports.router)
    app.include_router(auth_routes.router)
    app.include_router(schema_routes.router)
    app.include_router(ai_routes.router)
    app.include_router(audit_routes.router)
    app.include_router(pipeline_routes.router)
    app.include_router(schedules_routes.router)
    app.include_router(metadata_routes.router)
    app.include_router(live_metrics_routes.router)

    # ── Health endpoint (no auth) ────────────────────────────────────────────
    @app.get("/health", tags=["System"])
    def health_check():
        return {"status": "ok", "service": "DBAnalyser API", "version": "2.0.0"}

    @app.get("/", tags=["System"])
    def root():
        return {
            "service": "DBAnalyser REST API",
            "docs":    "/docs",
            "health":  "/health",
        }

    return app


# ── Default app instance (used by uvicorn directly) ──────────────────────────
app = create_app()


# ── CLI entry via `dbanalyser api` ────────────────────────────────────────────

def start_api(
        config_path: str = "analysis_config.yaml",
        host:        str = "0.0.0.0",
        port:        int = 8000,
        reload:      bool= False,
        api_key:     Optional[str] = None,
) -> None:
    """Start the API server with uvicorn."""
    import uvicorn  # type: ignore

    global _cfg
    from dbanalyser.config import load_config
    _cfg = load_config(config_path)

    key = api_key or getattr(getattr(_cfg, "api", None), "api_key", None)
    init_auth(key)

    uvicorn.run(
        "dbanalyser.api.main:app",
        host   = host,
        port   = port,
        reload = reload,
    )
