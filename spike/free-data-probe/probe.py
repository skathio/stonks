#!/usr/bin/env python3
# =============================================================================
# Free-data feasibility probe (SPIKE — throwaway, not production code)
#
# Purpose : Verify that every free data source the daily agent job would rely
#           on is reachable, returns usable data, and how fresh that data is
#           at the planned 07:00 CET run time.
# Author  : stonks spike
# Date    : 2026-10-29
# Version : 0.1
#
# Stdlib only, so it runs unchanged on a laptop and inside a Claude Code
# cloud session without a dependency install.
#
# Keys are read from the environment and never printed:
#   MASSIVE_API_KEY   (massive.com free "Basic" plan)
#   FINNHUB_API_KEY   (finnhub.io free plan)
#   FRED_API_KEY      (fred.stlouisfed.org, free)
#   SEC_USER_AGENT    ("<name> <contact email>" — SEC fair-access policy
#                      requires a real contact; a generic fallback is used
#                      only so the probe can run, set your own)
#
# Usage: python3 probe.py [--out results/<label>.json] [--skip-massive]
# =============================================================================
import argparse
import datetime as dt
import html.parser
import json
import os
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

def f_load_env_file(path):
    """Load KEY=VALUE lines from a local .env into os.environ; exported vars win."""
    if not os.path.isfile(path):
        return
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            if value and not os.environ.get(name.strip()):
                os.environ[name.strip()] = value


f_load_env_file(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# In a Claude Code cloud session, network secrets are injected into request
# headers by Anthropic's agent proxy and are NOT visible as env vars. With
# --proxy-auth the keyed probes run without a local key and send no auth header.
PROXY_AUTH = "<proxy-injected>"

ET = ZoneInfo("America/New_York")
CET = ZoneInfo("Europe/Berlin")
RUN_HOUR_CET = 7
TIMEOUT_S = 30
# Massive free plan = 5 calls/min; stay under it when walking back dates.
MASSIVE_CALL_GAP_S = 13
BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
SEC_UA = os.environ.get("SEC_USER_AGENT", "stonks-spike research-probe admin@example.com")
PROBE_SYMBOL = "AAPL"
PROBE_CIK = "0000320193"  # AAPL


# =============================================================================
# HTTP
# =============================================================================
def f_get(url, headers=None):
    """Return (status, body_bytes, latency_ms, error). Never raises."""
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA, **(headers or {})})
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            body = resp.read()
            return resp.status, body, int((time.monotonic() - start) * 1000), None
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), int((time.monotonic() - start) * 1000), None
    except Exception as exc:  # network / DNS / TLS / proxy-deny
        return None, b"", int((time.monotonic() - start) * 1000), f"{type(exc).__name__}: {exc}"


def f_result(source, endpoint, status, latency, ok, latest=None, note="", error=None):
    return {
        "source": source,
        "endpoint": endpoint,
        "http_status": status,
        "ok": ok,
        "latency_ms": latency,
        "latest_data_date": latest,
        "note": error or note,
    }


def f_json(body):
    try:
        return json.loads(body)
    except ValueError:
        return None


# =============================================================================
# Universe — Wikipedia constituent tables
# =============================================================================
class _TableRowCounter(html.parser.HTMLParser):
    """Counts <tr> rows and collects first-column text in the table with a given id."""

    def __init__(self, table_id):
        super().__init__()
        self.table_id = table_id
        self.depth = 0
        self.rows = 0
        self.first_cells = []
        self._in_first_cell = False
        self._cell_index = -1
        self._buf = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "table" and (self.depth or attrs.get("id") == self.table_id):
            self.depth += 1
        elif self.depth and tag == "tr":
            self.rows += 1
            self._cell_index = -1
        elif self.depth and tag in ("td", "th"):
            self._cell_index += 1
            self._in_first_cell = self._cell_index == 0
            self._buf = ""

    def handle_endtag(self, tag):
        if tag == "table" and self.depth:
            self.depth -= 1
        elif self.depth and tag in ("td", "th") and self._in_first_cell:
            self.first_cells.append(self._buf.strip())
            self._in_first_cell = False

    def handle_data(self, data):
        if self._in_first_cell:
            self._buf += data


def f_probe_wikipedia(index_name, page):
    url = f"https://en.wikipedia.org/wiki/{page}"
    status, body, latency, err = f_get(url)
    if status != 200:
        return f_result("wikipedia", index_name, status, latency, False, error=err), []
    parser = _TableRowCounter("constituents")
    parser.feed(body.decode("utf-8", "replace"))
    tickers = [c for c in parser.first_cells[1:] if c and c.replace(".", "").replace("-", "").isalnum()]
    ok = len(tickers) > 300
    return f_result("wikipedia", index_name, status, latency, ok, note=f"{len(tickers)} tickers parsed"), tickers


