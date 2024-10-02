'''
bahnapi.py - Python script for pulling departure data for a specific station
This is going to pull the data from the API every minute and update a webpage
hosted on one of my servers. The page will be displayed in HA dashboard.

'''
import requests
from datetime import datetime, timezone
from dataclasses import dataclass
import json


class TransportAPI:
    # This site has bad IPv6 support. Turn it off.
    requests.packages.urllib3.util.connection.HAS_IPV6 = False

    @dataclass
    class CacheElement:
        data: None # This will be the data structure returned by response.get()
        updated: datetime


    def __init__(self, name, departures=15, duration=360, cache_age_max=3) -> None:
        self.__name = name
        self.__departures = departures
        self.__duration = duration
        self.__cache = {}
        self.__cache_age_max = cache_age_max # in minutes

        self.__station = self.__get_station()


    def __cache_response(self, url, response):
        self.__cache[url] = self.CacheElement(data=response, updated=datetime.now())

    def __get_cached_response(self, url) -> CacheElement:
        delete_keys = []
        # Iterate over whole cache dictionary and remove any element that is older than cache_age_max
        for key, value in self.__cache.items():
            if (datetime.now() - value.updated).seconds > self.__cache_age_max * 60:
                delete_keys.append(key)
        for key in delete_keys:                
            self.__cache.pop(key)
        if url in self.__cache:
            return self.__cache[url]
        else:
            return None

    def __communicate(self, url, default=None):
        response = requests.get(url)
        if response.status_code == 200:
            response = response.json()
            self.__cache_response(url, response)
            updated = datetime.strftime(datetime.now(), '%H:%M')
        else:
            cached = self.__get_cached_response(url)
            if cached is None:
                if default == None:
                    print(f'Server error code {response.status_code} and cache miss. Exiting.')
                    raise SystemExit(1)
                else:
                    response = default
                    updated = datetime.strftime(datetime.now(), '%H:%M')
            else:
                updated = datetime.strftime(cached.updated, '%H:%M')
                response = cached.data
        return response, updated

    def __get_station(self) -> dict:
        '''Get station details from the transport API using the station name.
        The get() returns a dict with the station details, keyed on station
        ID. This is unhelpful to us as we don't know the ID yet. We save the
        station object by accessing the first (and only) element in the dict.
        '''
        response, _ = self.__communicate(f'https://v6.db.transport.rest/stations?query={self.__name}')
        self.__stations = response # .json()
        if not len(self.__stations) == 1:
                print(f'Station name not unique or not found')
                raise SystemExit(1)
        self.__station = self.__stations[next(iter(self.__stations))]
        return self.__station

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


    def get_departure_details(self, id: int):
        # 
        default = [("Waiting for DB", 0, "No response from server", 0, "....")]
        url = f'https://v6.db.transport.rest/stops/{id}/departures?results={self.__departures}&duration={self.__duration}&bus=false&taxi=false'
        response, timestamp = self.__communicate(url, default=default) 
        if 'departures' in response:
            retval = self.__process_departures(response['departures'])
        else:
            retval = response

        return retval, timestamp


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
        trains, timestamp = self.__transport_api.get_departure_details(self.id)
        trains.sort(key=lambda x: x[1])
        trains_east = [train for train in trains if train[0] in ['Ebersberg(Oberbay)', 'Grafing Bahnhof']]
        trains_west = [train for train in trains if train[0] not in ['Ebersberg(Oberbay)', 'Grafing Bahnhof']]

        retval = json.dumps({"timestamp": f"Updated {timestamp}",
                           "trains_east": trains_east, "trains_west": trains_west})
        return retval



if __name__ == '__main__':
    station = Station("Zorneding")
    trains = station.get_departure_details()
    print(trains)
