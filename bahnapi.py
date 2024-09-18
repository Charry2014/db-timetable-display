'''
bahnapi.py - Python script for pulling departure data for a specific station
This is going to pull the data from the API every minute and update a webpage
hosted on one of my servers. The page will be displayed in HA dashboard.

'''
import requests
from datetime import datetime
import xml.etree.ElementTree as elementTree


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
        self.__stations = response.json()
        if not len(self.__stations) == 1:
            raise Exception('Station name not unique or not found')
        self.__station = self.__stations[next(iter(self.__stations))]
        return self.__station


    def get_departure_details(self, id: int) -> tuple:
        response = requests.get(f'https://v6.db.transport.rest/stops/{id}/departures?results={self.__departures}&duration={self.__duration}&bus=false')
        decoded = response.json()['departures']
        # The response is a list of dicts with keys direction (Tutzing:str) delay (seconds:int)
        # when ('2024-09-18T16:23:00+02:00':str) and plannedWhen ('2024-09-18T16:23:00+02:00':str)
        print(type(decoded[0]))
        return decoded


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
        return self.__transport_api.get_departure_details(self.id)



station = Station("Zorneding")
trains = station.get_departure_details()
