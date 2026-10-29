# =============================================================================
# Free data-source clients. Each function returns plain dicts/lists; callers
# own caching and persistence. Verified free-tier behavior: see
# spike/free-data-probe/README.md.
# =============================================================================
import datetime as dt
import html.parser
import os

from .common import IN_CLOUD, HttpError, RateLimiter, http_get, http_json, log

MASSIVE_BASE = "https://api.massive.com"
FINNHUB_BASE = "https://finnhub.io/api/v1"
FRED_BASE = "https://api.stlouisfed.org/fred"

# Massive free plan: 5 calls/min. Finnhub free: ~60/min.
_massive_limiter = RateLimiter(12.5)
_finnhub_limiter = RateLimiter(1.05)
_sec_limiter = RateLimiter(0.15)

INDEX_PAGES = {
    "sp500": "List_of_S%26P_500_companies",
    "sp400": "List_of_S%26P_400_companies",
    "sp600": "List_of_S%26P_600_companies",
}


# =============================================================================
# Credentials
# =============================================================================
def _auth_header(env_name, header, prefix=""):
    """Header carrying an API key, or {} when the cloud proxy injects it."""
    key = os.environ.get(env_name)
    if key:
        return {header: f"{prefix}{key}"}
    if IN_CLOUD:
        return {}
    raise SystemExit(f"{env_name} is not set (local runs need it in the env or .env)")


# =============================================================================
# Universe — Wikipedia constituent tables
# =============================================================================
class _TableParser(html.parser.HTMLParser):
    """Collects every row (list of cell texts) of the table with id=constituents."""

    def __init__(self):
        super().__init__()
        self.depth = 0
        self.rows = []
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table" and (self.depth or dict(attrs).get("id") == "constituents"):
            self.depth += 1
        elif self.depth == 1 and tag == "tr":
            self._row = []
        elif self.depth == 1 and tag in ("td", "th") and self._row is not None:
            self._cell = ""

    def handle_endtag(self, tag):
        if tag == "table" and self.depth:
            self.depth -= 1
        elif self.depth == 1 and tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join(self._cell.split()))
            self._cell = None
        elif self.depth == 1 and tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell += data


def fetch_index_members(index_key):
    """[{ticker, name, sector, index}] for one S&P index."""
    body = http_get(f"https://en.wikipedia.org/wiki/{INDEX_PAGES[index_key]}")
    parser = _TableParser()
    parser.feed(body.decode("utf-8", "replace"))
    header, *rows = parser.rows
    cols = {name.lower(): i for i, name in enumerate(header)}
    sym_i = next(i for name, i in cols.items() if name in ("symbol", "ticker symbol", "ticker"))
    name_i = next(i for name, i in cols.items() if name in ("security", "company"))
    sector_i = next(i for name, i in cols.items() if "sector" in name)
    members = []
    for row in rows:
        if len(row) <= max(sym_i, name_i, sector_i):
            continue
        ticker = row[sym_i].strip().upper()
        if ticker and ticker.replace(".", "").replace("-", "").isalnum():
            members.append({"ticker": ticker, "name": row[name_i], "sector": row[sector_i], "index": index_key})
    if len(members) < 300:
        raise RuntimeError(f"{index_key}: parsed only {len(members)} members — page layout changed?")
    return members


# =============================================================================
# Massive — daily bars and splits
# =============================================================================
def massive_grouped_daily(day):
    """Raw (unadjusted) daily bars for every US stock/ETF on `day`.

    Returns {ticker: (o, h, l, c, v)} or None when the day isn't available
    (holiday, or same-day before 00:00 ET on the free plan -> HTTP 403).
    """
    _massive_limiter.wait()
    url = f"{MASSIVE_BASE}/v2/aggs/grouped/locale/us/market/stocks/{day.isoformat()}?adjusted=false"
    try:
        data = http_json(url, _auth_header("MASSIVE_API_KEY", "Authorization", "Bearer "))
    except HttpError as exc:
        if exc.status == 403:
            return None
        raise
    results = data.get("results") or []
    if not results:
        return {}
    return {r["T"]: (r["o"], r["h"], r["l"], r["c"], r.get("v", 0)) for r in results if "T" in r}


def massive_splits(since):
    """All splits with execution_date >= since: [{ticker, execution_date, split_from, split_to}]."""
    headers = _auth_header("MASSIVE_API_KEY", "Authorization", "Bearer ")
    url = (f"{MASSIVE_BASE}/v3/reference/splits?execution_date.gte={since.isoformat()}"
           "&limit=1000&order=asc&sort=execution_date")
    out = []
    while url:
        _massive_limiter.wait()
        data = http_json(url, headers)
        for r in data.get("results") or []:
            out.append({k: r[k] for k in ("ticker", "execution_date", "split_from", "split_to")})
        url = data.get("next_url")
    return out


