''' 
This is the main module for the trains web page
Establishes a Flask web server and serves the trains.html page.

The trains.html page will call the /update endpoint to get the latest departure data.
The /update endpoint will call the update() function which will get the latest departure data 
from the station object and return it as a JSON response.
The station object will use the TransportAPI class to communicate with the transport API and 
get the latest departure data.
The TransportAPI class will use Playwright to communicate with the transport API and get the 
latest departure data.

--- Threading ---

The Flask web server will run in the main thread and the Playwright browser will run in a separate 
thread.

Main thread
    |
    +-- imports trains.py
    +-- creates Flask app
    +-- creates Playwright
    +-- starts Waitress

Waitress uses a thread pool to handle requests. Each request will be handled in a separate thread.
Main thread
    |
    +-- Waitress listener

Worker thread #1
Worker thread #2
Worker thread #3
Worker thread #4

Worker thread #1
    |
    +-- imports trains.py
    +-- creates Playwright
    +-- starts Waitress


'''

import threading

from flask import Flask, render_template, Response
from waitress import serve

from mylog import logger


# from station import Station
from bahn_browser import BahnBrowser
from departures import process_departures

logger.debug("Starting")

app = Flask(__name__)
bahn_browser = None
init_lock = threading.Lock()

station_name = "Zorneding"
station_id = "8006671"
# station = Station(station_name, station_id)
url = f'https://www.bahn.de/web/api/reiseloesung/abfahrten?ortExtId={station_id}&verkehrsMittel[]=SBAHN'
port = 5123

def init():
    global bahn_browser
    with init_lock:
        if bahn_browser is None:
            bahn_browser = BahnBrowser()

def update():
    '''Get the latest departure data for the station from the station object and return it as a JSON response.'''
    logger.debug(f"Updating departure data for {station_name}")
    init()
    data = bahn_browser.get(url)
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
    init()
    logger.info(f"Starting web server for {station_name} at http://localhost:{port}")
    serve(
        app,
        host="0.0.0.0",
        port=port
    )
#    app.run(port=5124, debug=True)