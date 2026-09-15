import threading
from datetime import datetime, timedelta
from time import monotonic

from db_client import DbBadXml, DbError, DbRateLimited, DbTimetableClient
from db_config import DbConfig
from mylog import logger
from plan_cache import ChangesCache, PlanCache
from timetable_merger import BERLIN, TimetableMerger, format_existing_time


class DepartureService:
    def __init__(self, config, client, plan_cache=None, changes_cache=None, now_fn=None, log=logger):
        self.config = config
        self.client = client
        self.plan_cache = plan_cache or PlanCache(config.max_lookahead_hours)
        self.changes_cache = changes_cache or ChangesCache(config.changes_cache_seconds)
        self.now_fn = now_fn or (lambda: datetime.now(BERLIN))
        self.log = log
        self._refresh_lock = threading.Lock()
        self._last_good = None
        self._merger = TimetableMerger()

    @classmethod
    def from_env(cls):
        config = DbConfig.from_env()
        return cls(config, DbTimetableClient(config))

    def _plan_hours(self, start, end):
        hour = start.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        last = end.replace(minute=0, second=0, microsecond=0)
        while hour <= last:
            yield hour
            hour += timedelta(hours=1)

    def _error(self, exc):
        code = getattr(exc, "code", -1)
        if isinstance(exc, DbRateLimited):
            body = "DB API rate limited"
        elif isinstance(exc, DbError):
            body = str(exc)
        else:
            body = str(exc)
        return {"error": code, "body": body}

    def _refresh(self, start):
        end = start + timedelta(minutes=self.config.lookahead_minutes)
        maximum = start + timedelta(hours=self.config.max_lookahead_hours)
        changes = self.changes_cache.get_or_fetch(lambda: self.client.fetch_changes(self.config.station_eva))
        plans = {}
        while True:
            self.plan_cache.evict(start, self.config.station_eva)
            for hour in self._plan_hours(start, end):
                key = (self.config.station_eva, hour.strftime("%y%m%d"), hour.hour)
                if key not in plans:
                    plans[key] = self.plan_cache.get_or_fetch(
                        *key, fetch=lambda h=hour: self.client.fetch_plan(self.config.station_eva, h.strftime("%y%m%d"), h.hour)
                    )
            try:
                records = self._merger.merge(list(plans.values()), changes, self.config.station_eva)
            except Exception as exc:
                if isinstance(exc, DbError):
                    raise
                raise DbBadXml("DB API returned malformed XML") from exc
            selected = {"towards_munich": [], "towards_grafing": []}
            unclassified = 0
            for record in records:
                if record.direction is None:
                    unclassified += 1
                    continue
                if start <= record.effective_time < end:
                    selected[record.direction].append(record)
            if unclassified:
                self.log.debug("Ignored {} S-Bahn departures without a direction anchor", unclassified)
            if all(len(values) >= self.config.trains_per_direction for values in selected.values()) or end >= maximum:
                break
            end = min(end + timedelta(minutes=self.config.lookahead_increment_minutes), maximum)
        for direction in selected:
            selected[direction].sort(key=lambda item: (item.effective_time, item.line))
            selected[direction] = selected[direction][:self.config.trains_per_direction]
        counts = {key: len(value) for key, value in selected.items()}
        if any(value < self.config.trains_per_direction for value in counts.values()):
            self.log.warning("Departure window reached limit: {}", counts)
        entries = [self.to_entry(record) for values in selected.values() for record in values]
        return {"entries": entries}

    def get_departures(self):
        with self._refresh_lock:
            try:
                result = self._refresh(self.now_fn())
                self._last_good = result
                return result
            except Exception as exc:
                self.log.error("Departure refresh failed: {}", exc)
                return self._last_good if self._last_good is not None else self._error(exc)

    def to_entry(self, record):
        return {
            "bahnhofsId": record.station_eva,
            "zeit": format_existing_time(record.scheduled_time),
            "ezZeit": format_existing_time(record.effective_time),
            "gleis": record.effective_platform,
            "journeyId": record.id,
            "ueber": record.path,
            "verkehrmittel": {"name": record.line, "kurzText": "S", "mittelText": record.line, "langText": record.line, "produktGattung": "SBAHN"},
            "terminus": record.destination,
            "meldungen": [{"code": "c", "text": "Fahrt entfällt"}] if record.cancelled else [],
        }
