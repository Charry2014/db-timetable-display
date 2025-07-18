'''Uses the DB RIS API to pull data about local trains.
'''


import json
from datetime import datetime, timezone
from dataclasses import dataclass
import string
from transportapi import TransportAPI
from mylog import logger


class Station:
    def __init__(self, name, departures=15, duration=360) -> None:
        self.__station_id = None
        self.__name = name
        # Duration and cache age in seconds
        self.__departures = departures
        self.__duration = duration
        self.__transport_api = TransportAPI()
        self.__get_station()

        self.__cache = {}
        self.__cache_age_max = 300 # seconds

    # Caching currently disbled to see if we need it
    @dataclass
    class CacheElement:
        data: str
        updated: datetime

    def __cache_response(self, url, response):
        self.__cache[url] = self.CacheElement(data=response, updated=datetime.now())

    def __get_cached_response(self, url) -> CacheElement:
        delete_keys = []
        # Iterate over whole cache dictionary and remove any element that is older than cache_age_max
        for key, value in self.__cache.items():
            if (datetime.now() - value.updated).seconds > self.__cache_age_max:
                delete_keys.append(key)
        for key in delete_keys:                
            self.__cache.pop(key)
            
        if url in self.__cache:
            return self.__cache[url]
        else:
            return None




    @property
    def id(self) -> int:
        return self.__station_id


    def __get_station(self):
        '''Get station details from the transport API using the station name.
       Hacked out for now, will return when I figure out this API and how to do it.
        '''
        self.__station_id = "8006671" # Nasty hack to get us going



    def __process_departures(self, departures):
        '''
        '''
        journeys = []
        for d in departures: 
            if d['verkehrmittel']['produktGattung'] != 'SBAHN':
                continue
            # trains that are on time do not have an 'ezZeit' field
            if 'ezZeit' not in d:
                d['ezZeit'] = d['zeit']
            journeys.append((d['terminus'], d['zeit'], d['ezZeit']))

        retval = []
        count = 0
        logger.debug(f"Processing {len(journeys)} journeys")
        for j in journeys:
            # Planned departure time - given in CET
            # "zeit": "2025-07-18T10:57:00",
            # "ezZeit": "2025-07-18T11:13:00",

            depart_planned = datetime.strptime(j[1], '%Y-%m-%dT%H:%M:%S')
            depart_actual = datetime.strptime(j[2], '%Y-%m-%dT%H:%M:%S')
            #depart_in = int((depart_actual - datetime.now()).seconds / 60) + 1
            assert depart_planned >= datetime.now() 
            depart_in_s = depart_actual - datetime.now()
            depart_in = int(depart_in_s.seconds / 60)
            depart_planned = depart_planned.strftime('%H:%M')
            depart_actual = depart_actual.strftime('%H:%M')
            # Check sanity of the departure time - can return funky values for trains departing now
            # this is a race condition and nothing serious.
            if depart_in > 1000:
                logger.warning(f"Departure time is greater than 1000 minutes {depart_in} - setting to 0")
                depart_in = 0
            # Destination, Depart in minutes, Actual departure time, Delay minutes, Planned departure time
            delay = int((datetime.fromisoformat(j[2]) - datetime.fromisoformat(j[1])).total_seconds()/60)
            retval.append((j[0], depart_in, depart_actual, delay, depart_planned))
            count += 1
            if count == 20: break

        # Sort on the depart in minutes field
        retval.sort(key=lambda x: x[1])
        return retval

    def __get_departure_details(self, id: int):
        '''
        {
        "entries": [
            {
            "bahnhofsId": "8006671",
            "zeit": "2025-07-18T10:57:00",
            "ezZeit": "2025-07-18T11:13:00",
            "gleis": "4",
            "journeyId": "2|#VN#1#ST#1752694647#PI#0#ZI#291942#TA#2#DA#180725#1S#8005927#1T#944#LS#8002347#LT#1107#PU#80#RT#1#CA#s#ZE#6#ZB#S      6#PC#4#FR#8005927#FT#944#TO#8002347#TT#1107#",
            "meldungen": [],
            "verkehrmittel": {
                "name": "S 6",
                "linienNummer": "6",
                "kurzText": "S",
                "mittelText": "S 6",
                "langText": "S 6",
                "produktGattung": "SBAHN"
            },
            "terminus": "Grafing Bahnhof"
            },
            {
            "bahnhofsId": "8006671",
            "zeit": "2025-07-18T11:02:00",
        '''
        # Here are some deprecated URLs that used to work
        # url = f'https://www.bahnhof.de/api/boards/departures?evaNumbers=8006671&filterTransports=CITY_TRAIN&duration=60&locale=de'
        # url = f'https://www.bahnhof.de/api/boards/departures?evaNumbers={id}&filterTransports=CITY_TRAIN&duration={self.__duration}&locale=de'
        # Here is the current URL
        url = f'https://www.bahn.de/web/api/reiseloesung/abfahrten?ortExtId={id}&verkehrsMittel[]=SBAHN'

        response, timestamp = self.__transport_api.communicate(url) 
        if isinstance(response, int):
            # If we got a number back then we assume the server returned an error code
            retval = [(f"{timestamp}", f"Err {response}", f"Error code {response}", 0, "....")]
        else:
            retval = self.__process_departures(response['entries'])

        return retval, timestamp




    def get_departure_details(self):
        ''''Grafing Bahnhof', (Depart in) 8, '17:40', (Delay) 32, '17:08'
        '''
        trains, timestamp = self.__get_departure_details(self.id)
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
