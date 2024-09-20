'''
bahnapi.py - Python script for pulling departure data for a specific station
This is going to pull the data from the API every minute and update a webpage
hosted on one of my servers. The page will be displayed in HA dashboard.

'''
import requests
from datetime import datetime, timezone
import json


class TransportAPI:
    requests.packages.urllib3.util.connection.HAS_IPV6 = False

    def __init__(self, name, departures=15, duration=360) -> None:
        self.__name = name
        self.__station = self.__get_station()
        self.__departures = departures
        self.__duration = duration


    def __get_station(self) -> dict:
        '''Get station details from the transport API using the station name.
        The get() returns a dict with the station details, keyed on station
        ID. This is unhelpful to us as we don't know the ID yet. We save the
        station object by accessing the first (and only) element in the dict.
        '''
        response = requests.get(f'https://v6.db.transport.rest/stations?query={self.__name}')
        if response.status_code != 200:
            raise Exception(f'Server error code {response.status_code}')
        self.__stations = response.json()
        if not len(self.__stations) == 1:
            raise Exception('Station name not unique or not found')
        self.__station = self.__stations[next(iter(self.__stations))]
        return self.__station


    def get_departure_details(self, id: int):
        response = requests.get(f'https://v6.db.transport.rest/stops/{id}/departures?results={self.__departures}&duration={self.__duration}&bus=false&taxi=false')
        if response.status_code != 200:
            raise Exception(f'Server error code {response.status_code}')
            exit(response.status_code)
        decoded = response.json()['departures']
        # The response is a list of dicts with keys direction (Tutzing:str) delay (seconds:int)
        # when ('2024-09-18T16:23:00+02:00':str) and plannedWhen ('2024-09-18T16:23:00+02:00':str)
        filtered = []
        for d in decoded:
            if d['plannedWhen'] == None:
                raise Exception('Invalid data received from server')
                exit(1)
            if d['when'] == None:
                d['when'] = d['plannedWhen']
            depart = datetime.strptime(d['when'], '%Y-%m-%dT%H:%M:%S%z')
            when = depart.strftime('%H:%M')
            depart_in = int((depart - datetime.now(timezone.utc)).seconds / 60) + 1
            # Check sanity of the departure time - can return funky values for trains departing now
            assert depart_in >= 0
            if depart_in > 1000:
                depart_in = 0
            planned = datetime.strptime(d['plannedWhen'], '%Y-%m-%dT%H:%M:%S%z').strftime('%H:%M')
            if d['delay'] is not None: 
                delay = int(d['delay'] / 60) 
            else: 
                delay = 0 
            filtered.append((d['direction'], depart_in, when, delay, planned))

        return filtered


    @property
    def station(self) -> int:
        return self.__station



class Station:
    def __init__(self, name) -> None:
        self.__name = name
        self.__transport_api = TransportAPI(name)

    @property
    def id(self) -> int:
        return self.__transport_api.station['id']

    def get_departure_details(self):
        ''''Grafing Bahnhof', (Depart in) 8, '17:40', (Delay) 32, '17:08'
        '''
        trains = self.__transport_api.get_departure_details(self.id)
        trains.sort(key=lambda x: x[1])
        trains_east = [train for train in trains if train[0] in ['Ebersberg(Oberbay)', 'Grafing Bahnhof']]
        trains_west = [train for train in trains if train[0] not in ['Ebersberg(Oberbay)', 'Grafing Bahnhof']]

        retval = json.dumps({"timestamp": f"Updated {datetime.strftime(datetime.now(), '%H:%M') }",
                           "trains_east": trains_east, "trains_west": trains_west})
        return retval



if __name__ == '__main__':
    station = Station("Zorneding")
    trains = station.get_departure_details()
    print(trains)
