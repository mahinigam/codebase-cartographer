from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from neo4j.exceptions import AuthError, DriverError

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

    @app.exception_handler(DriverError)
    @app.exception_handler(AuthError)
    async def neo4j_unavailable_handler(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": "Graph database unavailable. Ensure Neo4j is running and configured."
            },
        )

    app.include_router(router, prefix="/api")
    # Unauthenticated liveness: container/uptime probes must keep working
    # even when API_TOKEN is configured.
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
