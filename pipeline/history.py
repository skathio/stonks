# =============================================================================
# Price-history store (lives in the private stonks-data repo).
#
# Layout:
#   history/bars/YYYY/YYYY-MM-DD.csv.gz   raw (UNADJUSTED) daily bars, one file
#                                         per session, stored symbols only
#   history/splits.json                   split ledger, applied at load time
#   history/closed_days.json              weekdays with no session (holidays)
#
# Why raw + ledger: adjusting at load time is deterministic and survives
# splits announced after a bar was stored. Storing pre-adjusted bars would
# silently turn every future split into a fake crash (a 4:1 split reads as
# -75%) for every stored day before it.
#
# Dividends are NOT adjusted. Price-only technicals on liquid large/mid caps
# drift by roughly the yield, which is immaterial for ATR/MA/RS work.
# =============================================================================
import csv
import datetime as dt
import gzip
import io
import os
from zoneinfo import ZoneInfo

from . import sources
from .common import log, read_json, write_json

ET = ZoneInfo("America/New_York")
# Benchmarks and sector proxies stored alongside the universe.
BENCHMARKS = ("SPY", "QQQ", "IWM", "DIA", "RSP", "SMH",
              "XLK", "XLF", "XLV", "XLY", "XLP", "XLE", "XLI", "XLB", "XLU", "XLRE", "XLC")
SECTOR_ETF = {
    "Information Technology": "XLK", "Financials": "XLF", "Health Care": "XLV",
    "Consumer Discretionary": "XLY", "Consumer Staples": "XLP", "Energy": "XLE",
    "Industrials": "XLI", "Materials": "XLB", "Utilities": "XLU", "Real Estate": "XLRE",
    "Communication Services": "XLC",
}
TARGET_SESSIONS = 300  # 252 for 52-week stats + warm-up for 200-day averages


def _paths(data_dir):
    root = os.path.join(data_dir, "history")
    return {
        "bars": os.path.join(root, "bars"),
        "splits": os.path.join(root, "splits.json"),
        "closed": os.path.join(root, "closed_days.json"),
        "meta": os.path.join(root, "meta.json"),
    }


def _bar_file(data_dir, day):
    return os.path.join(_paths(data_dir)["bars"], f"{day.year}", f"{day.isoformat()}.csv.gz")


def stored_days(data_dir):
    root = _paths(data_dir)["bars"]
    days = []
    if os.path.isdir(root):
        for year in os.listdir(root):
            for name in os.listdir(os.path.join(root, year)):
                if name.endswith(".csv.gz"):
                    days.append(dt.date.fromisoformat(name[:10]))
    return sorted(days)


def _write_day(data_dir, day, bars):
    path = _bar_file(data_dir, day)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    for ticker in sorted(bars):
        o, h, l, c, v = bars[ticker]
        writer.writerow([ticker, f"{o:.4f}", f"{h:.4f}", f"{l:.4f}", f"{c:.4f}", int(v)])
    # mtime=0 keeps the gzip bytes deterministic, so re-writes don't churn git.
    with open(path, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(buf.getvalue().encode())


def _read_day(data_dir, day):
    with gzip.open(_bar_file(data_dir, day), "rt") as fh:
        return {row[0]: (float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]))
                for row in csv.reader(fh)}


def latest_available_day(now=None):
    """Newest session the Massive free plan can serve: bars unlock after 00:00 ET."""
    today_et = (now or dt.datetime.now(ET)).astimezone(ET).date()
    return today_et - dt.timedelta(days=1)


def _weekdays_back(end, count):
    day = end
    while count > 0:
        if day.weekday() < 5:
            yield day
            count -= 1
        day -= dt.timedelta(days=1)


