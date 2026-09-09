Read the DB timetables through a third party API and make a nice display of the data. This is designed to be displayed in a card on a Home Assistant dashboard.

If you use Deutsche Bahn trains regularly you will be familiar with the importance of having up-to-date departure information ;-)

# Overview

* The project reads departure data from the Bahn web API (`bahn.de/web/api/reiseloesung/abfahrten`)
* A headless Chrome browser driven by `Playwright` fetches the data, so Google Chrome must be installed wherever the app runs
* `Flask` serves the timetable page and the `/update` JSON endpoint
* The page updates with browser polling while the tab is visible
* `Waitress` hosts the site in production
* The production site runs in a Docker container hosted on a Proxmox LXC
* Home Assistant connects to host port 5123; in production this maps to container port 8080
* Development uses a Compose override that runs `trains.py` directly on container port 5123

# Docker

One `Dockerfile`, two Compose files:

* `docker-compose.yml` (production, default) builds an image that contains the system packages, Google Chrome, the Python dependencies, and the application code. Nothing is installed when the container starts, so restarts are fast and independent of the network. Waitress listens on container port 8080 and Compose publishes host port 5123 to it.
* `docker-compose.dev.yml` (development override) bind-mounts the working tree over `/timetable` and runs `trains.py` directly on port 5123. It is for quick iteration only and must never be used in production, because there the mounted code would shadow the baked image.

The application layer is the last layer in the `Dockerfile`, so a code-only change rebuilds just that layer while the apt and pip layers come from cache. Changes to `requirements.txt` rebuild the Python dependency layer, and changes to the `Dockerfile` itself rebuild the system layers including Chrome.

## Updating production

Run these from the repository root on the Proxmox LXC:

1. `git pull`
1. `docker compose up -d --build`
1. `docker compose ps`
1. `docker compose logs --tail=100 timetable`
1. `curl -s http://localhost:5123/update`

Notes:

* `docker compose restart` only restarts the existing container with the existing image. It is **not** a code update. Use `docker compose up -d --build` whenever source code or `requirements.txt` changed.
* A code-only rebuild normally finishes in seconds because only the final `COPY` layer is rebuilt.
* System package and Chrome updates are picked up on the next image rebuild, since the apt repository is not version pinned. Rebuilt images should be spot-checked before going live.

## First migration from the old setup

The previous Compose file started a plain `ubuntu:24.04` container and ran `execute.sh`, which installed Python, Chrome, and pip packages on every container start. That script now lives in `deprecated/`. To migrate on the server:

1. Stop and remove the old container: `docker compose down` (from the old checkout/compose file)
1. `git pull` the new code
1. `docker compose up -d --build`
1. Verify with `docker compose ps` (should show `timetable_app` healthy), `curl -s http://localhost:5123/`, and `curl -s http://localhost:5123/update`
1. Keep the old Ubuntu image around until the new service has run successfully for a day, then remove it as optional cleanup

## Rollback

Check out the last known-good commit (`git checkout <commit>`) and run `docker compose up -d --build` again. Normal updates never require deleting volumes or destructive Docker cleanup commands.

## Development

1. `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d`
1. `docker compose -f docker-compose.yml -f docker-compose.dev.yml restart timetable`

The override mounts the working tree into the container and runs `trains.py` directly, so source changes need only a container restart to be served. Port 5123 maps to container port 5123. Do not use this configuration in production.

# To-do

* Abstract away the station name from the code, as well as the hard coded destinations for the east-west split.
* Clean up the time zones

# Testing

Run unit tests from the project root:

1. `./venv/bin/python -m unittest discover -s tests -p "test_*.py"`
