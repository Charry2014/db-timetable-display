import requests
from datetime import datetime
from mylog import logger

class TransportAPI:
    # This site has bad IPv6 support. Turn it off.
    requests.packages.urllib3.util.connection.HAS_IPV6 = False

    def communicate(self, url):
        '''Handle communication with the server - if the server responds 200 then all good.
        If the server responds anything else then we assume the call failed.
        Returns a tuple with the response and the time of the request if successful.
        If the request fails then we return the status code. and time of the request.
        '''
        logger.debug(f"Communicating with {url}")
        response = requests.get(url)
        updated = datetime.strftime(datetime.now(), '%H:%M')
        logger.debug(f"Communicating ended - response code {response.status_code} at {updated}")

        if response.status_code == 200:
            # If the response is 200 OK then we assume the server returned a JSON object 
            retval = response.json()
        else:
            logger.error(f'Server returned unexpected code {response.status_code}.')
            retval = response.status_code

        return retval, updated
    