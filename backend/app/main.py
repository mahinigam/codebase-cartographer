from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health_router, router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Codebase Cartographer API",
        description="Structural forensics API for repository graphing and AI-assisted analysis.",
        version="0.1.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )
    app.include_router(router, prefix="/api")
    # Unauthenticated liveness: container/uptime probes must keep working
    # even when API_TOKEN is configured.
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
