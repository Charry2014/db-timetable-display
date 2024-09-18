'''
flask.py - Flask script for pulling departure data for a specific station
'''

from flask import Flask, render_template, request, redirect
import requests

app = Flask(__name__)

def get_train_data(station_code):
    # Replace with your actual API endpoint and parameters
    api_url = f"https://api.example.com/trains?station={station_code}"
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

@app.route('/')
def index():
    station_code = request.args.get('station_code')
    if station_code:
        train_data = get_train_data(station_code)
        if train_data:
            return render_template('trains.html', train_data=train_data)
        else:
            return "Error fetching train data."
    else:
        return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    station_code = request.form['station_code']
    return redirect(f'/?station_code={station_code}')

if __name__ == '__main__':
    app.run(debug=True)