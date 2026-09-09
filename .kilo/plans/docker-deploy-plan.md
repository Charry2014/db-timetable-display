# Plan: Faster, cleaner Docker deployment for bahn-api

## Goal

Replace the current startup-installer container with one reproducible Docker image that contains system dependencies, Google Chrome, and Python dependencies at build time. Make production code updates a short, repeatable rebuild-and-redeploy operation on the Proxmox LXC, while providing an explicit development override for fast iteration.

The operator should be able to update production with:

```sh
rtk git pull && rtk docker compose up -d --build
```

The documented workflow must not depend on installing packages, downloading Chrome, or mounting a second repository directory while the container starts.

## Current-state diagnosis

- `docker-compose.yml` starts `ubuntu:24.04`, mounts the repository at `/timetable`, and runs `execute.sh`.
- `execute.sh` runs `apt update/upgrade`, installs Python and Google Chrome, creates a virtual environment, installs requirements, and starts `trains.py` on every container start. This makes restart time network-dependent and produces noisy logs.
- `Dockerfile` is a separate deployment path. It installs Python but not Google Chrome, even though `bahn_browser.py` launches `channel="chrome"`; the image therefore cannot reliably serve `/update`.
- `Dockerfile` copies the whole repository before installing `requirements.txt`, so a code-only change invalidates the dependency layer.
- The Dockerfile command uses a literal `${VENV}` in JSON exec form and does not explicitly include the port in the Waitress listen address.
- `trains.py` only calls `init()` inside its `__main__` block. A production command such as `waitress-serve trains:app` imports the Flask app without executing that block, leaving `bahn_browser` unset when `/update` is called. The implementation must initialize the browser for both direct execution and WSGI import.
- There is no `.dockerignore`, restart policy, or healthcheck.
- Port history is inconsistent. The target convention is host port 5123 mapped to production container port 8080; direct development execution continues to use port 5123 inside the container.

## Target design

Use one Dockerfile and two Compose configurations:

1. **Production default**: bake system packages, Chrome, Python dependencies, and application code into an image. The application layer is last so code-only changes reuse apt and pip layers. Waitress listens on container port 8080. Compose publishes host port 5123 to container port 8080.
2. **Development override**: opt-in bind mount of the working tree over `/timetable`, direct execution of `trains.py`, and host port 5123 mapped to container port 5123. This is for quick iteration only and must never be loaded automatically in production.

Do not use a registry, watchtower, host-level Python service, or Proxmox-specific application process for this migration. Docker remains the runtime inside the existing LXC.

## Planned file changes

### 1. Add `.dockerignore`

Exclude Git metadata, editor state, Serena state, the local virtual environment, bytecode, tests, deprecated code, macOS files, and documentation from the build context. Keep runtime source, templates, static assets, `requirements.txt`, and the Docker files needed for the build.

### 2. Rewrite `Dockerfile`

Use Ubuntu 24.04 with `DEBIAN_FRONTEND=noninteractive` and `TZ=Europe/Berlin`. In one cached system layer:

- install `curl`, `gnupg`, `ca-certificates`, `python3`, `python3-pip`, and `python3-venv`;
- add the Google signing key and apt repository;
- install `google-chrome-stable`;
- remove apt lists.

Create `/timetable/venv`, put its `bin` directory on `PATH`, copy only `requirements.txt`, install Python dependencies without pip cache, then copy application code. Expose 8080 and run:

```dockerfile
CMD ["waitress-serve", "--listen=0.0.0.0:8080", "trains:app"]
```

Do not run `apt upgrade` during every container startup. Base image and package updates happen during an explicit image rebuild.

### 3. Rewrite production `docker-compose.yml`

Use:

- `build: .`;
- `image: bahn-api:latest`;
- `container_name: timetable_app`;
- `restart: unless-stopped`;
- `TZ=Europe/Berlin`;
- `5123:8080`;
- an HTTP healthcheck against `127.0.0.1:8080/` with a start period long enough for Chrome and Flask to initialize.

Remove the repository bind mount, `working_dir`, and `execute.sh` command from production.

### 4. Add `docker-compose.dev.yml`

Override only what development needs:

- bind mount `.:/timetable`;
- replace the port mapping with `5123:5123`;
- run `python3 trains.py`;
- disable the production healthcheck because the direct development process uses a different port.

