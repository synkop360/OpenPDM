"""Runtime settings for the OpenPDM backend."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="OPENPDM_", env_file=".env", extra="ignore")

    env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://openpdm:openpdm@localhost:5432/openpdm"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_bucket: str = "openpdm-blobs"
    s3_access_key: str = "openpdm"
    s3_secret_key: str = "openpdm-secret"
    blob_local_root: str = ".openpdm-data/blobs"
    plugin_package_root: str = ".openpdm-data/plugins"
    plugin_runtime_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    plugin_runtime_fuel: int = Field(default=1_000_000, gt=0, le=100_000_000)
    plugin_runtime_memory_bytes: int = Field(default=64 * 1024 * 1024, gt=0, le=512 * 1024 * 1024)
    audit_graph_queries: bool = False
    api_cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]
