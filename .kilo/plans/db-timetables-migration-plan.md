# Plan: Migrate the data pull to the DB Timetables API

Source of truth for behavior: `DB-Timetables-API-Migration-Instructions.md` (sections referenced below as §).

## Goal

Replace the current data path (`trains.py` → `bahnrelay` on the Mac Mini → private `bahn.de` web endpoint) with DB's authenticated Timetables API (`/plan/{eva}/{date}/{hour}` + `/fchg/{eva}`), parsed from XML with the standard library, while keeping the application's JSON contract, routes, template, and JavaScript unchanged. No Playwright, Chrome, browser emulation, or further anti-bot workarounds (§2, §14).

The operator outcome: the board shows the earliest six Zorneding S-Bahn departures per direction (adaptive window, 60 min initial, one-hour steps, 12-hour cap), with planned vs. expected times, platform changes, and cancellations — driven by page-visible polling only.

## Current-state diagnosis

- `trains.py` fetches `http://10.0.0.204:8765/departures?station=8006671` via `fetch_departures()` (stdlib `urllib`, 30s timeout) and hands the parsed JSON to `process_departures()`. On failure it returns `{"error": <code>, "body": <text>}`.
- `departures.py::process_departures` is the sole consumer of the upstream JSON. Its actual reads per entry (`departures.py:62-67`, `departures.py:96`):
  - `verkehrmittel.produktGattung` — must equal `"SBAHN"` or the entry is skipped;
  - `zeit` — planned departure, parsed with `strptime('%Y-%m-%dT%H:%M:%S')`;
  - `ezZeit` — effective departure, parsed with `datetime.fromisoformat`;
  - `terminus` — destination; east partition uses exact names `['Ebersberg(Oberbay)', 'Grafing Bahnhof']`, everything else is west;
  - it derives `delay` itself as whole minutes from `ezZeit − zeit` — **no delay key exists in entries**;
  - it caps at 20 rows total and sorts by minutes-remaining.
- The frontend payload keys are `timestamp`, `direction1_title`, `direction2_title`, `trains_east`, `trains_west`, rows are 5-tuples. `trains.html` never re-renders platform; entries keys `gleis`, `journeyId`, `meldungen`, `ueber`, `bahnhofsId` are part of the upstream contract but unread today.
- Playwright/Chrome are already gone from requirements and the Dockerfile (previous migration). The only legacy piece left is the Mac Mini relay (`macmini/bahnrelay.py`), excluded from the image via `.dockerignore`.
- `.gitignore` already ignores `env.sh` and `secrets.py`; there is no committed credential.
- Python in the venv is 3.9 (local) and 3.12 (Ubuntu 24.04 image) — `zoneinfo` is stdlib on both.

## Target design

**The new adapter emits the existing relay-shaped JSON** — `{"entries": [...]}` with the documented field set — and `process_departures` stays untouched. This satisfies §10's strict compatibility rule with the smallest possible diff: web routes, template, JS, and display logic unchanged; `trains.update()` swaps one call.