Use the Compose `!override` tag for the ports list if required by the installed Compose version so the production `5123:8080` mapping is replaced rather than merged with the development mapping.

### 5. Retire `execute.sh`

Move it to `deprecated/execute.sh` for historical reference, or remove it if repository history is sufficient. No active Compose configuration may reference it.

### 6. Make WSGI startup safe

Update `trains.py` so `update()` ensures the browser is initialized before calling `.get()`. Protect initialization with a lock because Waitress handles requests concurrently. Keep direct `__main__` execution working without creating multiple browser workers.

Add a regression test proving that an imported `trains:app` path initializes `BahnBrowser` before processing an update.

### 7. Maintain error-path behavior

Keep the existing browser response contract (`error` and `body` for failures) and the frontend JSON keys stable. Add or retain tests for HTTP failures and departure error serialization. Do not make live Bahn requests in tests.

### 8. Rewrite `README.md` with human operator instructions

Document both workflows in plain language:

#### Production update on the Proxmox LXC

```sh
rtk git pull
rtk docker compose up -d --build
rtk docker compose ps
rtk docker compose logs --tail=100 timetable
rtk curl -s http://localhost:5123/update
```

Explain that code-only changes normally rebuild only the final `COPY` layer, while changes to `requirements.txt` rebuild the Python dependency layer and changes to the Dockerfile rebuild system layers. Explain that `docker compose restart` is not a code update because it reuses the existing image.

#### Quick development iteration

```sh
rtk docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
rtk docker compose -f docker-compose.yml -f docker-compose.dev.yml restart timetable
```

Explain that the override mounts host code and runs `trains.py` on port 5123, and that it must not be used for production.

#### First migration

Document that the operator should run from the repository root, stop the old startup-installer container, build the new image, start the new Compose service, and verify `docker compose ps`, `/`, and `/update`. Keep the old Ubuntu image until the new service has run successfully for a day; remove it only as optional cleanup.

#### Rollback

Document checking out a known-good commit and rerunning `docker compose up -d --build`. Do not recommend deleting volumes or using destructive Docker cleanup commands as part of normal updates.

### 9. Update `AGENTS.md` and Serena memory

Record the final architecture, port convention, deployment commands, the retired script, Chrome requirement, and the distinction between production and development Compose files. Explicitly preserve the rule that every shell command is prefixed with `rtk`.

## Implementation order

1. Add `.dockerignore`.
2. Rewrite `Dockerfile`.
3. Rewrite production `docker-compose.yml`.
4. Add `docker-compose.dev.yml`.
5. Move or retire `execute.sh`.
6. Fix WSGI-safe browser initialization and add regression coverage.
7. Update README, `AGENTS.md`, and Serena memory.
8. Validate Compose configurations and tests.

## Verification checklist

Run from the repository root:

```sh
rtk docker compose config
rtk docker compose -f docker-compose.yml -f docker-compose.dev.yml config
rtk ./venv/bin/python -m unittest discover -s tests -p "test_*.py"
```

On the Proxmox LXC, after migration:

1. `docker compose up -d --build` completes without startup apt or pip installation logs.
2. `docker compose ps` shows `timetable_app` running and then healthy.
3. Logs show `Chrome ready` from `bahn_browser.py`.
4. `curl -s http://localhost:5123/` returns the timetable HTML.
5. `curl -s http://localhost:5123/update` returns the expected JSON shape.
6. `time docker compose restart` is short because dependencies are already in the image.
7. After a source-only change, `time docker compose up -d --build` reuses apt and pip layers.
8. The development override exposes only port 5123 and serves source changes after a process restart.
9. Home Assistant continues using the host port 5123.

A local Docker build may be unavailable; if so, complete the configuration and unit-test checks locally and run the image build and runtime checks on the Proxmox LXC.

## Risks and decisions

- Google Chrome upgrades happen on image rebuild because the apt repository is not version-pinned. Test rebuilt images before production rollout.
- The image remains root-based and requirements remain unpinned; these are out of scope for this speed-focused migration.
- The server's outbound IP and Bahn anti-automation behavior are external to Docker. A successful Chrome launch does not guarantee Bahn will accept the request; retain response-body logging for diagnosing upstream 403 responses.
- The production image is intentionally baked while the development override is intentionally bind-mounted. Mixing these modes would make deployed code ambiguous.
