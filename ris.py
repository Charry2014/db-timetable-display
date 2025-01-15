'''Uses the DB RIS API to pull data about local trains.
'''


import json
from datetime import datetime, timezone

from transportapi import TransportAPI


class Station:
    def __init__(self, name, departures=15, duration=360) -> None:
        self.__name = name
        self.__station_id = 0
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
       Hacked out for now, will return when I figure out this API and how to do it.
        '''
        # response, _ = self.__transport_api.communicate(f'https://v6.db.transport.rest/stations?query={self.__name}')
        # if not len(response) == 1:
        #         print(f'Station name not unique or not found')
        #         raise SystemExit(1)
        self.__station_id = "8006671" # Nasty hack to get us going
        assert self.__station_id.isdigit()



    def __process_departures(self, departures):
        journeys = [(d[0]['destination']['name'], d[0]['timeSchedule'], d[0]['timeDelayed'], d[0]['delayed'], d[0]['canceled']) for d in departures]
        # ('Geltendorf', '2025-01-15T16:51:00+01:00', '2025-01-15T16:51:00+01:00', False, False)
        # ('Grafing Bahnhof', '2025-01-15T16:48:00+01:00', '2025-01-15T16:58:00+01:00', True, False)
        # ('Tutzing', '2025-01-15T17:02:00+01:00', '2025-01-15T17:02:00+01:00', False, False)
        retval = []
        count = 0
        for j in journeys:
            # Ignore trains labelled as cancelled
            if j[4] == True: continue
            # Planned departure time
            depart_planned = datetime.strptime(j[1], '%Y-%m-%dT%H:%M:%S%z')
            depart_planned = depart_planned.strftime('%H:%M')
            depart_actual = datetime.strptime(j[2], '%Y-%m-%dT%H:%M:%S%z')
            depart_in = int((depart_actual - datetime.now(timezone.utc)).seconds / 60) + 1
            depart_actual = depart_actual.strftime('%H:%M')
            # Check sanity of the departure time - can return funky values for trains departing now
            # this is a race condition and nothing serious.
            assert depart_in >= 0
            if depart_in > 1000:
                depart_in = 0
            # Destination, Depart in minutes, Actual departure time, Delay minutes, Planned departure time
            delay = int((datetime.fromisoformat(j[2]) - datetime.fromisoformat(j[1])).total_seconds()/60)
            retval.append((j[0], depart_in, depart_actual, delay, depart_planned))
            count += 1
            if count == 20: break

        return retval

    def __get_departure_details(self, id: int):
        # 
        default = [("Waiting for DB", 0, "No response from server", 0, "....")]
        # url = f'https://www.bahnhof.de/api/boards/departures?evaNumbers=8006671&filterTransports=CITY_TRAIN&duration=60&locale=de'
        url = f'https://www.bahnhof.de/api/boards/departures?evaNumbers={id}&filterTransports=CITY_TRAIN&duration={self.__duration}&locale=de'

        response, timestamp = self.__transport_api.communicate(url, default=default) 
        if 'entries' in response:
            retval = self.__process_departures(response['entries'])
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
