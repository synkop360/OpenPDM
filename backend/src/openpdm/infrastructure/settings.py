"""Runtime settings for the OpenPDM backend."""

from __future__ import annotations

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