# =============================================================================
# Update
# =============================================================================
def update(data_dir, symbols, target_sessions=TARGET_SESSIONS, max_calls=None):
    """Fetch missing sessions up to the newest available one.

    First run backfills `target_sessions` (about an hour at 5 calls/min).
    Daily runs fetch one call per new session. Returns the list of new days.
    """
    keep = set(symbols)
    paths = _paths(data_dir)
    closed = set(read_json(paths["closed"], []))
    have = set(stored_days(data_dir))
    newest = latest_available_day()

    # Forward: new sessions since the newest stored one (the daily case).
    forward = []
    if have:
        start = max(have) + dt.timedelta(days=1)
        forward = [start + dt.timedelta(days=i) for i in range((newest - start).days + 1)]
    # Backward: resumable backfill until target_sessions are stored. The
    # calendar span is padded because ~4% of weekdays are market holidays.
    missing = max(0, target_sessions - len(have))
    backward = list(_weekdays_back(min(have) - dt.timedelta(days=1) if have else newest,
                                   int(missing * 1.06) + 5)) if missing else []

    def skip(d):
        return d.weekday() >= 5 or d.isoformat() in closed or d in have

    added, calls, backfilled = [], 0, 0
    plan = [("forward", d) for d in forward if not skip(d)] + [("backward", d) for d in backward if not skip(d)]
    forward_blocked = False
    for direction, day in plan:
        if max_calls is not None and calls >= max_calls:
            log("history.call_cap", remaining=len(plan) - calls)
            break
        if direction == "forward" and forward_blocked:
            continue
        if direction == "backward" and backfilled >= missing:
            break
        bars = sources.massive_grouped_daily(day)
        calls += 1
        if bars is None:
            log("history.not_yet_available", day=day.isoformat())
            forward_blocked = forward_blocked or direction == "forward"
            continue
        if not bars:
            closed.add(day.isoformat())
            log("history.closed_day", day=day.isoformat())
            continue
        subset = {t: b for t, b in bars.items() if t in keep}
        _write_day(data_dir, day, subset)
        added.append(day)
        backfilled += direction == "backward"
        log("history.stored", day=day.isoformat(), symbols=len(subset), market=len(bars), direction=direction)
        write_json(paths["closed"], sorted(closed))  # checkpoint: a killed run resumes cleanly

    write_json(paths["closed"], sorted(closed))
    _prune(data_dir, target_sessions + 20)
    return sorted(added)


def _prune(data_dir, keep_sessions):
    days = stored_days(data_dir)
    for day in days[:-keep_sessions] if len(days) > keep_sessions else []:
        os.remove(_bar_file(data_dir, day))


def refresh_splits(data_dir, lookback_days=10):
    """Merge splits executed since the last refresh (or since the oldest stored bar)."""
    paths = _paths(data_dir)
    ledger = {(s["ticker"], s["execution_date"]): s for s in read_json(paths["splits"], [])}
    meta = read_json(paths["meta"], {})
    days = stored_days(data_dir)
    if not days:
        return 0
    # A backfill can extend history *backwards* past what the ledger covers,
    # so track coverage at both ends, not just the last refresh.
    covered_from = meta.get("splits_covered_from")
    if not covered_from or dt.date.fromisoformat(covered_from) > days[0] or not meta.get("splits_refreshed_through"):
        since = days[0]
    else:
        since = dt.date.fromisoformat(meta["splits_refreshed_through"]) - dt.timedelta(days=lookback_days)
    before = len(ledger)
    for split in sources.massive_splits(since):
        ledger[(split["ticker"], split["execution_date"])] = split
    write_json(paths["splits"], sorted(ledger.values(), key=lambda s: (s["execution_date"], s["ticker"])))
    meta["splits_covered_from"] = min(since, dt.date.fromisoformat(covered_from)).isoformat() if covered_from else since.isoformat()
    meta["splits_refreshed_through"] = days[-1].isoformat()
    write_json(paths["meta"], meta)
    return len(ledger) - before


# =============================================================================
# Load (split-adjusted panel)
# =============================================================================
def split_factors(splits, last_day):
    """{ticker: [(execution_date, price_factor)]} for splits effective by last_day."""
    out = {}
    for s in splits:
        ex = dt.date.fromisoformat(s["execution_date"])
        if ex > last_day or not s.get("split_from") or not s.get("split_to"):
            continue
        out.setdefault(s["ticker"], []).append((ex, s["split_from"] / s["split_to"]))
    return out


def adjust_series(days, bars, factors):
    """Apply split factors to one ticker's raw bars. bars[i] is (o,h,l,c,v) or None."""
    if not factors:
        return bars
    out = []
    for day, bar in zip(days, bars):
        if bar is None:
            out.append(None)
            continue
        price_f = 1.0
        for ex, f in factors:
            if day < ex:
                price_f *= f
        o, h, l, c, v = bar
        out.append((o * price_f, h * price_f, l * price_f, c * price_f, v / price_f))
    return out


def load_panel(data_dir, symbols, sessions=TARGET_SESSIONS):
    """(days, {ticker: [bar|None per day]}) split-adjusted, oldest first."""
    days = stored_days(data_dir)[-sessions:]
    wanted = set(symbols)
    raw = {t: [] for t in wanted}
    for day in days:
        bars = _read_day(data_dir, day)
        for t in wanted:
            raw[t].append(bars.get(t))
    splits = read_json(_paths(data_dir)["splits"], [])
    factors = split_factors(splits, days[-1]) if days else {}
    return days, {t: adjust_series(days, series, factors.get(t)) for t, series in raw.items()}
