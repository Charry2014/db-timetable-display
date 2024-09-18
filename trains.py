from flask import Flask, render_template, Response
from time import time, sleep
from datetime import datetime

from bahnapi import Station
import json

app = Flask(__name__)
station = Station("Zorneding")


def update():
    while True:
        data = station.get_departure_details()
        yield f"data: {json.dumps(data)}\n\n"
        sleep(60)


def generate_train_data():
    pass

@app.route('/')
def index():
    return render_template('trains.html')

@app.route('/update')
def time():
    while True:
        return Response(update(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True)