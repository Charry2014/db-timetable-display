# bahn-api Project Memory

## Purpose

`bahn-api` is a small Flask application that displays live Deutsche Bahn S-Bahn departures from Zorneding in a compact HTML table for a Home Assistant dashboard.

## Active modules

- `trains.py`: Flask routes, station constant, departures service URL `http://10.0.0.204:8765/departures`, `fetch_departures()` (stdlib `urllib`, 30s timeout, error/`body` contract), and Waitress startup on direct execution.
- `departures.py`: transforms service `entries` into departure tuples and JSON grouped by direction.
- `templates/trains.html`: frontend table and 15-second visible-tab polling loop.
- `mylog.py`: Loguru stdout configuration.

`deprecated/` contains retired implementations (`bahn_browser.py`, `station.py`, `transportapi.py`, `bahnapi_DEPRECATED.py`, `execute.sh`, experiments). The active path does not import them.

## Request and response flow

1. `/` renders `templates/trains.html`.
2. JavaScript calls `/update` immediately and every 15 seconds while visible.
3. `trains.flask_update` invokes `trains.update`.
4. `trains.update` calls `fetch_departures(url)`, which performs a plain HTTP GET against `http://10.0.0.204:8765/departures` and returns the parsed JSON, or an `error`/`body` dictionary on HTTP or connection failure.
5. `departures.process_departures` filters entries whose `verkehrmittel.produktGattung` is `SBAHN`, fills missing `ezZeit`, calculates delay and minutes remaining, sorts by minutes, limits to 20, and groups `Ebersberg(Oberbay)` and `Grafing Bahnhof` eastward.
6. Flask returns JSON with stable keys: `timestamp`, `direction1_title`, `direction2_title`, `trains_east`, and `trains_west`.

## Concurrency

Waitress handles requests in multiple threads. Each request thread performs an independent blocking HTTP fetch; there is no shared browser state and no worker thread.

## Deployment at this revision

Production uses one baked image built from the `Dockerfile`: Ubuntu 24.04, Python dependencies in `/opt/venv` on `PATH`, and application code copied last into `/timetable`. No browser or Chrome is needed because the data source is a plain HTTP service. Waitress serves on container port 8080 through `waitress-serve trains:app`. The default `docker-compose.yml` builds this image as `bahn-api:latest`, publishes host port 5123 to container port 8080, sets `restart: unless-stopped` and `TZ=Europe/Berlin`, and healthchecks `/` with curl. Code updates are `docker compose up -d --build`; `docker compose restart` reuses the existing image and is not a code update. The container must be able to reach `10.0.0.204:8765`.

`docker-compose.dev.yml` is a development override (`docker compose -f docker-compose.yml -f docker-compose.dev.yml`): it bind-mounts the source over `/timetable`, runs `python3 trains.py` on container port 5123, and disables the healthcheck. It must never be used in production. `.dockerignore` excludes `venv/`, `.git/`, tests, docs, and `deprecated/` from the build context. The venv is baked at `/opt/venv` rather than `/timetable/venv` so the development bind mount cannot shadow it with the host virtual environment.

## Known issues

- `transportapi.py` (now under `deprecated/`) referenced Playwright's nonexistent `response.status_code`; it is legacy code.
- The image runs as root and `requirements.txt` remains unpinned; both are out of scope for the current migration.

## Agent operating rules

Every shell command must be prefixed with `rtk` before the command is run. Serena should be initialized and onboarded before code work, and symbol navigation/editing should use Serena when available. Python commands must run inside the project virtual environment; use `rtk ./venv/bin/python ...` or manage environments with `rtk uv ...`.
