"""Foundation endpoints for Phase 0 validation and demonstrations."""

from fastapi import APIRouter
from pydantic import BaseModel

from openpdm import __version__

router = APIRouter(tags=["Foundation"])


class HealthResponse(BaseModel):
    status: str


class FoundationResponse(BaseModel):
    name: str
    version: str
    phase: str
    architecture: str


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return application health without exposing business capabilities."""
    return HealthResponse(status="ok")


@router.get("/foundation", response_model=FoundationResponse)
def foundation() -> FoundationResponse:
    """Return Phase 0 foundation metadata."""
    return FoundationResponse(
        name="OpenPDM",
        version=__version__,
        phase="Foundation",
        architecture="Modular Monolith",
    )
