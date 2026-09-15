# Implementation Instructions: Migrate the Timetable Display to DB Timetables API

## 1. Objective

Replace the unsupported `bahn.de` web endpoint and its Playwright/macOS relay workaround with Deutsche Bahn's authenticated **Timetables API**.

The application needs only:

- departures from **Zorneding** (`EVA 8006671`);
- S-Bahn services in both directions;
- an initial look-ahead window of 60 minutes, extended in one-hour steps when necessary;
- six upcoming S-Bahn departures in each direction (twelve displayed records in total when available);
- planned and real-time departure times;
- planned and current platform;
- destination, line and cancellation status;
- JSON output in exactly the same schema, field names and value formats currently consumed by the application;
- updates only while the timetable page is visible.

Keep the implementation lightweight. It must not require Playwright, Chrome or browser emulation. Prefer the Python standard library unless the repository already has an appropriate HTTP/XML dependency.

## 2. Background and confirmed findings

The original application requested:

```text
https://www.bahn.de/web/api/reiseloesung/abfahrten?ortExtId=8006671&verkehrsMittel[]=SBAHN
```

Deutsche Bahn serves this private web endpoint through Akamai. Automated requests began returning:

```json
{"status":"ERROR","code":"OPS_BLOCKED","errorRefId":"..."}
```

The failure was reproduced with:

- `curl` from a Linux Docker container;
- Playwright/Chrome from Docker;
- `curl` and Playwright directly on the Proxmox Linux VM;
- matched Playwright and Chrome versions;
- browser headers, cookies, a loaded Bahn homepage and headed/headless configurations;
- the same LAN and public egress address as a working Mac;
- a native macOS relay, which initially worked but was subsequently blocked as well.

This demonstrates that changing browser fingerprints or moving the same private endpoint to macOS is not a durable solution. Do not add further anti-bot workarounds.

The replacement is DB's official authenticated Timetables API. It exposes planned station timetables separately from real-time changes.

## 3. Credentials and configuration

The operator must create an application in the DB API Marketplace, subscribe it to **Timetables**, and provide these environment variables:

```bash
export DB_CLIENT_ID='replace-with-client-id'
export DB_API_KEY='replace-with-api-key'
```

Do not commit real credentials. Provide an example file such as `db-env.example.sh`, and add the real file to `.gitignore`.

Recommended application configuration:

```text
DB_TIMETABLE_BASE_URL=https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1
DB_STATION_EVA=8006671
DB_LOOKAHEAD_MINUTES=60
DB_LOOKAHEAD_INCREMENT_MINUTES=60
DB_MAX_LOOKAHEAD_HOURS=12
DB_TRAINS_PER_DIRECTION=6
DB_CHANGES_CACHE_SECONDS=30
DB_REQUEST_TIMEOUT_SECONDS=15
```

Required request headers:

```text
DB-Client-Id: <DB_CLIENT_ID>
DB-Api-Key: <DB_API_KEY>
```

Never log either credential or complete request headers containing them.

## 4. API endpoints

Use:

```text
GET /plan/{evaNo}/{date}/{hour}
GET /fchg/{evaNo}
```

Where:

- `evaNo` is `8006671`;
- `date` uses `YYMMDD`;
- `hour` uses `HH` in local station time (`Europe/Berlin`).

Examples:

```bash
curl --fail --silent --show-error \
  -H "DB-Client-Id: ${DB_CLIENT_ID}" \
  -H "DB-Api-Key: ${DB_API_KEY}" \
  "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1/plan/8006671/260915/08"
```

```bash
curl --fail --silent --show-error \
  -H "DB-Client-Id: ${DB_CLIENT_ID}" \
  -H "DB-Api-Key: ${DB_API_KEY}" \
  "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1/fchg/8006671"
```

The API returns XML.

## 5. Meaning of the two feeds

### Planned timetable (`plan`)

The plan response is the authoritative list of scheduled stops for one station and one clock hour. It supplies the full base record, including service identity, scheduled departure, planned platform, planned route and destination.

