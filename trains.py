from flask import Flask, render_template, Response

from mylog import logger


from station import Station

app = Flask(__name__)
logger.debug("Starting")
station_name = "Zorneding"
station = Station(station_name)
logger.debug(f"Got station details {station_name} - {station.id}")

def update():
    logger.debug(f"Updating departure data for {station_name}")
    data = station.get_departure_details()
    logger.debug(f"Got departure data - {data}")
    return data

@app.route('/')
def index():
    return render_template('trains.html')

@app.route('/update')
def flask_update():
    logger.debug("Serving departure update")
    return Response(update(), mimetype='application/json')

if __name__ == '__main__':
    app.run(port=5124, debug=True)