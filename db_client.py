from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DbError(Exception):
    code = -1


class DbAuthError(DbError):
    def __init__(self, message="DB API authentication failed", code=401):
        super().__init__(message)
        self.code = code


class DbRateLimited(DbError):
    code = 429
    def __init__(self, message="Rate limited", retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


class DbServerError(DbError):
    def __init__(self, message="DB API server error", code=502):
        super().__init__(message)
        self.code = code


class DbUnavailable(DbError):
    code = -1


class DbBadXml(DbError):
    code = -1


class DbTimetableClient:
    def __init__(self, config):
        self.config = config.validate()

    def _get(self, path):
        request = Request(self.config.base_url.rstrip("/") + "/" + path, headers={
            "DB-Client-Id": self.config.client_id,
            "DB-Api-Key": self.config.api_key,
            "Accept": "application/xml",
        })
        try:
            with urlopen(request, timeout=self.config.request_timeout_seconds) as response:
                return response.read()
        except HTTPError as exc:
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            if exc.code in (401, 403):
                raise DbAuthError("DB API authentication failed", exc.code) from exc
            if exc.code == 429:
                raise DbRateLimited("DB API rate limit", retry_after) from exc
            if exc.code >= 500:
                raise DbServerError("DB API server error", exc.code) from exc
            raise DbUnavailable("DB API request failed") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise DbUnavailable("DB API unavailable") from exc

    def fetch_plan(self, eva, yymmdd, hour):
        return self._get(f"plan/{eva}/{yymmdd}/{hour:02d}")

    def fetch_changes(self, eva):
        return self._get(f"fchg/{eva}")
