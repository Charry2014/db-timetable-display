# bahn-api

This Flask application displays live Deutsche Bahn S-Bahn departures from Zorneding (`8006671`) for a Home Assistant dashboard.

## Architecture

The application uses DB's authenticated Timetables API directly over outbound HTTPS. `DepartureService` fetches the planned `/plan/{eva}/{date}/{hour}` feeds and sparse real-time `/fchg/{eva}` feed, overlays changes by stop ID, expands the search window as needed, and emits the existing relay-shaped `{"entries": [...]}` contract. `departures.py`, the routes, template, and visible-tab polling remain unchanged.

The API allows 60 calls per minute. Plan hours are cached, changes are cached for 30 seconds, and concurrent refreshes use single-flight locks. Temporary upstream failures serve the last successful response; first boot returns the established error row.

## Credentials

Create an application in the DB API Marketplace, subscribe it to Timetables, and copy the example:

```sh
cp db-env.example.sh db-env.sh
```

Set `DB_CLIENT_ID` and `DB_API_KEY` in the untracked file. Optional settings are listed there. Never commit or log credential values.

## Docker

Production listens on host port 5123 and container port 8080. The container needs only outbound HTTPS access to `apis.deutschebahn.com`.

```sh
set -a && source db-env.sh && set +a
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 timetable
curl -s http://localhost:5123/update
```

Use `docker compose restart` only to restart the existing image; source changes require `up -d --build`. Development uses:

```sh
set -a && source db-env.sh && set +a
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

The former Mac Mini relay and its test are retained under `deprecated/` as retired rollback artifacts and are not used by the application.

## Testing

```sh
./venv/bin/python -m unittest discover -s tests -p "test_*.py"
```
