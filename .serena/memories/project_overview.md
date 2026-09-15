# bahn-api Project Memory

## Purpose

`bahn-api` displays live Deutsche Bahn S-Bahn departures from Zorneding in a compact HTML table for Home Assistant.

## Active modules

- `trains.py`: Flask routes and Waitress startup; delegates `/update` to `DepartureService` and preserves the frontend response.
- `db_config.py`: environment configuration and credential validation.
- `db_client.py`: authenticated DB Timetables HTTP client for plan and full-change feeds.
- `plan_cache.py`: plan-hour single-flight cache and 30-second changes cache with backoff.
- `timetable_merger.py`: XML parsing, exact stop-ID joins, sparse overlays, normalization, and route classification.
- `departure_service.py`: adaptive Europe/Berlin window, S-Bahn filtering, six-per-direction selection, last-known-good fallback, and relay-shaped compatibility mapping.
- `departures.py`: transforms `entries` into stable frontend keys.
- `templates/trains.html`: visible-tab polling every 15 seconds.
- `deprecated/bahnrelay.py` and `deprecated/test_bahnrelay.py`: retired relay artifacts; not in the production path.

## Request and response flow

1. `/` renders `templates/trains.html`.
2. JavaScript calls `/update` while visible.
3. `trains.flask_update` invokes `trains.update`.
4. `DepartureService` fetches one cached `fchg` response and the required cached plan hours.
5. `TimetableMerger` overlays sparse changes by exact stop ID and `DepartureService` filters, classifies, sorts, limits, and emits `{"entries": [...]}`.
6. `departures.process_departures` returns stable frontend JSON keys: `timestamp`, `direction1_title`, `direction2_title`, `trains_east`, and `trains_west`.

## Deployment

Production is a baked Ubuntu 24.04 image with Python in `/opt/venv`, Waitress on container port 8080, and host port 5123. It requires outbound HTTPS to `apis.deutschebahn.com`. Credentials are supplied by sourcing the untracked `db-env.sh` before Compose interpolation. The development override bind-mounts the source and runs port 5123. Tests mock DB requests and use XML fixtures; no live network is required.

## Agent operating rules

Every shell command must be prefixed with `rtk`. Serena should be initialized before code work when available, and Python commands run inside the project virtual environment.
