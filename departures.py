'''
'''
import json
from datetime import datetime
from mylog import logger

def process_departures(data:dict):
    '''
    Takes a dictionary from the bahn_browser and returns a JSON string with the departure details for the station.
    'Grafing Bahnhof', (Depart in) 8, '17:40', (Delay) 32, '17:08'
    '''
    timestamp = datetime.strftime(datetime.now(), '%H:%M')

    if 'error' in data:
        retval = [(f"{timestamp}", f"Err {data}", f"Error code {data}", 0, "....")]
        response = data['body']
    else:
        trains = __get_departure_details(data['entries'])
        trains_east = [train for train in trains if train[0] in ['Ebersberg(Oberbay)', 'Grafing Bahnhof']]
        trains_west = [train for train in trains if train[0] not in ['Ebersberg(Oberbay)', 'Grafing Bahnhof']]

        retval = json.dumps({"timestamp": f"Updated {timestamp}",
                                "direction1_title": "Direction Ebersberg",
                                "direction2_title": "Direction Munich",
                                "trains_east": trains_east, "trains_west": trains_west})

        return retval




def __get_departure_details(data:dict):
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
    journeys = []
    for d in data:
        try:
            # This log is very informative but too noisy for regular use
            # logger.debug(f"Processing departure data {d}")
            if d['verkehrmittel']['produktGattung'] != 'SBAHN':
                continue
            # trains that are on time do not have an 'ezZeit' field
            if 'ezZeit' not in d:
                d['ezZeit'] = d['zeit']
            journeys.append((d['terminus'], d['zeit'], d['ezZeit']))
        except Exception as e:
            logger.error(f"Error processing departure data: {e} - data: {d}")

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
        if depart_actual >= datetime.now():
            depart_in_s = depart_actual - datetime.now()
            depart_in = int(depart_in_s.seconds / 60)
        else:
            logger.warning(f"Departure time is in the past {depart_actual} - setting to 0")
            depart_in = 0
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
