import threading
import time


class PlanCache:
    def __init__(self, max_lookahead_hours=12):
        self._values = {}
        self._locks = {}
        self._guard = threading.Lock()
        self.max_lookahead_hours = max_lookahead_hours

    def get_or_fetch(self, eva, yymmdd, hour, fetch):
        key = (eva, yymmdd, hour)
        with self._guard:
            lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            if key not in self._values:
                self._values[key] = fetch()
            return self._values[key]

    def evict(self, current, eva=None):
        lower = current.replace(minute=0, second=0, microsecond=0) - __import__("datetime").timedelta(hours=1)
        upper = current.replace(minute=0, second=0, microsecond=0) + __import__("datetime").timedelta(hours=self.max_lookahead_hours)
        with self._guard:
            for key in list(self._values):
                if eva is not None and key[0] != eva:
                    continue
                try:
                    value = __import__("datetime").datetime.strptime(key[1] + "%02d" % key[2], "%y%m%d%H").replace(tzinfo=current.tzinfo)
                except ValueError:
                    continue
                if value < lower or value > upper:
                    self._values.pop(key, None)
                    self._locks.pop(key, None)


class ChangesCache:
    def __init__(self, ttl_seconds=30):
        self.ttl_seconds = ttl_seconds
        self._body = None
        self._fetched_at = 0
        self._not_before = 0
        self._lock = threading.Lock()

    def get_or_fetch(self, fetch, now=None):
        now = time.monotonic() if now is None else now
        with self._lock:
            if self._body is not None and now - self._fetched_at < self.ttl_seconds:
                return self._body
            if now < self._not_before and self._body is not None:
                return self._body
            try:
                body = fetch()
            except Exception as exc:
                retry = getattr(exc, "retry_after", None)
                if retry is not None:
                    try:
                        self._not_before = now + float(retry)
                    except ValueError:
                        self._not_before = now + self.ttl_seconds
                raise
            self._body, self._fetched_at, self._not_before = body, now, 0
            return body
