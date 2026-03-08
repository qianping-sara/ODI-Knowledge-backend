from __future__ import annotations

import logging

from fastapi import FastAPI

from api.routes import completions, messages, sessions
from core.config import get_app_name
from core.database import init_engine
from models.entities import Base


def _configure_logging() -> None:
    """Ensure agent and PageIndex logs are visible (INFO level)."""
    fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    for name in ("agent", "agent.research", "agent.research.pageindex_cache"):
        log = logging.getLogger(name)
        log.setLevel(logging.INFO)
        if not log.handlers:
            h = logging.StreamHandler()
            h.setFormatter(logging.Formatter(fmt))
            log.addHandler(h)
            log.propagate = False  # avoid duplicate when root also has handler


async def _init_db() -> None:
    engine = init_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def create_app() -> FastAPI:
    app = FastAPI(title=get_app_name())

    @app.on_event("startup")
    async def startup() -> None:
        _configure_logging()
        await _init_db()

    app.include_router(sessions.router)
    app.include_router(messages.router)
    app.include_router(completions.router)

    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok"}

    return app


app = create_app()