### Full changes (`fchg`)

The change response is a sparse set of real-time updates. It is **not** a standalone departure board. A change record may contain only the attributes that changed and may omit service metadata entirely.

The supplied Zorneding change-feed sample confirms this:

- response size: approximately 55 KB;
- `<s>` stop records: 141;
- records containing `<dp>`: 43;
- records containing `<ar>`: 45;
- records containing `<tl>`: only 2;
- departure lines present: 34 `S6` and 9 `S4`;
- most departure records contain a changed time (`ct`) but omit full planned details.

Therefore, do not filter `fchg` by itself and do not replace a complete planned record with a sparse changed record. Fetch the plan and overlay the changes using the stop ID.

## 6. Relevant XML structure

A timetable contains stop records:

```xml
<timetable station="Zorneding" eva="8006671">
    <s id="unique-stop-id" eva="8006671">
        <tl c="S" n="..." />
        <ar ... />
        <dp ... />
    </s>
</timetable>
```

Relevant elements:

- `<s>`: one train's stop event at Zorneding;
- `<tl>`: trip/service metadata;
- `<dp>`: departure data;
- `<ar>`: arrival data, which is not needed for the board;
- `<m>`: messages and disruption information, not required for the first migration.

Relevant attributes:

| Information | Planned attribute | Changed attribute |
|---|---:|---:|
| Departure time | `dp.pt` | `dp.ct` |
| Platform | `dp.pp` | `dp.cp` |
| Destination | `dp.pde` | `dp.cde` |
| Route/path | `dp.ppth` | `dp.cpth` |
| Line designation | `dp.l` | `dp.l` |
| Cancellation status | — | `dp.cs` |

Times use this compact local-time format:

```text
YYMMDDHHMM
```

For example:

```text
2609150831 = 2026-09-15 08:31 Europe/Berlin
```

Use timezone-aware `datetime` values with `zoneinfo.ZoneInfo("Europe/Berlin")`. Do not interpret these values as UTC.

## 7. Adaptive fetch window

The first candidate window is:

```text
now <= effective departure time < now + 60 minutes
```

After merging and filtering the records, divide them into the two travel directions and count each direction separately. If either direction contains fewer than six departures, extend the end of the window by another hour, fetch any newly required plan hour, merge and filter again. Continue in one-hour increments until both directions contain at least six departures.

This is necessary because S-Bahn services stop for several hours overnight. The one-hour window is therefore only the initial search window, not a fixed output restriction.

Use this bounded algorithm:

```python
window_start = now
window_end = now + timedelta(hours=1)
maximum_end = now + timedelta(hours=12)

while True:
    fetch_any_missing_plan_hours(window_start, window_end)
    departures = merge_and_filter(window_start, window_end)
    by_direction = partition_by_direction(departures)

    if (
        len(by_direction.get("towards_munich", [])) >= 6
        and len(by_direction.get("towards_grafing", [])) >= 6
    ):
        break

    if window_end >= maximum_end:
        break

    window_end = min(window_end + timedelta(hours=1), maximum_end)
```

The 12-hour maximum prevents an unbounded sequence of API calls during a complete service suspension or when direction classification fails. Make it configurable. If six departures in each direction still cannot be found, return all valid departures found and log a warning containing the counts, but do not treat the response as a server error.

Fetch plan data for every clock hour touched by the expanding window. Also fetch the immediately preceding hour so that a heavily delayed train whose scheduled time has passed but whose changed departure remains in the search window can still be joined to its planned record.

At the first iteration this normally requires:

- previous hour;
- current hour;
- next hour.

Each later iteration should request only plan hours not already cached. Fetch `fchg` once for the overall refresh and reuse it throughout the expansion; do not fetch changes again for every added hour.

At day or year boundaries, derive each URL from a timezone-aware `datetime`; do not construct the previous/next date manually.

Plan responses should be cached by this key:

```text
(eva_number, local_date, local_hour)
```

They are effectively static base data. Do not download the same plan on every 30-second page update.

