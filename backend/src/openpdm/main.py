"""FastAPI application entrypoint for the OpenPDM modular monolith."""

from fastapi import FastAPI

from openpdm.api.foundation import router as foundation_router


def create_app() -> FastAPI:
    """Create the OpenPDM API application."""
    app = FastAPI(
        title="OpenPDM",
        summary="Open-source Engineering Collaboration Platform",
        version="0.0.0",
    )
    app.include_router(foundation_router)
    return app


app = create_app()
