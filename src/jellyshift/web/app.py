from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from jellyshift.config import Config
from jellyshift.web.models import AppState
from jellyshift.web.routes import api, pages


def _package_dir() -> Path:
    return Path(__file__).resolve().parent


def create_app(config_path: Path, *, host: str | None = None, port: int | None = None) -> FastAPI:
    config = Config.load(config_path)
    if host is not None:
        config.web.host = host
    if port is not None:
        config.web.port = port

    app = FastAPI(title="JellyShift", version="0.1.0")
    state = AppState(config_path=config_path.resolve(), config=config)
    app.state.jellyshift = state

    templates = Jinja2Templates(directory=str(_package_dir() / "templates"))
    app.state.templates = templates

    static_dir = _package_dir() / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(pages.router)
    app.include_router(api.router, prefix="/api")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
