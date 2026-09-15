import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

BERLIN = ZoneInfo("Europe/Berlin")


def parse_db_time(value):
    return datetime.strptime(value, "%y%m%d%H%M").replace(tzinfo=BERLIN)


def format_existing_time(value):
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def final_path_stop(path):
    if not path:
        return None
    stops = [part.strip() for part in path.split("|") if part.strip()]
    return stops[-1] if stops else None


def classify_direction(changed_path, planned_path):
    for path in (changed_path, planned_path):
        stops = [part.strip() for part in (path or "").split("|") if part.strip()]
        if "Baldham" in stops:
            return "towards_munich"
        if "Eglharting" in stops:
            return "towards_grafing"
    return None


def is_s_bahn(line, category=None):
    if line and re.fullmatch(r"S\s*\d+[A-Za-z]?", line.strip()):
        return True
    return category == "S"


@dataclass(frozen=True)
class NormalizedDeparture:
    id: str
    station_eva: str
    line: str
    category: str
    direction: str
    destination: str
    scheduled_time: datetime
    actual_time: Optional[datetime]
    effective_time: datetime
    scheduled_platform: Optional[str]
    actual_platform: Optional[str]
    effective_platform: Optional[str]
    cancelled: bool
    path: Optional[str]


class TimetableMerger:
    def merge(self, plan_docs, changes_doc, station_eva=None):
        planned = {}
        for document in plan_docs:
            root = ET.fromstring(document)
            for stop in root.findall(".//s"):
                departure = stop.find("dp")
                if departure is not None and stop.get("id") and stop.get("id") not in planned:
                    planned[stop.get("id")] = (stop, departure)
        changes = {}
        if changes_doc:
            root = ET.fromstring(changes_doc)
            for stop in root.findall(".//s"):
                if stop.get("id"):
                    changes[stop.get("id")] = stop
        result = []
        for stop_id, (planned_stop, planned_dp) in planned.items():
            changed_stop = changes.get(stop_id)
            changed_dp = changed_stop.find("dp") if changed_stop is not None else None
            pt = planned_dp.get("pt")
            if not pt:
                continue
            try:
                scheduled = parse_db_time(pt)
            except (TypeError, ValueError):
                continue
            ct = changed_dp.get("ct") if changed_dp is not None else None
            try:
                actual = parse_db_time(ct) if ct else None
            except (TypeError, ValueError):
                actual = None
            effective = actual or scheduled
            path = ((changed_dp.get("cpth") if changed_dp is not None else None) or planned_dp.get("ppth"))
            destination = ((changed_dp.get("cde") if changed_dp is not None else None) or planned_dp.get("pde") or final_path_stop(changed_dp.get("cpth") if changed_dp is not None else None) or final_path_stop(planned_dp.get("ppth")) or "")
            line = ((changed_dp.get("l") if changed_dp is not None else None) or planned_dp.get("l") or "").strip()
            tl = planned_stop.find("tl")
            category = (tl.get("c") if tl is not None else "")
            if changed_stop is not None and changed_stop.find("tl") is not None:
                category = changed_stop.find("tl").get("c") or category
            if not is_s_bahn(line, category):
                continue
            direction = classify_direction(changed_dp.get("cpth") if changed_dp is not None else None, planned_dp.get("ppth"))
            planned_platform = planned_dp.get("pp")
            actual_platform = changed_dp.get("cp") if changed_dp is not None else None
            result.append(NormalizedDeparture(stop_id, station_eva or root.get("eva", ""), line, category, direction, destination, scheduled, actual, effective, planned_platform, actual_platform, actual_platform or planned_platform, changed_dp is not None and changed_dp.get("cs") == "c", path))
        return result
