"""FastAPI application entrypoint for the OpenPDM modular monolith."""

from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from openpdm.api.core import application_lifespan
from openpdm.api.core import router as core_router
from openpdm.infrastructure.database import initialize_database
from openpdm.infrastructure.settings import Settings
from openpdm.platform_core.modules.services import reset_request_id, set_request_id


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

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next: object) -> Response:
        request_id = request.headers.get("X-Request-Id") or str(uuid4())
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers["X-Request-Id"] = request_id
        return response

    app.include_router(core_router)
    return app


app = create_app()