# =============================================================================
# SEC EDGAR — fundamentals, filings, insider forms (no key)
# =============================================================================
def f_probe_sec():
    out = []
    hdr = {"User-Agent": SEC_UA, "Accept-Encoding": "identity"}

    status, body, latency, err = f_get("https://www.sec.gov/files/company_tickers.json", hdr)
    data = f_json(body) if status == 200 else None
    out.append(f_result("sec", "company_tickers.json", status, latency, bool(data),
                        note=f"{len(data)} issuers" if data else "", error=err))

    status, body, latency, err = f_get(f"https://data.sec.gov/submissions/CIK{PROBE_CIK}.json", hdr)
    data = f_json(body) if status == 200 else None
    latest, note = None, ""
    if data:
        recent = data["filings"]["recent"]
        latest = recent["filingDate"][0]
        forms = recent["form"][:20]
        note = f"latest form {forms[0]}; last-20 forms incl. 8-K={forms.count('8-K')}, 4={forms.count('4')}"
    out.append(f_result("sec", f"submissions ({PROBE_SYMBOL})", status, latency, bool(data), latest, note, err))

    status, body, latency, err = f_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{PROBE_CIK}.json", hdr)
    data = f_json(body) if status == 200 else None
    note = ""
    if data:
        concepts = data.get("facts", {}).get("us-gaap", {})
        rev = concepts.get("RevenueFromContractWithCustomerExcludingAssessedTax") or concepts.get("Revenues")
        last = rev["units"]["USD"][-1] if rev else None
        note = f"{len(concepts)} us-gaap concepts; revenue last period end {last['end'] if last else 'n/a'}"
    out.append(f_result("sec", f"companyfacts XBRL ({PROBE_SYMBOL})", status, latency, bool(data), note=note, error=err))
    return out


# =============================================================================
# Daily OHLCV candidates
# =============================================================================
def f_probe_stooq():
    url = f"https://stooq.com/q/d/l/?s={PROBE_SYMBOL.lower()}.us&i=d"
    status, body, latency, err = f_get(url)
    text = body.decode("utf-8", "replace").strip()
    lines = text.splitlines()
    ok = status == 200 and len(lines) > 10 and lines[0].lower().startswith("date")
    latest = lines[-1].split(",")[0] if ok else None
    note = f"{len(lines) - 1} bars" if ok else f"body starts: {text[:80]!r}"
    return f_result("stooq", f"daily csv ({PROBE_SYMBOL})", status, latency, ok, latest, note, err)


def f_probe_yahoo():
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{PROBE_SYMBOL}?range=5d&interval=1d"
    status, body, latency, err = f_get(url)
    data = f_json(body) if status == 200 else None
    latest = None
    if data and data.get("chart", {}).get("result"):
        ts = data["chart"]["result"][0]["timestamp"][-1]
        latest = dt.datetime.fromtimestamp(ts, ET).date().isoformat()
    note = "unofficial; ToS forbids redistribution; often blocks datacenter IPs"
    return f_result("yahoo", f"chart v8 ({PROBE_SYMBOL})", status, latency, bool(latest), latest, note, err)


def f_massive_get(path, key):
    # Bearer header keeps the key out of URLs/logs.
    hdr = {"Authorization": f"Bearer {key}"} if key and key != PROXY_AUTH else {}
    return f_get(f"https://api.massive.com{path}", hdr)


def f_key(name, proxy_auth):
    return os.environ.get(name) or (PROXY_AUTH if proxy_auth else None)


