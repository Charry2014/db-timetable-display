# Agent Development Guide

## Mandatory tool workflow

- Every shell command must be prefixed with `rtk`. Use `rtk git status`, `rtk ./venv/bin/python -m unittest discover -s tests -p "test_*.py"`, and `rtk docker compose config`.
- Before code work, initialize Serena and complete project onboarding when those tools are available.
- Use Serena for symbol navigation and edits. Use file tools only for non-symbol content, documentation, configuration, or when Serena cannot perform the operation.
- Do not commit, reset, push, or otherwise rewrite Git history unless the user explicitly asks.
- Do not add credentials, API keys, or private data.

## Project purpose

This project displays live Deutsche Bahn S-Bahn departures from Zorneding, Germany, for a Home Assistant dashboard card. It serves an HTML timetable and a JSON update endpoint.

## Active runtime architecture

- `trains.py` creates the Flask application, defines station `Zorneding` (`8006671`), builds the Bahn API URL, initializes `BahnBrowser` lazily through a lock-protected `init()` called from `update()`, and starts Waitress on `0.0.0.0:5123` when executed directly. The lazy init keeps WSGI imports such as `waitress-serve trains:app` safe.
- `bahn_browser.py` owns the synchronous Playwright browser in a dedicated daemon thread. Flask request threads place URLs on a queue and wait for the result.
- `departures.py` filters `SBAHN` entries, fills missing actual times, calculates minutes and delay, sorts departures, limits results to 20, and partitions destinations into east and west groups.
- `templates/trains.html` renders the table and polls `/update` every 15 seconds while visible.
- `mylog.py` configures Loguru to write debug-level logs to stdout.
- `station.py`, `transportapi.py`, `bahnapi_DEPRECATED.py`, and files under `deprecated/` are legacy paths. Do not use them for new runtime code.

## Runtime data flow

1. The browser loads `/` and receives `templates/trains.html`.
2. The page requests `/update`.
3. `trains.flask_update` calls `trains.update`.
4. `trains.update` requests the fixed Bahn URL through `BahnBrowser`.
5. The Playwright worker calls `page.goto`, parses successful JSON, or returns an `error` and `body` dictionary.
6. `process_departures` serializes the response for the frontend.

Keep the frontend keys `timestamp`, `direction1_title`, `direction2_title`, `trains_east`, and `trains_west` stable.

## Docker deployment

- Production (`docker-compose.yml`) builds a baked image (`bahn-api:latest`) from the `Dockerfile`: Ubuntu 24.04, Google Chrome (required by `bahn_browser.py`'s `channel="chrome"` launch), Python dependencies in `/opt/venv` on `PATH`, and application code in `/timetable`. Waitress serves on container port 8080 via `waitress-serve trains:app`; Compose publishes host `5123:8080`, sets `restart: unless-stopped` and `TZ=Europe/Berlin`, and runs an HTTP healthcheck against `/`.
- Code updates on the server are `docker compose up -d --build`, not `docker compose restart`, which reuses the existing image. The `COPY . .` layer is last, so code-only changes reuse the cached apt and pip layers.
- Development (`docker-compose.dev.yml`) is an override for `docker compose -f docker-compose.yml -f docker-compose.dev.yml`: it bind-mounts the source over `/timetable`, runs `python3 trains.py` on container port 5123, and disables the healthcheck. Never use it in production; the bind mount would shadow the baked image.
- `.dockerignore` keeps `venv/`, `.git/`, tests, docs, and legacy code out of the build context.
- `execute.sh` is retired to `deprecated/` and must not be referenced by any active Compose configuration.
- The venv is deliberately baked at `/opt/venv`, not `/timetable/venv`, so the development bind mount cannot shadow it with the host's virtual environment.

## Development and validation

Use the existing virtual environment for Python commands:

```sh
rtk ./venv/bin/python -m unittest discover -s tests -p "test_*.py"
rtk python3 trains.py
rtk docker compose config
rtk docker compose -f docker-compose.yml -f docker-compose.dev.yml config
rtk docker compose up -d --build
```

There is no configured lint or type-check command. Tests should mock the external Bahn API and browser rather than requiring live network access.

## Code guidelines

- Keep Playwright confined to `BahnBrowser`'s worker thread.
- Preserve the response shape consumed by the JavaScript template.
- Preserve Europe/Berlin timezone behavior from the container `TZ` setting.
- Avoid changing the hard-coded station and direction behavior unless tests and documentation are updated together.
- Avoid adding comments unless they explain a non-obvious behavior and are requested or necessary.