## 8. Merge algorithm

Parse the XML with `xml.etree.ElementTree` unless the existing project already uses another XML parser.

### Step 1: index planned stops

Combine the required hourly plan responses and create:

```python
planned_by_id: dict[str, PlannedStop]
```

The key is the exact `<s id>` string. Ignore planned records without `<dp>` because the display needs departures only.

### Step 2: index changes

Parse `fchg` and create:

```python
changes_by_id: dict[str, ChangedStop]
```

Again, key by the exact `<s id>`. A change record may lack `<tl>` or `<dp>` and must be treated as a partial patch.

### Step 3: overlay changed attributes

For each planned stop, find the corresponding changed stop. Preserve planned attributes and overwrite them only when the changed record supplies a value.

Conceptually:

```python
effective_dp = dict(planned_dp.attrib)

if changed_dp is not None:
    effective_dp.update(changed_dp.attrib)
```

Do not replace `planned_dp` wholesale with `changed_dp`.

Resolve important fields explicitly:

```python
scheduled_time = planned_dp.get("pt")
actual_time = changed_dp.get("ct") if changed_dp is not None else None
effective_time = actual_time or scheduled_time

scheduled_platform = planned_dp.get("pp")
actual_platform = changed_dp.get("cp") if changed_dp is not None else None

line = (
    changed_dp.get("l") if changed_dp is not None else None
) or planned_dp.get("l")

destination = (
    changed_dp.get("cde") if changed_dp is not None else None
) or planned_dp.get("pde")

cancelled = (
    changed_dp is not None
    and changed_dp.get("cs") == "c"
)
```

If the explicit destination is absent, fall back to the last entry in the changed path (`cpth`), then the last entry in the planned path (`ppth`). Paths are pipe-separated:

```python
def final_path_stop(path: str | None) -> str | None:
    if not path:
        return None
    stops = [part.strip() for part in path.split("|") if part.strip()]
    return stops[-1] if stops else None
```

Destination fallback order:

```text
cde → pde → final stop in cpth → final stop in ppth
```

Keep cancelled trains in the output and mark them as cancelled. A passenger-facing display should not silently make a scheduled train disappear.

### Step 4: calculate when the train will leave

For a given train, match the planned and change records using the exact `<s id="...">`. Read departure data only from `<dp>`; an `<ar>` element describes arrival at Zorneding and its `ct` must not be used as the departure time.

The definitive calculation available from these feeds is:

```text
original scheduled departure = plan.dp.pt
latest expected departure    = fchg.dp.ct, when present
                               otherwise plan.dp.pt
delay                         = latest expected departure
                                minus original scheduled departure
```

Example planned record:

```xml
<s id="train-123">
    <dp pt="2609150831" pp="3" l="S4" pde="Geltendorf"/>
</s>
```

Matching change record:

```xml
<s id="train-123">
    <dp ct="2609150837" cp="4" l="S4"/>
</s>
```

The resulting values are:

```text
Original scheduled departure: 08:31
Latest expected departure:     08:37
Delay:                          6 minutes
Effective platform:             4
```

Implement the selection explicitly:

```python
planned_dp = planned_stop.find("dp")
changed_dp = changed_stop.find("dp") if changed_stop is not None else None

scheduled_departure = parse_db_time(planned_dp.get("pt"))

if changed_dp is not None and changed_dp.get("ct"):
    expected_departure = parse_db_time(changed_dp.get("ct"))
else:
    expected_departure = scheduled_departure

delay_minutes = int(
    (expected_departure - scheduled_departure).total_seconds() / 60
)
```

Do not infer departure time from message timestamps such as `ts`, from the time at which the HTTP response was received, or from `ar.ct`. Only `dp.pt` and the matching `dp.ct` participate in the departure-time calculation.

Parse DB times as local German time. The compact format is `YYMMDDHHMM`:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")


def parse_db_time(value: str) -> datetime:
    return datetime.strptime(value, "%y%m%d%H%M").replace(tzinfo=BERLIN)
