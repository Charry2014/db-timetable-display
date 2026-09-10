'''
This is the main module for the trains web page
Establishes a Flask web server and serves the trains.html page.

The trains.html page will call the /update endpoint to get the latest departure data.
The /update endpoint will call the update() function which fetches the latest departure data
from the departures service and returns it as a JSON response.
The departures service returns JSON in the same structure as the Bahn API and
process_departures() turns it into the payload used by the frontend.

--- Threading ---

The Flask web server runs in the main thread and Waitress uses a thread pool to handle
requests. Each request thread calls update(), which performs a plain HTTP fetch of the
departures service URL. There is no browser and no worker thread.
'''

import json
from urllib.error import HTTPError
from urllib.request import urlopen

from flask import Flask, render_template, Response
from waitress import serve

from mylog import logger
from departures import process_departures

logger.debug("Starting")

app = Flask(__name__)

station_name = "Zorneding"
url = 'http://10.0.0.204:8765/departures'
port = 5123


def fetch_departures(url):
    '''Fetch the raw departure JSON from the departures service.

    Returns the parsed JSON on success, otherwise a dictionary with
    "error" (HTTP status code or -1 for exceptions) and "body" describing
    the failure.
    '''
    logger.debug(f"Fetching data from {url}")
    try:
        with urlopen(url, timeout=30) as response:
            return json.loads(response.read())
    except HTTPError as e:
        try:
            body = e.read().decode('utf-8', errors='replace')
        except Exception:
            body = ''
        logger.error(f'Server returned {e.code}')
        logger.error(f"Response text: {body}")
        return {"error": e.code, "body": body}
    except Exception as e:
        logger.error(f'Exception reading train data: {e}')
        return {"error": -1, "body": str(e)}


def update():
    '''Fetch the latest departure data and return it as a JSON response.'''
    logger.debug(f"Updating departure data for {station_name}")
    data = fetch_departures(url)
    logger.debug(f"Got departure data - {data}")
    departures = process_departures(data)
    return departures


@app.route('/')
def index():
    return render_template('trains.html')


@app.route('/update')
def flask_update():
    logger.debug("Serving departure update")
    return Response(update(), mimetype='application/json')


if __name__ == '__main__':
    logger.info(f"Starting web server for {station_name} at http://localhost:{port}")
    serve(
        app,
        host="0.0.0.0",
        port=port
    )