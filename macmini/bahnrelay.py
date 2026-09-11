#!/usr/bin/env python3

import json
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit


LISTEN_ADDRESS = "0.0.0.0"
LISTEN_PORT = 8765

# Cache each station's response separately so parallel page polls do not
# cause several Bahn requests simultaneously.
CACHE_SECONDS = 15
CURL_TIMEOUT_SECONDS = 20

cache_lock = threading.Lock()
cache = {}


def bahn_url(station):
    """Build the Bahn departures URL for one station code."""

    return (
        "https://www.bahn.de/web/api/reiseloesung/abfahrten"
        f"?ortExtId={station}"
        "&verkehrsMittel%5B%5D=SBAHN"
    )


def parse_station(query):
    """Extract the station parameter from a request query string."""

    values = parse_qs(query).get("station")

    return values[0] if values else None


def is_valid_station(station):
    """Only EVA station numbers (plain digit strings) are accepted."""

    return station is not None and station.isdigit()


def fetch_from_bahn(station):
    """Fetch departure data using the native macOS curl executable."""

    command = [
        "/usr/bin/curl",
        "-4",
        "--silent",
        "--show-error",
        "--max-time",
        str(CURL_TIMEOUT_SECONDS),
        "--output",
        "-",
        "--write-out",
        "\n%{http_code}",
        bahn_url(station),
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            "curl failed with exit code {}: {}".format(
                result.returncode,
                error,
            )
        )

    try:
        body, status_text = result.stdout.rsplit(b"\n", 1)
        status_code = int(status_text)
    except (ValueError, TypeError) as exc:
        raise RuntimeError("Could not parse curl response") from exc

    if status_code != 200:
        response_text = body.decode("utf-8", errors="replace")
        raise RuntimeError(
            "Bahn returned HTTP {}: {}".format(
                status_code,
                response_text,
            )
        )

    # Confirm that Bahn actually returned valid JSON.
    try:
        json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Bahn returned invalid JSON") from exc

    return body


def get_departures(station):
    """Return cached data for one station or perform a new request."""

    with cache_lock:
        entry = cache.get(station)

        if entry is None:
            entry = {
                "body": None,
                "cached_at": 0.0,
                "lock": threading.Lock(),
            }
            cache[station] = entry

    with entry["lock"]:
        now = time.monotonic()

        if entry["body"] is not None and now - entry["cached_at"] < CACHE_SECONDS:
            return entry["body"], True

        body = fetch_from_bahn(station)
        entry["body"] = body
        entry["cached_at"] = time.monotonic()

        return body, False


class BahnRelayHandler(BaseHTTPRequestHandler):

    server_version = "BahnRelay/1.1"

    def send_body(self, status_code, body, content_type):
        if isinstance(body, str):
            body = body.encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status_code, value):
        body = json.dumps(value).encode("utf-8")
        self.send_body(
            status_code,
            body,
            "application/json; charset=utf-8",
        )

    def do_GET(self):
        split = urlsplit(self.path)
        path = split.path

        if path == "/health":
            self.send_json(
                200,
                {
                    "status": "OK",
                    "service": "bahn-relay",
                },
            )
            return

        if path == "/departures":
            station = parse_station(split.query)

            if not is_valid_station(station):
                print(
                    "{} /departures: 400 (missing or invalid station parameter)".format(
                        self.client_address[0],
                    )
                )

                self.send_json(
                    400,
                    {
                        "status": "ERROR",
                        "message": "Use /departures?station=<eva number>",
                    },
                )
                return

            try:
                body, from_cache = get_departures(station)

                print(
                    "{} /departures?station={}: 200 ({})".format(
                        self.client_address[0],
                        station,
                        "cached" if from_cache else "fetched from Bahn",
                    )
                )

                self.send_body(
                    200,
                    body,
                    "application/json; charset=utf-8",
                )

            except Exception as exc:
                print(
                    "{} /departures?station={}: ERROR: {}".format(
                        self.client_address[0],
                        station,
                        exc,
                    )
                )

                self.send_json(
                    502,
                    {
                        "status": "ERROR",
                        "message": str(exc),
                    },
                )

            return

        self.send_json(
            404,
            {
                "status": "ERROR",
                "message": "Not found",
            },
        )

    def log_message(self, message_format, *args):
        # Suppress BaseHTTPRequestHandler's duplicate access logging.
        return


def main():
    server = ThreadingHTTPServer(
        (LISTEN_ADDRESS, LISTEN_PORT),
        BahnRelayHandler,
    )

    print(
        "Bahn relay listening on http://{}:{}/departures?station=<eva number>".format(
            LISTEN_ADDRESS,
            LISTEN_PORT,
        )
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Bahn relay")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()