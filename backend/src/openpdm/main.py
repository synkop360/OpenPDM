"""FastAPI application entrypoint for the OpenPDM modular monolith."""

from fastapi import FastAPI

from openpdm.api.core import application_lifespan
from openpdm.api.core import router as core_router
from openpdm.infrastructure.database import initialize_database


def create_app() -> FastAPI:
    """Create the OpenPDM API application."""
    initialize_database()
    app = FastAPI(
        title="OpenPDM",
        summary="Open-source Engineering Collaboration Platform",
        version="0.0.0",
        lifespan=application_lifespan,
    )
    app.include_router(core_router)
    return app


app = create_app()
