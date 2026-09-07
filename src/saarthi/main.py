from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from saarthi.api.routes import router
from saarthi.config import get_settings
from saarthi.runtime import build_runtime


def create_app() -> FastAPI:
    settings = get_settings()
    runtime = build_runtime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await runtime.initialize()
        app.state.runtime = runtime
        yield
        await runtime.close()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Synthetic, draft-only voice pre-application API.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(router)

    web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if web_dist.exists():
        app.mount("/app", StaticFiles(directory=web_dist, html=True), name="web")

    @app.get("/")
    async def root() -> dict:
        return {
            "service": settings.app_name,
            "docs": "/docs",
            "web": "/app"
            if web_dist.exists()
            else "Run the Vite development server in web/",
            "boundary": "Synthetic reviewable draft only; no lending action exists.",
        }

    return app


app = create_app()


def run_api() -> None:
    settings = get_settings()
    railway_port = os.getenv("PORT")
    uvicorn.run(
        "saarthi.main:app",
        host="0.0.0.0" if railway_port else settings.api_host,
        port=int(railway_port or settings.api_port),
        reload=False,
    )


if __name__ == "__main__":
    run_api()
