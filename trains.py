'''Flask application serving the DB Timetables-powered departure board.

The page polls the /update endpoint while visible. The server uses the authenticated
DB Timetables API and keeps the existing relay-shaped data contract for the frontend.
'''

from flask import Flask, Response, render_template
from waitress import serve

from departure_service import DepartureService
from departures import process_departures
from mylog import logger

logger.debug("Starting")

app = Flask(__name__)
station_name = "Zorneding"
port = 5123
service = DepartureService.from_env()


def update():
    logger.debug("Updating departure data for {}", station_name)
    return process_departures(service.get_departures())


@app.route('/')
def index():
    return render_template('trains.html')


@app.route('/update')
def flask_update():
    logger.debug("Serving departure update")
    return Response(update(), mimetype='application/json')


if __name__ == '__main__':
    logger.info("Starting web server for {} at http://localhost:{}", station_name, port)
    serve(app, host="0.0.0.0", port=port)