def f_probe_massive(skip, proxy_auth):
    key = f_key("MASSIVE_API_KEY", proxy_auth)
    if not key:
        status, _, latency, err = f_massive_get("/v2/aggs/grouped/locale/us/market/stocks/2026-10-27", None)
        return [f_result("massive", "grouped daily (no key)", status, latency, status in (401, 403),
                         note="reachability only — set MASSIVE_API_KEY for a real probe", error=err)]
    if skip:
        return [f_result("massive", "grouped daily", None, 0, False, note="skipped by flag")]

    out = []
    day = dt.datetime.now(ET).date()
    latest = None
    for attempt in range(5):
        while day.weekday() >= 5:
            day -= dt.timedelta(days=1)
        status, body, latency, err = f_massive_get(
            f"/v2/aggs/grouped/locale/us/market/stocks/{day.isoformat()}?adjusted=true", key)
        data = f_json(body) if status == 200 else None
        count = data.get("resultsCount", 0) if data else 0
        out.append(f_result("massive", f"grouped daily {day.isoformat()}", status, latency, count > 0,
                            day.isoformat() if count else None, f"{count} tickers in one call", err))
        if count:
            latest = day
            break
        day -= dt.timedelta(days=1)
        time.sleep(MASSIVE_CALL_GAP_S)

    time.sleep(MASSIVE_CALL_GAP_S)
    status, body, latency, err = f_massive_get("/v3/reference/splits?limit=5&order=desc&sort=execution_date", key)
    data = f_json(body) if status == 200 else None
    newest = data["results"][0].get("execution_date") if data and data.get("results") else None
    out.append(f_result("massive", "reference splits", status, latency, bool(newest), newest,
                        "needed to re-adjust stored history", err))
    return out


# =============================================================================
# Earnings dates, news, analyst data
# =============================================================================
def f_probe_finnhub(proxy_auth):
    key = f_key("FINNHUB_API_KEY", proxy_auth)
    today = dt.datetime.now(ET).date()
    frm, to = today - dt.timedelta(days=7), today + dt.timedelta(days=14)
    endpoints = {
        # /quote returns today's o/h/l/c — could close the 03:00 CET staleness gap.
        "quote (same-day OHLC)": f"/quote?symbol={PROBE_SYMBOL}",
        "earnings calendar": f"/calendar/earnings?from={frm}&to={to}",
        "company news": f"/company-news?symbol={PROBE_SYMBOL}&from={frm}&to={today}",
        "recommendation trends": f"/stock/recommendation?symbol={PROBE_SYMBOL}",
        "price target": f"/stock/price-target?symbol={PROBE_SYMBOL}",
        "eps estimates": f"/stock/eps-estimate?symbol={PROBE_SYMBOL}",
        "basic financials": f"/stock/metric?symbol={PROBE_SYMBOL}&metric=all",
        "daily candles": f"/stock/candle?symbol={PROBE_SYMBOL}&resolution=D&from={int(time.time()) - 864000}&to={int(time.time())}",
    }
    if not key:
        status, _, latency, err = f_get("https://finnhub.io/api/v1" + endpoints["earnings calendar"])
        return [f_result("finnhub", "earnings calendar (no key)", status, latency, status in (401, 403),
                         note="reachability only — set FINNHUB_API_KEY for the free-endpoint map", error=err)]
    out = []
    for name, path in endpoints.items():
        hdr = {"X-Finnhub-Token": key} if key != PROXY_AUTH else {}
        status, body, latency, err = f_get("https://finnhub.io/api/v1" + path, hdr)
        data = f_json(body) if status == 200 else None
        if isinstance(data, dict) and "earningsCalendar" in data:
            size = len(data["earningsCalendar"])
        elif isinstance(data, (list, dict)):
            size = len(data)
        else:
            size = 0
        note = f"{size} items" if status == 200 else body[:100].decode("utf-8", "replace")
        out.append(f_result("finnhub", name, status, latency, status == 200 and size > 0, note=note, error=err))
        time.sleep(1.1)  # free plan ~60/min
    return out


def f_probe_nasdaq_earnings():
    day = dt.datetime.now(ET).date()
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={day.isoformat()}"
    status, body, latency, err = f_get(url, {"Accept": "application/json"})
    data = f_json(body) if status == 200 else None
    rows = (data or {}).get("data", {}) or {}
    rows = rows.get("rows") or []
    return f_result("nasdaq", f"earnings calendar {day}", status, latency, bool(rows),
                    note=f"{len(rows)} reporting today (pre/after-mkt, consensus EPS, #ests); unofficial endpoint",
                    error=err)


# =============================================================================
# Macro — FRED
# =============================================================================
def f_probe_fred_csv():
    # Keyless graph CSV — avoids needing the key at all (FRED's API only takes
    # the key as a URL parameter, which header-based network secrets can't carry).
    status, body, latency, err = f_get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10")
    lines = body.decode("utf-8", "replace").strip().splitlines() if status == 200 else []
    ok = len(lines) > 10 and "DGS10" in lines[0]
    latest = lines[-1].split(",")[0] if ok else None
    value = lines[-1].split(",")[1] if ok else ""
    return f_result("fred", "DGS10 graph CSV (no key)", status, latency, ok, latest,
                    f"value {value}; {len(lines) - 1} rows" if ok else (lines[0][:80] if lines else ""), err)


