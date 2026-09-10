''' Uses the DB API to pull data about local trains.
'''
from multiprocessing import context
import threading
import queue
import time
from playwright.sync_api import sync_playwright

from mylog import logger


class BahnBrowser:

    def __init__(self):

        self.requests = queue.Queue()

        self.thread = threading.Thread(
            target=self._worker,
            daemon=True
        )

        self.thread.start()


    def _worker(self):

        """
        This entire function runs in one thread.
        Playwright is created and used here only.
        """

        logger.debug("Starting Playwright worker")

        with sync_playwright() as p:

            browser = p.chromium.launch(
                channel="chrome",
                headless=True
            )

            context = browser.new_context(
                locale="de-DE",
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/153.0.0.0 Safari/537.36"
                ),
                extra_http_headers={
                    "sec-ch-ua-platform": '"macOS"',
                },
            )

            page = browser.new_page()

            logger.info(f"Playwright browser type: {p.chromium.name}")
            logger.info(f"Browser version: {browser.version}")

            browser_environment = page.evaluate("""
                () => ({
                    userAgent: navigator.userAgent,
                    webdriver: navigator.webdriver,
                    platform: navigator.platform,
                    languages: navigator.languages
                })
            """)

            logger.info(f"Browser environment: {browser_environment}")

            def log_request(request):
                if "bahn.de" in request.url:
                    logger.info(f"Bahn request: {request.method} {request.url}")
                    logger.info(f"Bahn request headers: {request.all_headers()}")

            def log_response(response):
                if "bahn.de" in response.url:
                    logger.info(f"Bahn response: {response.status} {response.url}")

            page.on("request", log_request)
            page.on("response", log_response)            

            logger.debug("Chrome ready")

            while True:

                request = self.requests.get()

                if request is None:
                    break

                url, result_queue = request

                try:

                    response = page.goto(
                        url,
                        wait_until="networkidle"
                    )

                    if response.status == 200:
                        result = response.json()
                    elif response.status == 403:
                        logger.error(f'Server returned 403 Forbidden')
                        logger.error(f"Response text: {response.text()}")

                        result = {
                            "error": response.status,
                            "body": response.text()
                        }
                    else:
                        logger.error(f'Server returned unexpected code {response.status}.')
                        logger.error(f"Response text: {response.text()}")

                        result = {
                            "error": response.status,
                            "body": response.text()
                        }

                except Exception as e:
                    logger.error(f'Exception reading train data: {e}')

                    result = {
                        "error": -1,
                        "body": str(e)
                    }

                result_queue.put(result)

            browser.close()


    def get(self, url):

        """
        Called by Flask threads.
        This function puts a request into the queue and waits for the result.

        The content will be a dictionary with the following keys:

        If the request was successful:
        - The JSON object returned by the server

        If the request failed:
        - error: The HTTP status code or -1 if there was an exception
        - body: The error message or response text

        """
        logger.debug(f"Fetching data from {url}")
        result_queue = queue.Queue()

        self.requests.put(
            (url, result_queue)
        )

        return result_queue.get()