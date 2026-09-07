# Named launcher deployments

Each `*.env` file here describes one **isolated local Compose stack** for the
OpenPDM launcher: its own Compose project (containers, network and volumes are
namespaced, so nothing collides), its own published host ports, and its own blob
storage target.

Run real work on one deployment and throwaway or test work on another — neither
can reach the other's database or blobs.

Every `*.env` in this directory is git-ignored except `example.env`.

## Create one

Interactive CLI:

```bash
python scripts/start_all.py --new-deployment
```

Or the desktop launcher — `python scripts/start_all.py --gui`, then
**New deployment…**. Both ask for a name and where blob content should live:

| Storage | What it does |
|---|---|
| **bundled** | This deployment's own MinIO container. Fully isolated, no external account. |
| **s3** | An external S3-compatible bucket (OVH, AWS, …). Prompts for endpoint, region, bucket, and keys. |
| **local** | A local filesystem directory or a Docker volume, mounted into the backend. |

The launcher allocates a free, non-overlapping port block — backend, Vite Web
UI, PostgreSQL and MinIO — and writes `deployments/<name>.env`. Each deployment
gets its own Vite port (`OPENPDM_FRONTEND_HOST_PORT`), so several Web UIs can run
at once; `default` keeps `5173`. Ports and any value can be edited by hand
afterwards.

## Run one

```bash
python scripts/start_all.py --deployment <name>
python scripts/start_all.py --list-deployments
python scripts/dev.py compose-up --deployment <name>
```

`default` is the built-in single stack (project `deployment`, ports
18000/5432/9000/9001, `.env.example`). It behaves exactly as before this
directory existed; you never need a file here to use it.
