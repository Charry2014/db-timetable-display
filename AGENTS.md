# Agent Development Guide

## Mandatory tool workflow

- Every shell command must be prefixed with `rtk`. Use `rtk ./venv/bin/python -m unittest discover -s tests -p "test_*.py"` and `rtk docker compose config`.
- Before code work, initialize Serena and complete project onboarding when those tools are available.
- Use Serena for symbol navigation and edits when available. Do not commit, reset, push, or rewrite Git history unless explicitly asked.
- Never add credentials, API keys, or private data.

## Project purpose

This project displays live Deutsche Bahn S-Bahn departures from Zorneding (`8006671`) for a Home Assistant dashboard card. It serves an HTML timetable and a JSON update endpoint.

## Active runtime architecture

- `trains.py` serves Flask routes and delegates updates to `DepartureService`.
- `db_config.py` reads `DB_CLIENT_ID`, `DB_API_KEY`, and optional Timetables settings. Credentials are supplied through `db-env.sh`, never committed or logged.
- `db_client.py` performs authenticated standard-library HTTP requests to DB Timetables `/plan/{eva}/{date}/{hour}` and `/fchg/{eva}`.
- `plan_cache.py` provides plan-hour caching, per-key single-flight, and 30-second changes caching with rate-limit backoff.
- `timetable_merger.py` parses XML and sparsely overlays changes onto planned departures.
- `departure_service.py` expands the Europe/Berlin search window up to 12 hours, filters S-Bahn records, classifies route direction, preserves last-known-good data, and emits the relay-shaped `{"entries": [...]}` contract.
- `departures.py` transforms entries into the stable frontend keys `timestamp`, `direction1_title`, `direction2_title`, `trains_east`, and `trains_west`.
- `templates/trains.html` polls `/update` every 15 seconds while visible.
- `deprecated/bahnrelay.py` and `deprecated/test_bahnrelay.py` are retired rollback artifacts; they are not active code.

## Runtime data flow

1. The browser loads `/` and receives `templates/trains.html`.
2. The page requests `/update` only while visible.
3. `trains.flask_update` calls `trains.update`.
4. `DepartureService` fetches cached changes and required plan hours from the authenticated DB API.
5. The merger joins exact stop IDs, overlays sparse changes, filters and classifies departures, and maps them to relay-shaped entries.
6. `process_departures` serializes the unchanged frontend payload.

## Docker deployment

Production builds the baked image with the application in `/timetable` and Waitress on container port 8080, published as host port 5123. The container needs outbound HTTPS access to `apis.deutschebahn.com`; it no longer depends on the Mac Mini LAN relay. Before Compose commands, source credentials with `set -a && source db-env.sh && set +a`. Code updates use `docker compose up -d --build`, not `docker compose restart`.

Development uses `docker compose -f docker-compose.yml -f docker-compose.dev.yml`; it bind-mounts the source, runs `python3 trains.py` on port 5123, and requires the DB variables in the environment. `.dockerignore` excludes credentials, tests, docs, relay code, and legacy code.

## Development and validation

```sh
rtk ./venv/bin/python -m unittest discover -s tests -p "test_*.py"
rtk docker compose config
rtk docker compose -f docker-compose.yml -f docker-compose.dev.yml config
```

There is no configured lint or type-check command. Tests mock the external DB API and use XML fixtures rather than live network access.

## Code guidelines

- Preserve the relay-shaped entries contract and frontend response keys.
- Preserve Europe/Berlin wall-clock handling.
- Never log credentials or authenticated request headers.
- Avoid adding comments unless requested or necessary for non-obvious behavior.
