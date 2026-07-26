# import requests
from curl_cffi import requests

from datetime import datetime
from mylog import logger

class TransportAPI:
    # This site has bad IPv6 support. Turn it off.
    # requests.packages.urllib3.util.connection.HAS_IPV6 = False

    def __init__(self):
        self.__session = requests.Session()
        self.__session.impersonate = "chrome150"

    def communicate(self, url):
        '''Handle communication with the server - if the server responds 200 then all good.
        If the server responds anything else then we assume the call failed.
        Returns a tuple with the response and the time of the request if successful.
        If the request fails then we return the status code. and time of the request.
        '''
        '''
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        '''
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "de-DE,de;q=0.9",
            "Referer": "https://www.bahn.de/",
            "Origin": "https://www.bahn.de",
        }
        logger.debug(f"Communicating with {url}")
        # response = requests.get(url, headers=headers)
        response = self.__session.get(
            url,
            headers=headers
        )
        updated = datetime.strftime(datetime.now(), '%H:%M')
        logger.debug(f"Communicating ended - response code {response.status_code} at {updated}")


        if response.status_code == 200:
            # If the response is 200 OK then we assume the server returned a JSON object 
            retval = response.json()
        else:
            logger.error(f'Server returned unexpected code {response.status_code}.')
            # logger.error(f"Response text: {curl_cffi.__version__}")
            for k, v in response.headers.items():
                logger.error(f"{k}: {v}")
            # for c in self.__session.cookies:
            #     logger.error(f"{c.name} = {c.value}")
            
            retval = response.status_code

        return retval, updated
    