from flask import Flask, render_template, Response
from time import time, sleep
from datetime import datetime
import json

from mylog import logger


from ris import Station

app = Flask(__name__)
logger.debug("Starting")
station_name = "Zorneding"
station = Station(station_name)
logger.debug(f"Got station details {station_name} - {station.id}")

def update():
    
    while True:
        logger.debug(f"Updating departure data for {station_name}")
        data = station.get_departure_details()
        logger.debug(f"Got departure data - {data}")
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
    app.run(port=5123, debug=True)