# OpenPDM Deployment

This document describes the Phase 0 local deployment path.

Phase 0 deployment is for local development and demonstration. It is not a
production hardening guide.

## Services

The local deployment uses Docker Compose:

* `backend`: FastAPI backend skeleton.
* `postgres`: PostgreSQL 18 primary database.
* `minio`: MinIO S3-compatible Blob storage.

PostgreSQL and MinIO are infrastructure dependencies selected by accepted ADRs.
The Platform Core must still depend on application interfaces rather than
provider-specific implementation details.

## Start the Environment

```bash
python scripts/dev.py compose-up
```

Equivalent Docker command:

```bash
docker compose --env-file .env.example -f deployment/compose.yaml up --build
```

## Endpoints

After startup:

* Backend API: `http://localhost:18000`
* Health check: `http://localhost:18000/health`
* OpenAPI documentation: `http://localhost:18000/docs`
* MinIO API: `http://localhost:9000`
* MinIO console: `http://localhost:9001`

## Limitations

Phase 0 does not include:

* production secrets management;
* TLS termination;
* backup and restore procedures;
* database migrations for Platform Core business data;
* authentication or authorization;
* Blob upload and download behavior;
* plugin execution.

Those capabilities belong to later roadmap phases or production deployment
hardening.
