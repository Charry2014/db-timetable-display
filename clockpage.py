from flask import Flask, render_template, Response
from time import time, sleep
from datetime import datetime

from bahnapi import Station


app = Flask(__name__)
station = Station("Zorneding")


def generate_time():
    while True:
        now = f"data:{datetime.now()}\n\n"
        # print(now)
        yield now
        sleep(1)


def generate_train_data():
    pass

@app.route('/')
def index():
    return render_template('trains.html')

@app.route('/time')
def time():
    return Response(generate_time(), mimetype='text/event-stream')

@app.route('/trains')
def trains():
    return Response(generate_train_data(), mimetype='text/event-stream')

if __name__ == '__main__':

    app.run(debug=True)