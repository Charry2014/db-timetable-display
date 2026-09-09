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

- `trains.py` creates the Flask application, defines station `Zorneding` (`8006671`), builds the Bahn API URL, initializes `BahnBrowser`, and starts Waitress on `0.0.0.0:5123` when executed directly.
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

## Current Docker setup

The default `docker-compose.yml` is the older runtime: it starts `ubuntu:24.04`, bind-mounts the repository at `/timetable`, and runs `/timetable/execute.sh`. That script installs Python, Chrome, and dependencies at container startup, then runs `trains.py` on port 5123. The standalone `Dockerfile` builds an Ubuntu image and exposes 8080 for Waitress, but its current image does not install Chrome; treat it as a separate, incomplete deployment path until explicitly changed.

Do not assume the later baked-image or Portainer workflow exists in this checkout. Verify the checked-out files before changing deployment behavior.

## Development and validation

Use the existing virtual environment for Python commands:

```sh
rtk ./venv/bin/python -m unittest discover -s tests -p "test_*.py"
rtk python3 trains.py
rtk docker compose config
rtk docker compose up -d
```

There is no configured lint or type-check command. Tests should mock the external Bahn API and browser rather than requiring live network access. The current `tests/test_trains.py` references the removed `trains.station` path and is expected to need maintenance before it passes.

## Code guidelines

- Keep Playwright confined to `BahnBrowser`'s worker thread.
- Preserve the response shape consumed by the JavaScript template.
- Preserve Europe/Berlin timezone behavior from the container `TZ` setting.
- Avoid changing the hard-coded station and direction behavior unless tests and documentation are updated together.
- Avoid adding comments unless they explain a non-obvious behavior and are requested or necessary.
