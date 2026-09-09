# bahn-api Project Memory

## Purpose

`bahn-api` is a small Flask application that displays live Deutsche Bahn S-Bahn departures from Zorneding in a compact HTML table for a Home Assistant dashboard.

## Active modules

- `trains.py`: Flask routes, station constants, Bahn URL, lock-protected lazy `BahnBrowser` initialization called from `update()`, and Waitress startup on direct execution.
- `bahn_browser.py`: queue-based handoff from Flask threads to one synchronous Playwright/Chrome worker thread.
- `departures.py`: transforms Bahn `entries` into departure tuples and JSON grouped by direction.
- `templates/trains.html`: frontend table and 15-second visible-tab polling loop.
- `mylog.py`: Loguru stdout configuration.

`station.py`, `transportapi.py`, `bahnapi_DEPRECATED.py`, and `deprecated/` contain older implementations and experiments. The active path does not import them.

## Request and response flow

1. `/` renders `templates/trains.html`.
2. JavaScript calls `/update` immediately and every 15 seconds while visible.
3. `trains.flask_update` invokes `trains.update`.
4. `trains.update` sends the fixed URL `https://www.bahn.de/web/api/reiseloesung/abfahrten?ortExtId=8006671&verkehrsMittel[]=SBAHN` to `BahnBrowser`.
5. The worker launches Chrome with Playwright `channel="chrome"`, calls `page.goto`, and returns parsed JSON on HTTP 200 or an error dictionary otherwise.
6. `departures.process_departures` filters entries whose `verkehrmittel.produktGattung` is `SBAHN`, fills missing `ezZeit`, calculates delay and minutes remaining, sorts by minutes, limits to 20, and groups `Ebersberg(Oberbay)` and `Grafing Bahnhof` eastward.
7. Flask returns JSON with stable keys: `timestamp`, `direction1_title`, `direction2_title`, `trains_east`, and `trains_west`.

## Concurrency

Waitress handles requests in multiple threads. Playwright's synchronous API is isolated in `BahnBrowser._worker`; request threads communicate with it through `queue.Queue`, and `trains.init()` serializes browser creation with `threading.Lock`. Changes must not share a Playwright page across Flask threads.

## Deployment at this revision

Production uses one baked image built from the `Dockerfile`: Ubuntu 24.04 (amd64), Google Chrome from Google's apt repository (required for the Playwright `channel="chrome"` launch), Python dependencies in `/opt/venv` on `PATH`, and application code copied last into `/timetable`. Waitress serves on container port 8080 through `waitress-serve trains:app`. The default `docker-compose.yml` builds this image as `bahn-api:latest`, publishes host port 5123 to container port 8080, sets `restart: unless-stopped` and `TZ=Europe/Berlin`, and healthchecks `/` with curl. Code updates are `docker compose up -d --build`; `docker compose restart` reuses the existing image and is not a code update.

`docker-compose.dev.yml` is a development override (`docker compose -f docker-compose.yml -f docker-compose.dev.yml`): it bind-mounts the source over `/timetable`, runs `python3 trains.py` on container port 5123, and disables the healthcheck. It must never be used in production. `.dockerignore` excludes `venv/`, `.git/`, tests, docs, and legacy code from the build context. `execute.sh` is retired to `deprecated/`. The venv is baked at `/opt/venv` rather than `/timetable/venv` so the development bind mount cannot shadow it with the host virtual environment.

## Known issues

- The runtime requires Google Chrome; the production image installs `google-chrome-stable`, and the Chrome apt repository is not version pinned, so Chrome upgrades arrive with image rebuilds.
- `transportapi.py` still references Playwright's nonexistent `response.status_code` on non-200 responses, but it is legacy code.
- The image runs as root and `requirements.txt` remains unpinned; both are out of scope for the current migration.

## Agent operating rules

Every shell command must be prefixed with `rtk` before the command is run. Serena should be initialized and onboarded before code work, and symbol navigation/editing should use Serena when available. Python commands must run inside the project virtual environment; use `rtk ./venv/bin/python ...` or manage environments with `rtk uv ...`.