def f_probe_fred():
    key = os.environ.get("FRED_API_KEY")
    if not key:
        status, _, latency, err = f_get("https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&file_type=json")
        return f_result("fred", "DGS10 (no key)", status, latency, status in (400, 401, 403),
                        note="reachability only — set FRED_API_KEY", error=err)
    url = (f"https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key={key}"
           "&file_type=json&sort_order=desc&limit=1")
    status, body, latency, err = f_get(url)
    data = f_json(body) if status == 200 else None
    obs = (data or {}).get("observations") or []
    latest = obs[0]["date"] if obs else None
    return f_result("fred", "DGS10 10y yield", status, latency, bool(obs), latest,
                    f"value {obs[0]['value']}" if obs else "", err)


# =============================================================================
# Timing — what session is the latest one at the planned CET run hour?
# =============================================================================
def f_prev_weekday(day):
    day -= dt.timedelta(days=1)
    while day.weekday() >= 5:
        day -= dt.timedelta(days=1)
    return day


def f_timing(sample_dates):
    """For a RUN_HOUR_CET run on each date: ET wall time, the last closed US session,
    and the newest session Massive's free plan serves (bars unlock after 00:00 ET)."""
    rows = []
    for d in sample_dates:
        run_cet = dt.datetime.combine(d, dt.time(RUN_HOUR_CET), CET)
        run_et = run_cet.astimezone(ET)
        last_closed = run_et.date() if run_et.weekday() < 5 and run_et.hour >= 16 else f_prev_weekday(run_et.date())
        massive_newest = f_prev_weekday(run_et.date())
        rows.append({
            "run_cet": run_cet.strftime("%a %Y-%m-%d %H:%M %Z"),
            "run_et": run_et.strftime("%a %Y-%m-%d %H:%M %Z"),
            "last_closed_session": last_closed.isoformat(),
            "massive_free_newest": massive_newest.isoformat(),
            "sessions_stale": 0 if massive_newest == last_closed else 1,
        })
    return rows


# =============================================================================
# Main
# =============================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write JSON results here")
    ap.add_argument("--skip-massive", action="store_true")
    ap.add_argument("--proxy-auth", action="store_true",
                    help="cloud session: keys are injected by the network-secrets proxy")
    args = ap.parse_args()

    started = dt.datetime.now(dt.timezone.utc)
    results = []
    universe = {}
    for name, page in (("S&P 500", "List_of_S%26P_500_companies"), ("S&P 400", "List_of_S%26P_400_companies")):
        res, tickers = f_probe_wikipedia(name, page)
        results.append(res)
        universe[name] = len(tickers)
    results += f_probe_sec()
    results.append(f_probe_stooq())
    results.append(f_probe_yahoo())
    results += f_probe_massive(args.skip_massive, args.proxy_auth)
    results += f_probe_finnhub(args.proxy_auth)
    results.append(f_probe_nasdaq_earnings())
    results.append(f_probe_fred_csv())
    results.append(f_probe_fred())

    today_cet = dt.datetime.now(CET).date()
    samples = [today_cet + dt.timedelta(days=i) for i in range(1, 8)] + [dt.date(2027, 3, 23), dt.date(2027, 7, 14)]
    timing = f_timing(samples)

    report = {
        "started_utc": started.isoformat(timespec="seconds"),
        "host_hint": os.environ.get("CLAUDE_CODE_REMOTE", "local"),
        "universe_sizes": universe,
        "results": results,
        "timing_run_cet": timing,
    }

    print(f"\nProbe run {report['started_utc']} ({report['host_hint']})\n")
    print(f"{'source':9} {'endpoint':34} {'http':>4} {'ok':>3} {'ms':>6}  {'latest':10}  note")
    for r in results:
        print(f"{r['source']:9} {r['endpoint'][:34]:34} {str(r['http_status']):>4} "
              f"{'Y' if r['ok'] else '-':>3} {r['latency_ms']:>6}  {str(r['latest_data_date'] or ''):10}  {r['note'][:90]}")
    print(f"\n{RUN_HOUR_CET:02d}:00 CET run → freshness")
    for t in timing:
        print(f"  {t['run_cet']:28} = {t['run_et']:28} last closed {t['last_closed_session']}  "
              f"massive-free newest {t['massive_free_newest']}  stale={t['sessions_stale']}")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as fh:
            json.dump(report, fh, indent=2)
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
