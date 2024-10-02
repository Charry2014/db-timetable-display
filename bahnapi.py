'''
bahnapi.py - Python script for pulling departure data for a specific station
This is going to pull the data from the API every minute and update a webpage
hosted on one of my servers. The page will be displayed in HA dashboard.

'''
import json
from datetime import datetime, timezone

from transportapi import TransportAPI


class Station:
    def __init__(self, name, departures=15, duration=360) -> None:
        self.__name = name
        # Duration and cache age in seconds
        self.__departures = departures
        self.__duration = duration
        self.__transport_api = TransportAPI()
        self.__get_station()


    @property
    def id(self) -> int:
        return self.__station_id


    def __get_station(self):
        '''Get station details from the transport API using the station name.
        The get() returns a dict with the station details, keyed on station
        ID. This is unhelpful to us as we don't know the ID yet. We save the
        station object by accessing the first (and only) element in the dict.
        '''
        response, _ = self.__transport_api.communicate(f'https://v6.db.transport.rest/stations?query={self.__name}')
        if not len(response) == 1:
                print(f'Station name not unique or not found')
                raise SystemExit(1)
        self.__station_id = response[next(iter(response))]['id']
        assert self.__station_id.isdigit()


    def __process_departures(self, departures):
        # The response is a list of dicts with keys direction (Tutzing:str) delay (seconds:int)
        # when ('2024-09-18T16:23:00+02:00':str) and plannedWhen ('2024-09-18T16:23:00+02:00':str)
        filtered = []
        tripid = {}
        for d in departures:
            # Filter out duplicates, the server does sometimes produce these
            if d['tripId'] in tripid:
                continue
            tripid[d['tripId']] = 1
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


    def __get_departure_details(self, id: int):
        # 
        default = [("Waiting for DB", 0, "No response from server", 0, "....")]
        url = f'https://v6.db.transport.rest/stops/{id}/departures?results={self.__departures}&duration={self.__duration}&bus=false&taxi=false'
        response, timestamp = self.__transport_api.communicate(url, default=default) 
        if 'departures' in response:
            retval = self.__process_departures(response['departures'])
        else:
            retval = response

        return retval, timestamp


    def get_departure_details(self):
        ''''Grafing Bahnhof', (Depart in) 8, '17:40', (Delay) 32, '17:08'
        '''
        trains, timestamp = self.__get_departure_details(self.id)
        trains.sort(key=lambda x: x[1])
        trains_east = [train for train in trains if train[0] in ['Ebersberg(Oberbay)', 'Grafing Bahnhof']]
        trains_west = [train for train in trains if train[0] not in ['Ebersberg(Oberbay)', 'Grafing Bahnhof']]

        retval = json.dumps({"timestamp": f"Updated {timestamp}",
                             "direction1_title": "Direction Ebersberg",
                             "direction2_title": "Direction Munich",
                             "trains_east": trains_east, "trains_west": trains_west})

        return retval



if __name__ == '__main__':
    station = Station("Zorneding")
    trains = station.get_departure_details()
    print(trains)
