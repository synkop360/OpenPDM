"""FastAPI application entrypoint for the OpenPDM modular monolith."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from openpdm.api.core import application_lifespan
from openpdm.api.core import router as core_router
from openpdm.infrastructure.database import initialize_database
from openpdm.infrastructure.settings import Settings


def create_app() -> FastAPI:
    """Create the OpenPDM API application."""
    initialize_database()
    settings = Settings()
    app = FastAPI(
        title="OpenPDM",
        summary="Open-source Engineering Collaboration Platform",
        version="0.0.0",
        lifespan=application_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(core_router)
    return app


app = create_app()