Internal pipeline (§11 component names → new flat modules, matching the repo's flat style):

| Component | File | Responsibility |
|---|---|---|
| config | `db_config.py` | env reading, defaults, fail-fast validation (no secret values printed) |
| `DbTimetableClient` | `db_client.py` | authenticated GETs, timeout, typed HTTP errors, no display logic |
| `PlanCache` + changes cache | `plan_cache.py` | plan keyed `(eva, yymmdd, hour)` with per-key single-flight and eviction; `fchg` 30s TTL, single-flight, Retry-After/backoff state |
| `TimetableMerger` | `timetable_merger.py` | ElementTree parsing, join by exact `<s id>`, sparse overlay, normalized records, direction classification |
| `DepartureService` | `departure_service.py` | adaptive window, one `fchg` per refresh, filters, ≤6 per direction, last-known-good, compatibility mapping |

`macmini/bahnrelay.py` stays in place but out of the production path until live verification passes, then retires to `deprecated/` in a separate cleanup commit (§14, §17 step 11).

## Planned file changes

### 1. Credentials and configuration

- **`db-env.example.sh`** (new): `export DB_CLIENT_ID='replace-with-client-id'`, `export DB_API_KEY='replace-with-api-key'`, plus the optional overrides from §3 with their defaults.
- **`.gitignore`**: add `db-env.sh` (real credentials file).
- **`.dockerignore`**: add `db-env*.sh` and `.env*` so credentials can never enter the image.
- **`docker-compose.yml`**: add `environment: DB_CLIENT_ID=${DB_CLIENT_ID}` and `DB_API_KEY=${DB_API_KEY}` (compose interpolation from the host shell). Document: `set -a && source db-env.sh && set +a` before `docker compose up -d --build`. Compose `env_file` cannot parse `export`-style files, hence interpolation.
- **`db_config.py`** (new): dataclass `DbConfig` with `from_env()`: `client_id`, `api_key`, `base_url` (default `https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1`), `station_eva` (`"8006671"`), `lookahead_minutes` (60), `lookahead_increment_minutes` (60), `max_lookahead_hours` (12), `trains_per_direction` (6), `changes_cache_seconds` (30), `request_timeout_seconds` (15). `validate()` raises naming the missing variable names only.

### 2. `db_client.py` (new)

`DbTimetableClient(config)`:
- `fetch_plan(eva, yymmdd, hour) -> bytes` → `GET {base_url}/plan/{eva}/{yymmdd}/{hour}`;
- `fetch_changes(eva) -> bytes` → `GET {base_url}/fchg/{eva}`;
- headers `DB-Client-Id`, `DB-Api-Key` from config; `urllib.request`, timeout from config;
- typed failures for §13: `DbAuthError` (401/403), `DbRateLimited` (429, carries `Retry-After`), `DbServerError` (5xx), `DbUnavailable` (timeout/network), `DbBadXml` (caller-side, non-XML body);
- never logs credentials or full headers; date/hour parameters are always derived from timezone-aware datetimes (§7 day/year boundary rule).

### 3. `plan_cache.py` (new)

- `PlanCache.get_or_fetch(eva, yymmdd, hour, fetch)`: per-key `threading.Lock` so concurrent requests for the same hour share one upstream call (§12 single-flight).
- Eviction: keep hours from `(current_berlin_hour − 1)` through `current + max_lookahead_hours`; drop the rest each refresh so the previous-hour plan needed for delayed joins survives exactly as long as it can contribute (§7, §11).
- `ChangesCache`: 30s TTL (config), single shared lock, honors `Retry-After` by refusing refetch until `not_before`; exposes the cached body even while backoff is active.

### 4. `timetable_merger.py` (new)

- `parse_db_time(value) -> datetime` — `strptime('%y%m%d%H%M').replace(tzinfo=ZoneInfo("Europe/Berlin"))` (§8; wall-clock semantics, `fold=0`).
- `format_existing_time(dt) -> str` — `strftime('%Y-%m-%dT%H:%M:%S')`, no timezone suffix, matching the old relay strings exactly.
- `TimetableMerger.merge(plan_docs, changes_doc) -> list[NormalizedDeparture]`:
  1. index planned stops by exact `<s id>` from all plan docs; skip records without `<dp>`;
  2. index change stops by exact `<s id>`; treat as sparse patches (a change record may lack `<tl>`/`<dp>`);
  3. overlay: `effective_dp = dict(planned_dp.attrib)` then `update(changed_dp.attrib)` — never wholesale replacement (§8 step 3);
  4. resolve explicitly: `ct`→effective time else `pt`; `cp`→effective platform else `pp`; line `changed dp.l` else `planned dp.l`; destination fallback chain `cde → pde → last stop of cpth → last stop of ppth` (pipe-split, strip, last non-empty); `cancelled = changed_dp is not None and changed_dp.get("cs") == "c"`;
  5. de-duplicate by `<s id>` across combined plan responses;
  6. never read `ar.ct`, `m`, or message timestamps for departure times.
- `NormalizedDeparture` dataclass: `id, station_eva, line, category, direction, destination, scheduled_time, actual_time, effective_time, scheduled_platform, actual_platform, effective_platform, cancelled, path` (§10 internal representation).
- `classify_direction(changed_path, planned_path)`: split effective path on `|`; `Baldham` → `towards_munich`, `Eglharting` → `towards_grafing`, else `None` (§9 anchors; anchors live as named constants in `db_config.py` alongside an optional empty destination-fallback map).
- `is_s_bahn(line, category)`: `re.fullmatch(r"S\s*\d+[A-Za-z]?", line.strip())`, fallback `<tl c="S">` when `dp.l` is absent (§9).

### 5. `departure_service.py` (new)

`DepartureService(config, client, plan_cache, changes_cache, now_fn=..., log=...)` — injectable clock/client for tests (§15: no live DB in tests):

- `get_departures()` — called by `trains.update()`; thread-safe:
  - if the changes cache is fresh, return the cached response immediately (page-driven 30s updates never duplicate upstream calls, §12);
  - otherwise take one refresh lock (single-flight for all waiters), refresh, swap `self._last_good`, return it;
  - on any upstream failure: log concise error, return `self._last_good` if present; if none exists (first boot), return `{"error": <code>, "body": <message>}` so the existing Error row renders.
- Refresh algorithm (§7): `window_start = now(Berlin)`, `window_end = start + 1h`, cap `start + max_lookahead_hours`. Fetch `fchg` once. Plan hours = `hour(start − 1h)` … `hour(window_end)` inclusive, only keys not cached. Merge → filter (§9 order: has `<dp>` → S-Bahn → parseable effective time → inside `[start, window_end)` → dedupe) → partition → expand `window_end += 1h` until both directions ≥ 6 or cap. If the cap is hit without 6+6: return what was found and log a warning with the per-direction counts — not an error (§7).
- Sort each direction by `(effective_time, line)`, keep the first `trains_per_direction` per direction (§9); cancelled records stay and count toward the six.
- Unclassified records: logged, excluded from both counts (§9).
- Compatibility mapper `to_entry(norm) -> dict` — the §10 table instantiated against this repo's real contract:
  ```python
  {
      "bahnhofsId": config.station_eva,
      "zeit": format_existing_time(norm.scheduled_time),
      "ezZeit": format_existing_time(norm.effective_time),
      "gleis": norm.effective_platform,
      "journeyId": norm.id,
      "ueber": norm.path,
      "verkehrmittel": {
          "name": norm.line, "kurzText": "S", "mittelText": norm.line,
          "langText": norm.line, "produktGattung": "SBAHN",
      },
      "terminus": norm.destination,
      "meldungen": [{"code": "c", "text": "Fahrt entfällt"}] if norm.cancelled else [],
  }
  ```
  No `delay` key — `process_departures` derives it from `ezZeit − zeit` (§10: "adjust to the repository's exact current contract"). Returns `{"entries": [...]}`.
- Freshness metadata (cache ages, window size) goes to logs only.

### 6. `trains.py` (modify, minimal diff)

- Remove `url`, `station_id`, and `fetch_departures()`; create `service = DepartureService.from_env()` at module level (validates credentials, fail-fast with a clear message, no values printed — §13).
- `update()` becomes `data = service.get_departures()` then `process_departures(data)` — error/last-known-good handling lives in the service.
- Keep routes, `port = 5123`, `__main__` Waitress startup; rewrite the module docstring (no browser/worker; the page polls only while visible, unchanged).

### 7. Tests and fixtures

Fixtures under `tests/fixtures/timetables/` (small hand-written XML per §15 list): `plan_single_hour.xml` (S4+S6 both directions), `plan_prev_hour.xml`, `plan_overnight_gap.xml`, `plan_year_boundary.xml`, `plan_duplicates.xml`, `plan_non_sbahn.xml`, `fchg_changed_times.xml`, `fchg_platform_change.xml`, `fchg_cancelled.xml`, `fchg_sparse_no_tl.xml`, `fchg_arrival_only.xml`, `fchg_empty.xml`.

- `tests/test_db_merger.py`: join by exact id; sparse patches never erase planned values; `ct`/`cp`/`cde` override rules; destination path fallback; arrival-only excluded; non-S-Bahn excluded; cancellation kept and flagged; duplicate stop IDs; `parse_db_time` on date/year boundaries.
- `tests/test_db_service.py` (fake client + fake clock): initial 1-hour window sufficient; expands exactly one hour while short; stops at 6+6 or cap; one complete direction does not stop expansion for the other; only uncached plan hours fetched during expansion; `fchg` fetched once per refresh; ≤6 per direction; sorting within direction; overnight gap; midnight/year/DST windows; unclassified logged and uncounted; single-flight (two concurrent `get_departures` → one `fetch_changes`); last-known-good on failure; error payload only when no last-known-good; 429 honors Retry-After; 5xx bounded backoff.
- `tests/test_db_contract.py`: adapter output → real `process_departures` → assert the exact frontend payload (keys, 5-tuple shape, `produktGattung` filtering, terminus-based east/west partition, derived delay values). Plus a regression test proving `trains.update()` still returns `process_departures` output unchanged (patch point moves from `trains.fetch_departures` to the service — update `tests/test_trains.py` accordingly).
- `tests/test_failures.py` and `tests/test_bahnrelay.py` remain until the cleanup stage (relay tests move/deleted with the relay).
- Credentials-never-logged test: assert no config secret appears in captured log output.

### 8. Documentation

- `README.md`: replace the "Mac Mini departures relay" section with "DB Timetables API" — Marketplace app + Timetables subscription, `db-env.sh` workflow, the two endpoints, plan/changes overlay in one paragraph, adaptive window behavior, rate-limit note (§12: 60 calls/min; design uses ≤1 changes call/30s while visible plus cached plan hours), and updated architecture bullets. Note the container needs only outbound HTTPS to `apis.deutschebahn.com`.
- `AGENTS.md`: rewrite the runtime architecture bullet (client/cache/merger/service modules, credential rules: never commit, never log, fail fast), deployment (compose env passthrough), and update the runtime data-flow steps.
- `.serena/memories/project_overview.md`: same content, module list and request flow updated.
- Knowledge graph: new `db-timetables-adapter` entity (components, contract, config) related to the deployment entity; relay entity marked retired after cleanup.

## Implementation order (staged, per §17 and §14)

**Stage 1 — functional migration (one commit):**
1. `db_config.py` + `db-env.example.sh` + `.gitignore`/`.dockerignore` entries.
2. `db_client.py` with typed errors.
3. Fixtures + `timetable_merger.py` + merger tests.
4. `plan_cache.py` + `departure_service.py` adaptive window, caching, last-known-good + service tests.
5. Compatibility mapper + contract tests (capture the current `/update` shape first: derive the fixture from a live relay call if the Mac Mini is reachable, otherwise from `process_departures` behavior — the code path is deterministic).
6. Rewire `trains.py`; update `tests/test_trains.py`; full suite green.
7. Docs + memory + knowledge graph.

**Stage 2 — operator cutover (documented, not code):** create the Marketplace app, subscribe to Timetables, fill `db-env.sh`, `set -a && source db-env.sh && set +a && docker compose up -d --build`, verify from inside the container (see checklist). Keep the Mac Mini relay installed but stopped during this stage.

**Stage 3 — cleanup (separate commit, only after live verification, §14):** move `macmini/bahnrelay.py` to `deprecated/`, delete `tests/test_bahnrelay.py`, remove `macmini/` from `.dockerignore` (covered by `deprecated/`), update docs/memory/graph. Playwright/Chrome removal is already done.

## Verification checklist

From the repo root:

```sh
rtk ./venv/bin/python -m unittest discover -s tests -p "test_*.py"
rtk docker compose config
rtk docker compose -f docker-compose.yml -f docker-compose.dev.yml config
```

On the Proxmox LXC after Stage 2:

1. Startup fails loudly with missing-variable names when `db-env.sh` is not sourced; no values printed.
2. `curl -s http://localhost:5123/update` returns the established JSON shape; Home Assistant card renders unchanged.
3. `docker compose logs timetable` shows one changes-fetch per 30s while the page is visible, none while idle; plan fetches appear only on hour/cold-cache boundaries; overnight expansion logged as warning with counts, not as error.
4. A deliberate bad API key → 401 logged once as configuration failure, last-known-good (or Error row on first boot) served, no retry storm.
5. Timing sanity: repeated `/update` within 30s causes no new `fchg` call (single-flight + TTL).
6. `docker compose restart` stays fast; the image contains no credentials (`docker compose exec timetable env | grep -c DB_API_KEY` only via environment, `grep -r DB_API_KEY /timetable` finds only config code reading `os.environ`).

## Risks and decisions

- **East/west partition compatibility (highest risk).** `process_departures` partitions by exact terminus strings; the adapter classifies direction by route anchors. Real DB `pde` values for Zorneding eastbound S-Bahn services are expected to match `Ebersberg(Oberbay)` / `Grafing Bahnhof` (same DB station-name source as the old endpoint), and westbound `Geltendorf` falls to west — the contract test encodes this. If live data shows a mismatch (e.g. `Grafing Stadt`), the contained fallback is a tiny patch to the partition in `departures.py` using the adapter's direction field with terminus fallback — an explicit, tested deviation; do not silently rename destinations.
- **Cancellation representation.** The old contract carried `meldungen` as an opaque array the display ignores. Decision: cancellations keep their row (counting toward six), set `cancelled` internally, and surface as a minimal `meldungen` marker (`code: "c"`). No template change.
- **`verkehrmittel` reconstruction.** Only `produktGattung` is consumed today; `name`/`mittelText` are rebuilt from `dp.l`/`<tl>` and may differ cosmetically from bahn.de's objects. Accepted; documented in the mapper.
- **DST.** `replace(tzinfo=BERLIN)` uses wall-clock semantics (`fold=0`); windows are computed on aware datetimes so a 1-hour step stays 1 real hour except across transitions, which the fixture tests cover explicitly.
- **Clock skew / "departed already" records.** Records whose effective time precedes `now` are filtered by the window start; a delayed train pulled into the window by `ct` is the exact case the extra previous-hour plan fetch covers.
- **Credentials via compose interpolation** are visible in `docker inspect` on the LXC. Acceptable for this single-operator deployment; Docker secrets are out of scope.
- **Relay fallback window.** The relay stays deployed (stopped or running) until Stage 2 verification passes; rollback is `git checkout <previous>` + rebuild, reverting to the relay path if needed.
- **Out of scope (§18):** arrivals, disruption messages `<m>`, multi-station support, UI changes (including a platform column), route planning, any Akamai evasion.

## Deviations from the instruction file (all justified by the repo's actual contract)

1. Entries carry **no** `delay` key — the consumer derives delay from `ezZeit − zeit` (§10 allows exactly this).
2. The adapter's output layer is `process_departures`' input (relay shape), so "the existing application outside the data-source adapter remains unchanged" holds literally; the compatibility mapper lives in `departure_service.py`.
3. §14's Playwright/Chrome/Xvfb removals are already complete; the only cleanup left is the Mac Mini relay.