```

Format the values for the existing JSON contract without adding a timezone suffix, matching the old response:

```python
def format_existing_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S")
```

Map the result as follows:

```text
zeit   = formatted plan.dp.pt
ezZeit = formatted fchg.dp.ct, or zeit when no changed departure exists
delay  = whole-minute difference between ezZeit and zeit
gleis  = fchg.dp.cp, or plan.dp.pp when no changed platform exists
```

Decision cases:

| Available data | Meaning and output |
|---|---|
| No matching `fchg` stop | No current departure-time change: set `ezZeit = zeit` and delay to zero |
| Matching stop but no `dp.ct` | Something else may have changed; retain `plan.dp.pt` as the expected departure |
| Matching `dp.ct` | Use it as the latest DB expected departure from Zorneding |
| Only `ar.ct` | Arrival change only; do not use it for departure |
| `dp.cs="c"` | Departure is cancelled; retain its time for ordering/display but mark it cancelled |
| Expected time earlier than planned | Preserve the calculated negative value if the current contract supports it; otherwise apply the existing application's established handling rather than inventing new behavior |

The word **expected** is important. `dp.ct` is DB's latest changed or predicted departure time, not a guarantee of the precise physical moment the train will leave. For a future, non-cancelled train, it is the best available answer. For a cancelled train there is no meaningful “will leave” time, even though its scheduled or changed time remains useful for display.

## 9. Filtering and direction classification

Apply filters after merging, in this order:

1. Record has a planned `<dp>`.
2. Line is an S-Bahn line.
3. Effective departure time can be parsed.
4. Effective departure is inside the current adaptive search window.
5. De-duplicate by `<s id>`.
6. Classify the direction.
7. Sort each direction by effective departure time, then line.
8. After the adaptive search finds enough records, retain the first six records in each direction.

Recommended S-Bahn test:

```python
import re

is_s_bahn = bool(line and re.fullmatch(r"S\s*\d+[A-Za-z]?", line.strip()))
```

This accepts examples such as `S4`, `S6` and `S 4`, while excluding unrelated train categories. If DB supplies an S-Bahn service without `dp.l`, use `<tl c="S">` as the fallback category test.

The line number does not identify direction. For Zorneding, classify direction from the downstream route after departure:

| Direction key | Meaning | Adjacent downstream station |
|---|---|---|
| `towards_munich` | Westbound towards Munich | `Baldham` |
| `towards_grafing` | Eastbound towards Grafing/Ebersberg | `Eglharting` |

Build the effective path from `cpth` when present, otherwise `ppth`. Split it on `|` and inspect the downstream stops. Prefer the adjacent-station anchors above over the final destination because terminal destinations can change between timetable periods.

```python
def classify_direction(changed_path: str | None,
                       planned_path: str | None) -> str | None:
    path = changed_path or planned_path
    stops = [part.strip() for part in (path or "").split("|") if part.strip()]

    if "Baldham" in stops:
        return "towards_munich"
    if "Eglharting" in stops:
        return "towards_grafing"
    return None
