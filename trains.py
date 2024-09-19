from flask import Flask, render_template, Response
from time import time, sleep
from datetime import datetime
import json

from loguru import logger
logger.remove(0)

from bahnapi import Station

app = Flask(__name__)

def update():
    while True:
        logger.debug("Updating data")
        data = station.get_departure_details()
        logger.debug("Got data")
        yield f"data: {data}\n\n"
        sleep(15)

@app.route('/')
def index():
    return render_template('trains.html')

@app.route('/update')
def flask_update():
    logger.debug("Starting Flask update")
    while True:
        return Response(update(), mimetype='text/event-stream')

if __name__ == '__main__':

    logger.debug("Starting")
    station = Station("Zorneding")
    logger.debug("Got station details")
    app.run(port=5123, debug=True)