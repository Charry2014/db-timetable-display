import requests
from datetime import datetime
from dataclasses import dataclass


class TransportAPI:
    # This site has bad IPv6 support. Turn it off.
    requests.packages.urllib3.util.connection.HAS_IPV6 = False

    @dataclass
    class CacheElement:
        data: requests.Response
        updated: datetime


    def __init__(self, cache_age_max=180):
        self.__cache = {}
        self.__cache_age_max = cache_age_max # seconds

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

    def communicate(self, url, default=None):
        '''Handle communication with the server - if the server responds 200 then all good.
        Otherwise it will attempt to find a value in the cache, or otherwise return a provided
        default value. If all that fails then we exit gracefully.
        '''
        response = requests.get(url)
        updated = datetime.strftime(datetime.now(), '%H:%M')

        if response.status_code == 200:
            response = response.json()
            self.__cache_response(url, response)
        else:
            cached = self.__get_cached_response(url)
            if cached is None:
                if default == None:
                    print(f'Server error code {response.status_code} and cache miss. Exiting.')
                    raise SystemExit(1)
                else:
                    response = default
            else:
                updated = datetime.strftime(cached.updated, '%H:%M')
                response = cached.data

        return response, updated