```

If neither anchor is present, optionally use a small, explicitly configured destination fallback map. Do not guess direction from platform number or line number. Log unclassified records without counting them towards either target.

The final response should contain at most the earliest six records in each direction. A direction that reaches six early must not prevent the window expanding for the other direction. Extra records found in the already-complete direction are discarded only after the other direction also reaches six or the safety limit is reached.

Cancelled departures remain visible and count as records towards the six displayed entries. This preserves important passenger information and guarantees a stable maximum of six rows per direction. If the product requirement later changes to six non-cancelled services plus cancellations, implement that as a separate explicit rule.

## 10. Backward-compatible JSON output

This is a strict compatibility requirement: **the output of the new XML processing pipeline must be JSON in the same format currently returned to and consumed by the rest of the application**. Replacing the DB data source must not require changes to the existing web routes, templates, JavaScript, display logic or downstream processing.

Before implementing the mapper, inspect the current producer and every consumer of the existing departure JSON. Capture a representative response as a regression-test fixture. That fixture—not a newly invented schema—is the authoritative output contract. Preserve:

- the top-level object shape, including the `entries` array;
- all field names and nesting;
- whether absent values are omitted, `null`, empty strings or empty arrays;
- timestamp formatting;
- platform and delay value types;
- ordering assumptions used by the display;
- the existing error response contract.

Each emitted train entry must provide the existing application with, at minimum:

- the destination of the train;
- the effective/expected departure time from Zorneding;
- the original scheduled departure time from Zorneding;
- the delay in minutes;
- the line/service identification required by the current display;
- the effective platform and any cancellation state already handled by the current code.

The private Bahn endpoint used fields including:

| Existing JSON field | Required value from Timetables data |
|---|---|
| `bahnhofsId` | Station EVA number, always `8006671` for this deployment |
| `zeit` | Original planned Zorneding departure from `dp.pt` |
| `ezZeit` | Effective Zorneding departure: `dp.ct` when present, otherwise `dp.pt` |
| `terminus` | Effective destination: `cde`, then `pde`, then the path fallback |
| `gleis` | Effective platform: `cp` when present, otherwise `pp` |
| `journeyId` | Stable stop/journey identity derived from the DB `<s id>` |
| `ueber` | Effective path split into a JSON array when the current application uses it |
| `verkehrmittel` | Existing nested service/line object reconstructed from `<tl>` and `dp.l` |
| `meldungen` | Existing message array; at minimum represent cancellation consistently with current behavior |

The existing format distinguishes the original time from the expected time:

```text
zeit   = original scheduled departure
ezZeit = current expected departure, or zeit when there is no changed time
```

Calculate delay from those two values rather than trusting a separate upstream delay field:

```python
delay_minutes = int((effective_time - scheduled_time).total_seconds() / 60)
```

Use the exact delay key and type already expected by the repository. If the current backend returns a delay field, populate that field with the calculated whole-minute value. If the current frontend derives delay from `ezZeit - zeit`, continue supplying both timestamps in precisely the existing format and preserve that derivation. Do not introduce a second, competing delay representation.

A representative compatibility entry is conceptually:

```json
{
  "bahnhofsId": "8006671",
  "zeit": "2026-09-15T08:31:00",
  "ezZeit": "2026-09-15T08:34:00",
  "gleis": "3",
  "journeyId": "unique-stop-id",
  "ueber": ["Baldham", "Vaterstetten", "Haar"],
  "verkehrmittel": {
    "name": "S4",
    "kurzText": "S",
    "mittelText": "S4",
    "langText": "S4",
    "produktGattung": "SBAHN"
  },
  "terminus": "Geltendorf",
  "delay": 3,
  "meldungen": []
}
```

The agent must adjust this example to the repository's exact current contract if its delay key, transport object or message representation differs. Compatibility with the checked-in consumers takes precedence over the illustrative values above.

### Internal normalized representation

The implementation may use a clearer normalized record internally, but this object must remain behind the compatibility mapper and must not become the externally returned schema.

Use an internal normalized record similar to:

```json
{
  "id": "unique-stop-id",
  "stationEva": "8006671",
  "line": "S4",
  "direction": "towards_munich",
  "destination": "Geltendorf",
  "scheduledTime": "2026-09-15T08:31:00+02:00",
  "actualTime": "2026-09-15T08:34:00+02:00",
  "effectiveTime": "2026-09-15T08:34:00+02:00",
  "scheduledPlatform": "3",
  "actualPlatform": "4",
  "effectivePlatform": "4",
  "cancelled": false
}
```

Rules:

```text
effectiveTime = actualTime or scheduledTime
effectivePlatform = actualPlatform or scheduledPlatform
```

Map every normalized record back into the existing application-facing JSON before returning it. No consumer outside the new DB adapter should need to understand Timetables XML or the normalized internal field names.

Do not leak raw DB credentials, request headers or unnecessarily large XML fragments through the application's response or logs.

## 11. Application components

Keep responsibilities separate:

### `DbTimetableClient`

- Reads credentials and base URL from configuration.
- Performs authenticated HTTP GET requests.
- Applies a connection/read timeout.
- Returns response bytes or parsed XML.
- Does not contain display-specific filtering.

### `PlanCache`

- Caches plan responses by station/date/hour.
- Prevents simultaneous duplicate requests for the same key.
- Expires old hours after they can no longer contribute delayed departures.

### `TimetableMerger`

- Parses plan and change XML.
- Joins records by `<s id>`.
- Applies changed attributes as sparse patches.
- Produces normalized departure records.

### `DepartureService`

- Starts with a one-hour window in `Europe/Berlin` and expands it in one-hour steps.
- Requests only missing plan hours and reuses one current-change response per refresh.
- Filters and partitions S-Bahn departures by direction.
- Stops expanding when each direction has six records or the configured safety limit is reached.
- Returns at most the first six departures in each direction.
- Sorts and maps the result into the existing response contract.
- Maintains last-known-good output.

## 12. Refresh, caching and concurrency

Retain the existing behavior in which the browser requests updates only while the page is visible.

Server-side behavior:

- Cache `fchg` for at least 30 seconds.
- Cache plan responses per station/date/hour.
- Use a lock or single-flight mechanism so concurrent web requests share one upstream refresh.
- Never let each browser client independently trigger its own DB request when a sufficiently fresh server-side result exists.
- Make no periodic background requests when there are no page-driven updates.
- Keep and serve the last successful normalized response if a temporary upstream failure occurs.
- Include internal freshness metadata in logs or metrics, not necessarily in the public response.
- Cache every additional plan hour fetched during overnight window expansion.

The API allowance is 60 calls per minute. This design normally performs no more than one change request per 30 seconds while active, plus occasional cached plan requests.

## 13. HTTP and error handling

Use a finite timeout, recommended 15 seconds.

Handle failures as follows:

| Condition | Behavior |
|---|---|
| HTTP 200 and valid XML | Parse and update cache |
| Timeout/network error | Log concise error; serve last-known-good data if available |
| HTTP 401/403 | Treat as configuration/authentication failure; do not retry immediately |
| HTTP 429 | Respect `Retry-After`; retain cached data |
| HTTP 5xx | Apply bounded exponential backoff; retain cached data |
| Malformed XML | Reject refresh; retain previous cache |
| Empty legitimate result | Return an empty departure list, not an error |

Never turn one page refresh into a tight retry loop.

At application startup, fail clearly if either `DB_CLIENT_ID` or `DB_API_KEY` is absent. Do not print their values.

## 14. Dependencies and container changes

The official API works from Linux and Docker and does not require a browser fingerprint.

Preferred implementation:

- HTTP: existing project HTTP client, or `urllib.request` from the standard library;
- XML: `xml.etree.ElementTree`;
- timezone: `zoneinfo` on Python 3.9+;
- JSON: standard `json` module.

After the official implementation passes its acceptance tests:

- remove Playwright from `requirements.txt` if nothing else uses it;
- remove Google Chrome installation from the Dockerfile;
- remove Xvfb and `xvfb-run` if nothing else uses them;
- remove the Playwright worker thread and browser lifecycle code;
- remove the Mac Mini relay from the production path;
- retain unrelated user changes in the repository.

Do not combine dependency cleanup with the first functional commit unless the existing test suite makes the change low-risk. A staged migration is easier to diagnose and revert.

## 15. Tests

All parsing and merge tests must use saved XML fixtures; unit tests must not call DB.

Create at least these fixtures:

- planned timetable with S4 and S6 departures in both directions;
- matching `fchg` records with changed times;
- platform change;
- cancellation;
- sparse change without `<tl>`;
- unrelated arrival-only record;
- non-S-Bahn departure;
- unchanged planned departure;
- train scheduled in the preceding hour but delayed into the result window;
- overnight gap requiring several one-hour expansions;
- one direction reaching six departures before the other;
- unclassifiable S-Bahn route without either adjacent-station anchor;
- window crossing midnight and a year boundary;
- duplicate stop IDs across combined plan responses.

Required unit tests:

1. Planned and changed records join by exact `<s id>`.
2. Missing fields in `fchg` do not erase planned values.
3. `ct` overrides `pt` for effective time.
4. `cp` overrides `pp` for effective platform.
5. `cde` overrides `pde` for destination.
6. Path fallback derives the final destination correctly.
7. Arrival-only records are excluded.
8. Non-S-Bahn departures are excluded.
9. Direction classification uses `Baldham` for `towards_munich` and `Eglharting` for `towards_grafing`.
10. The initial one-hour window is sufficient when it contains at least six records in each direction.
11. The window expands by exactly one hour while either direction has fewer than six records.
12. Expansion stops only when both directions have six records or the maximum look-ahead is reached.
13. A direction that already has six records does not stop expansion for the other direction.
14. Only newly required, uncached plan hours are fetched during expansion.
15. `fchg` is fetched only once per refresh, not once per expansion step.
16. The final result contains no more than six records per direction.
17. The time calculations use `Europe/Berlin` and handle overnight, date, year and daylight-saving transitions.
18. Cancelled services remain present, are marked cancelled and count as displayed records.
19. Unclassified records are logged and do not count towards either direction.
20. Results are sorted by effective departure time within each direction.
21. Concurrent callers produce only one upstream change request.
22. Upstream failure returns last-known-good data when available.
23. Credentials never appear in logs.
24. A contract test proves that the new adapter returns the existing top-level JSON structure and entry field names.
25. `zeit` contains the original scheduled departure and `ezZeit` contains the changed departure or falls back to `zeit`.
26. The reported delay equals the whole-minute difference between the effective and scheduled departure times.
27. Existing frontend/display code passes unchanged against the new adapter output.

## 16. Acceptance criteria

The migration is complete when:

- the application runs in its normal Linux Docker container without Chrome or Playwright;
- the only DB requests use the authenticated Timetables API;
- the search begins with the coming hour and expands in one-hour steps when required;
- the displayed result contains the earliest six Zorneding S-Bahn departures in each direction when available;
- overnight service gaps are handled without polling or an unbounded request loop;
- delays, platform changes and cancellations are applied correctly;
- the adapter emits the same JSON contract as the old data path, including destination, scheduled time, expected departure time and delay;
- the existing application outside the data-source adapter remains unchanged;
- page-driven 30-second updates do not cause duplicate concurrent upstream calls;
- no requests are made while the display is inactive;
- a temporary DB failure leaves the last successful timetable visible;
- automated tests cover XML parsing, sparse merge behavior, filtering and caching;
- credentials are provided through the deployment environment and are absent from Git and logs.

## 17. Suggested implementation order

1. Inspect the existing departure-data consumer and document its required response fields.
2. Add configuration and authenticated API client.
3. Add XML fixtures and parsers for `plan` and `fchg`.
4. Implement sparse merge by stop ID.
5. Implement Europe/Berlin adaptive time-window, S-Bahn filtering and Zorneding direction classification.
6. Capture the existing JSON contract as a fixture and map normalized records into that exact response schema.
7. Add a contract test that exercises the existing consumer unchanged with the new adapter output.
8. Add plan/change caching, single-flight protection and last-known-good behavior.
9. Route the existing page-visible update path through the new service.
10. Verify live data for Zorneding from inside the deployed Docker container.
11. Remove the obsolete Playwright, Chrome and Mac-relay components in a separate cleanup step.

## 18. Non-goals

The first migration does not need to:

- reproduce every field returned by the private `bahn.de` web API;
- process arrivals;
- display every disruption message in `<m>`;
- support arbitrary stations or transport categories;
- implement route planning or ticket information;
- attempt to bypass Akamai or imitate a human browser.

Keep the first version narrowly focused on a reliable Zorneding S-Bahn departure board.
