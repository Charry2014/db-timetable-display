# bahn-api Project Memory

## Purpose

`bahn-api` is a small Flask application that displays live Deutsche Bahn S-Bahn departures from Zorneding in a compact HTML table for a Home Assistant dashboard.

## Active modules

- `trains.py`: Flask routes, station constants, Bahn URL, `BahnBrowser` initialization, and Waitress startup.
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

Waitress handles requests in multiple threads. Playwright's synchronous API is isolated in `BahnBrowser._worker`; request threads communicate with it through `queue.Queue`. Changes must not share a Playwright page across Flask threads.

## Deployment at this revision

The default Compose file uses `ubuntu:24.04`, mounts the repository at `/timetable`, and executes `/timetable/execute.sh` on container start. `execute.sh` performs apt upgrades and installs Python, Google Chrome, and requirements on every start, then executes `trains.py` on port 5123. The standalone `Dockerfile` creates a virtual environment and runs Waitress on container port 8080, but it currently does not install Chrome and is not equivalent to the Compose path.

`TZ=Europe/Berlin` is part of the runtime assumptions. The host-facing Compose port is 5123 at this revision.

## Known issues

- `trains.py` initializes `bahn_browser` only inside its `__main__` block. Running `waitress-serve trains:app` imports the app without calling `init`, so production startup through the Dockerfile path can leave the browser unset.
- The current error branch in `departures.py` builds a tuple but does not return a serialized response and assigns an unused local variable.
- `transportapi.py` still references Playwright's nonexistent `response.status_code` on non-200 responses, but it is legacy code.
- `tests/test_trains.py` patches `trains.station`, although the active implementation uses `bahn_browser`; the test requires maintenance.
- The runtime assumes Google Chrome is installed because Playwright launches `channel="chrome"`.

## Agent operating rules

Every shell command must be prefixed with `rtk` before the command is run. Serena should be initialized and onboarded before code work, and symbol navigation/editing should use Serena when available. Python commands must run inside the project virtual environment; use `rtk ./venv/bin/python ...` or manage environments with `rtk uv ...`.
