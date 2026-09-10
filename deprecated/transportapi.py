

DEPRECATED: This file is deprecated and will be removed in a future release. Use bahn_browser.py instead.

from playwright.sync_api import sync_playwright

from datetime import datetime
from mylog import logger

class TransportAPI:

    def __init__(self):
        p = sync_playwright().start()
        self.__browser = p.chromium.launch(
            channel="chrome",
            headless=True
        )
        self.__page = self.__browser.new_page()

    def communicate(self, url):
        '''Handle communication with the server - if the server responds 200 then all good.
        If the server responds anything else then we assume the call failed.
        Returns a tuple with the response and the time of the request if successful.
        If the request fails then we return the status code. and time of the request.
        '''
        logger.debug(f"Communicating with {url}")
        # response = requests.get(url, headers=headers)
        response = self.__page.goto(url)
        updated = datetime.strftime(datetime.now(), '%H:%M')
        logger.debug(f"Communicating ended - response code {response.status} at {updated}")


        if response.status == 200:
            # If the response is 200 OK then we assume the server returned a JSON object 
            retval = response.json()
        else:
            logger.error(f'Server returned unexpected code {response.status_code}.')
            logger.error(f"Response text: {response.text()}")
            
            retval = response.status

        return retval, updated
    