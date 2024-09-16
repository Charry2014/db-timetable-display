'''
bahnapi.py - Python library for the Deutsche Bahn API

Register at https://developers.deutschebahn.com and get your credentials.
Sign up to the timetables api and associate your application with this.
https://developers.deutschebahn.com/db-api-marketplace/apis/product/timetables/api/26494#/Timetables_10213/overview
Then it will work

https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1/station/BLS
Where BLS is the station code for Berlin Hbf.

Seven digit station codes (EvaNo)can be found here:
https://github.com/ratopi/haltestellendaten/blob/master/D_Bahnhof_2017_09.csv

Code letters can be found here -->
https://www.bahnstatistik.de/BfVerzM.htm

'''
import requests
from datetime import datetime
import xml.etree.ElementTree as elementTree

class ApiAuthentication:
    def __init__(self, client_id, client_secret) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    def test_credentials(self) -> bool:
        response = requests.get(
            "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1/station/MZO",
            headers={
                "DB-Api-Key": self.client_secret,
                "DB-Client-Id": self.client_id,
            }
        )
        # Returns the EVA number for the station Zorneding.
        # '<stations>\n\n<station name="Zorneding" eva="8006671" ds100="MZO" db="true" creationts="24-09-12 10:07:44.814"/>\n\n</stations>\n'
        # '<stations>\n\n<station p="11|12 D - G|12|13 A - D|13|14|13 D - G|13 A - C|13 C - D|11 D - G|14 A - D|14 A - C|14 C - D|14 E - F|11 C - D|13 E - F|11 E - F|11 A - D|12 A - D|14 D - G|12 C - D|12 E - F" meta="8070952|8071068|8089021|8098160" name="Berlin Hbf" eva="8011160" ds100="BLS" db="true" creationts="24-09-12 10:07:44.079"/>\n\n</stations>\n'
        return response.status_code == 200

    def get_headers(self) -> dict[str, str]:
        return {
                "DB-Api-Key": self.client_secret,
                "DB-Client-Id": self.client_id,
            }

    @property
    def client_id(self):
        return self._client_id

    @client_id.setter
    def client_id(self, value):
        self._client_id = value

    @property
    def client_secret(self):
        return self._client_secret

    @client_secret.setter
    def client_secret(self, value):
        self._client_secret = value


class Station:
    def __init__(self, api, name) -> None:
        self.api = api
        self.name = name

        # headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
        headers = {'Accept': 'application/json', 'Host': 'httpbin.org', 'User-Agent': 'curl/7.68.0', 'X-Amzn-Trace-Id': 'Root=1-66e7e22b-293b9f31221d559558bfddfd'}

        requests.packages.urllib3.util.connection.HAS_IPV6 = False
        response = requests.get('https://v6.db.transport.rest/stations?query=berlin') #, headers=headers, stream=True)
        # response = requests.get('https://v6.db.transport.rest/stops/8006671/departures', params=params, headers=headers)        
        print(response.text)

        def log(event_name, info):
            print(event_name, info)

        import httpx
        client = httpx.Client(http2=True)
        # response = client.get(f'https://v6.db.transport.rest/stations?query={self.name}') #, headers=headers)
        response = client.get(f'https://v6.db.transport.rest/stations?query=berlin', extensions={"trace": log}) #, headers=headers)
        protocol = response.http_version
        print(f'Response received via: {protocol}')
        # Print the response
        print(response.text)
        pass

        import subprocess
        # command = f'curl \'https://v6.db.transport.rest/stations?query={self.name}\' -s'
        command = f'curl \'https://v6.db.transport.rest/stations?query=berlin\' -s'
        result = subprocess.run(command, capture_output=True, shell=True, text=True)
        print(result.stdout)
        print(result.stderr)
        pass

    def get_stuff(self):
        date_string: str = datetime.now().strftime("%y%m%d")
        hour_date: datetime = datetime.now()
        hour: str = hour_date.strftime("%H")
        
        response = requests.get(
            f"https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1/plan/8006671/{date_string}/{hour}",
            # f"/plan/MZO/{date_string}/{hour}",
#            headers=self.api.get_headers()
            headers={
                "DB-Api-Key": self.api.client_secret,
                "DB-Client-Id": self.api.client_id,
            }
)

        print("timetables plan")
        print(response.text)
        with(open("plan.xml", "w")) as f:
            f.write(response.text)
        return response.status_code == 200

    def get_timetable_changes(self, trains: list) -> int:
        response = requests.get(
            f"https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1/fchg/8006671",
            headers=self.api.get_headers()
        )
        with(open("changes.xml", "w")) as f:
            f.write(response.text)
        # print("timetables changes")
        # print(response.text)

        changed_trains = elementTree.fromstringlist(response.text)
        return 0

    def get_journey_details(self):
        params = {
            'results': '5',
        }
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}

        import httpx
        client = httpx.Client(http2=True)
        response = client.get('https://v6.db.transport.rest/stops/8006671/departures?results=15&duration=360&bus=false')
        protocol = response.http_version
        print(f'Response received via: {protocol}')
        # Print the response
        print(response.text)
        with(open("journey_details.json", "w")) as f:
            f.write(response.text)
        decoded = response.json()



        response = requests.get('https://v6.db.transport.rest/stops/8006671/departures', headers=headers)
        # response = requests.get('https://v6.db.transport.rest/stops/8006671/departures', params=params, headers=headers)        
        print("journey details")
        print(response.text)
        return 0



api = ApiAuthentication("44a6dd972ce8a4fb8944a0e72fed8c9c", "340cc28c569f14b91187e15cee474324")
success: bool = api.test_credentials()

station = Station(api, "Zorneding")
result = station.get_stuff()
result = station.get_timetable_changes([])
station.get_journey_details()


print(result)