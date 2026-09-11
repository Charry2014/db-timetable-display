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

- `trains.py` creates the Flask application, defines station `Zorneding` (`8006671`), fetches departures JSON from the departures relay URL `http://10.0.0.204:8765/departures?station=8006671` via `fetch_departures()` (stdlib `urllib`, 30s timeout), and starts Waitress on `0.0.0.0:5123` when executed directly. No browser or worker thread is involved.
- `macmini/bahnrelay.py` is the puller service that runs on the Mac Mini host (not in Docker). It fetches `https://www.bahn.de/web/api/reiseloesung/abfahrten?ortExtId=<station>&verkehrsMittel%5B%5D=SBAHN` with the macOS native `curl` per requested station, caches each station's response for 15 seconds, and serves `/departures?station=<eva>` (HTTP 400 on a missing or non-numeric station, 502 when the Bahn fetch fails) plus `/health`. The station code comes from the URL; no station is hard-coded in the script.
- `departures.py` filters `SBAHN` entries, fills missing actual times, calculates minutes and delay, sorts departures, limits results to 20, and partitions destinations into east and west groups.
- `templates/trains.html` renders the table and polls `/update` every 15 seconds while visible.
- `mylog.py` configures Loguru to write debug-level logs to stdout.
- Files under `deprecated/` (including `bahn_browser.py`, `station.py`, `transportapi.py`, `execute.sh`, and `bahnapi_DEPRECATED.py`) are retired implementations. Do not use them for new runtime code.

## Runtime data flow

1. The browser loads `/` and receives `templates/trains.html`.
2. The page requests `/update`.
3. `trains.flask_update` calls `trains.update`.
4. `trains.update` fetches the departures relay URL with the station parameter through `fetch_departures`, which returns the parsed JSON on success or an `error` and `body` dictionary otherwise.
5. The relay on the Mac Mini either serves its per-station 15-second cache or fetches bahn.de with native `curl` for the requested station.
6. `process_departures` serializes the response for the frontend.

Keep the frontend keys `timestamp`, `direction1_title`, `direction2_title`, `trains_east`, and `trains_west` stable.

## Docker deployment

- Production (`docker-compose.yml`) builds a baked image (`bahn-api:latest`) from the `Dockerfile`: Ubuntu 24.04, Python dependencies in `/opt/venv` on `PATH`, and application code in `/timetable`. Waitress serves on container port 8080 via `waitress-serve trains:app`; Compose publishes host `5123:8080`, sets `restart: unless-stopped` and `TZ=Europe/Berlin`, and runs an HTTP healthcheck against `/`. The container must be able to reach the departures service at `10.0.0.204:8765`.
- Code updates on the server are `docker compose up -d --build`, not `docker compose restart`, which reuses the existing image. The `COPY . .` layer is last, so code-only changes reuse the cached apt and pip layers.
- Development (`docker-compose.dev.yml`) is an override for `docker compose -f docker-compose.yml -f docker-compose.dev.yml`: it bind-mounts the source over `/timetable`, runs `python3 trains.py` on container port 5123, and disables the healthcheck. Never use it in production; the bind mount would shadow the baked image.
- `.dockerignore` keeps `venv/`, `.git/`, tests, docs, `macmini/`, and legacy code out of the build context.
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

- Keep `fetch_departures` tolerant of upstream failures and preserve the `error`/`body` contract consumed by `process_departures`.
- Preserve the response shape consumed by the JavaScript template.
- Preserve Europe/Berlin timezone behavior from the container `TZ` setting.
- Avoid changing the hard-coded station and direction behavior unless tests and documentation are updated together.
- Avoid adding comments unless they explain a non-obvious behavior and are requested or necessary.
