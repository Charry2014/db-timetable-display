import os
from dataclasses import dataclass

BERLIN = "Europe/Berlin"


@dataclass(frozen=True)
class DbConfig:
    client_id: str
    api_key: str
    base_url: str = "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1"
    station_eva: str = "8006671"
    lookahead_minutes: int = 60
    lookahead_increment_minutes: int = 60
    max_lookahead_hours: int = 12
    trains_per_direction: int = 6
    changes_cache_seconds: int = 30
    request_timeout_seconds: int = 15

    @classmethod
    def from_env(cls):
        missing = [name for name in ("DB_CLIENT_ID", "DB_API_KEY") if not os.environ.get(name)]
        if missing:
            raise ValueError("Missing required environment variables: " + ", ".join(missing))
        return cls(
            client_id=os.environ["DB_CLIENT_ID"], api_key=os.environ["DB_API_KEY"],
            base_url=os.getenv("DB_TIMETABLE_BASE_URL", cls.base_url),
            station_eva=os.getenv("DB_STATION_EVA", cls.station_eva),
            lookahead_minutes=int(os.getenv("DB_LOOKAHEAD_MINUTES", cls.lookahead_minutes)),
            lookahead_increment_minutes=int(os.getenv("DB_LOOKAHEAD_INCREMENT_MINUTES", cls.lookahead_increment_minutes)),
            max_lookahead_hours=int(os.getenv("DB_MAX_LOOKAHEAD_HOURS", cls.max_lookahead_hours)),
            trains_per_direction=int(os.getenv("DB_TRAINS_PER_DIRECTION", cls.trains_per_direction)),
            changes_cache_seconds=int(os.getenv("DB_CHANGES_CACHE_SECONDS", cls.changes_cache_seconds)),
            request_timeout_seconds=int(os.getenv("DB_REQUEST_TIMEOUT_SECONDS", cls.request_timeout_seconds)),
        )

    def validate(self):
        if not self.client_id or not self.api_key:
            raise ValueError("DB_CLIENT_ID and DB_API_KEY are required")
        return self

    @staticmethod
    def direction_anchors():
        return {"towards_munich": "Baldham", "towards_grafing": "Eglharting"}