# =============================================================================
# Finnhub — earnings calendar, news, recommendations, metrics
# =============================================================================
def _finnhub(path):
    _finnhub_limiter.wait()
    return http_json(f"{FINNHUB_BASE}{path}", _auth_header("FINNHUB_API_KEY", "X-Finnhub-Token"))


def finnhub_earnings_calendar(start, end):
    data = _finnhub(f"/calendar/earnings?from={start.isoformat()}&to={end.isoformat()}")
    return [{"ticker": r["symbol"], "date": r["date"], "hour": r.get("hour") or "",
             "eps_estimate": r.get("epsEstimate"), "revenue_estimate": r.get("revenueEstimate")}
            for r in data.get("earningsCalendar") or [] if r.get("symbol") and r.get("date")]


def finnhub_company_news(ticker, start, end, limit=12):
    items = _finnhub(f"/company-news?symbol={ticker}&from={start.isoformat()}&to={end.isoformat()}") or []
    items = sorted(items, key=lambda r: r.get("datetime", 0), reverse=True)[:limit]
    return [{"date": dt.datetime.fromtimestamp(r["datetime"], dt.timezone.utc).date().isoformat(),
             "headline": r.get("headline", ""), "source": r.get("source", ""), "url": r.get("url", ""),
             "summary": (r.get("summary") or "")[:400]}
            for r in items if r.get("datetime")]


def finnhub_recommendations(ticker):
    rows = _finnhub(f"/stock/recommendation?symbol={ticker}") or []
    return rows[:3]


def finnhub_metrics(ticker):
    data = _finnhub(f"/stock/metric?symbol={ticker}&metric=all") or {}
    metric = data.get("metric") or {}
    keep = ("marketCapitalization", "peTTM", "psTTM", "epsGrowthTTMYoy", "revenueGrowthTTMYoy",
            "revenueGrowthQuarterlyYoy", "epsGrowthQuarterlyYoy", "grossMarginTTM", "netProfitMarginTTM",
            "roeTTM", "beta", "52WeekHigh", "52WeekLow", "totalDebt/totalEquityQuarterly")
    return {k: metric.get(k) for k in keep if metric.get(k) is not None}


# =============================================================================
# Nasdaq — earnings calendar cross-check (unofficial, keyless)
# =============================================================================
def nasdaq_earnings(day):
    data = http_json(f"https://api.nasdaq.com/api/calendar/earnings?date={day.isoformat()}",
                     {"Accept": "application/json"})
    rows = ((data or {}).get("data") or {}).get("rows") or []
    return [{"ticker": r["symbol"], "date": day.isoformat(), "time": r.get("time", ""),
             "eps_forecast": r.get("epsForecast", ""), "n_estimates": r.get("noOfEsts", "")}
            for r in rows if r.get("symbol")]


# =============================================================================
# FRED — macro context
# =============================================================================
def fred_series(series_id, limit=260):
    """[(date, value)] newest last; '.' (missing) observations dropped."""
    key = os.environ.get("FRED_API_KEY")
    if not key:
        raise SystemExit("FRED_API_KEY is not set")
    data = http_json(f"{FRED_BASE}/series/observations?series_id={series_id}&api_key={key}"
                     f"&file_type=json&sort_order=desc&limit={limit}")
    obs = [(o["date"], float(o["value"])) for o in data.get("observations", []) if o["value"] not in (".", "")]
    return list(reversed(obs))


# =============================================================================
# SEC EDGAR — recent filings
# =============================================================================
def _sec_headers():
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua:
        raise SystemExit("SEC_USER_AGENT is not set (SEC fair-access policy: '<name> <email>')")
    return {"User-Agent": ua}


def sec_ticker_ciks():
    _sec_limiter.wait()
    data = http_json("https://www.sec.gov/files/company_tickers.json", _sec_headers())
    return {row["ticker"].upper(): f"{int(row['cik_str']):010d}" for row in data.values()}


def sec_recent_filings(cik, since, forms=("8-K", "10-Q", "10-K", "S-3", "424B5", "SC 13D", "4")):
    _sec_limiter.wait()
    data = http_json(f"https://data.sec.gov/submissions/CIK{cik}.json", _sec_headers())
    recent = data.get("filings", {}).get("recent", {})
    out = []
    for form, date, items, desc in zip(recent.get("form", []), recent.get("filingDate", []),
                                       recent.get("items", [""] * 10_000), recent.get("primaryDocDescription", [""] * 10_000)):
        if date < since.isoformat():
            break
        if form in forms:
            out.append({"form": form, "date": date, "items": items, "description": desc})
    return out[:15]


def safe(call, *args, default=None, **kwargs):
    """Run an enrichment call; log and degrade instead of failing the whole run."""
    try:
        return call(*args, **kwargs)
    except (HttpError, RuntimeError, ValueError, KeyError) as exc:
        log("source.degraded", call=call.__name__, error=str(exc)[:200])
        return default
