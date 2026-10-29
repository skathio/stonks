# =============================================================================
# Universe: S&P 500 + S&P 400 are scanned; S&P 600 is stored too, so names
# promoted into the scan universe already have price history.
#
# Index membership is the penny-stock filter: S&P inclusion needs size,
# liquidity and profitability. features.py adds a price >= $5 and liquidity
# floor on top. The $5 is the SEC penny-stock definition, an eligibility
# rule rather than a trading threshold.
# =============================================================================
import datetime as dt
import os

from . import sources
from .common import log, read_json, write_json

SCAN_INDEXES = ("sp500", "sp400")
STORE_INDEXES = ("sp500", "sp400", "sp600")
REFRESH_DAYS = 7


def load(data_dir, refresh=False):
    """{ticker: {name, sector, index}} for all stored indexes, cached weekly."""
    path = os.path.join(data_dir, "universe.json")
    cached = read_json(path)
    fresh = cached and (dt.date.today() - dt.date.fromisoformat(cached["fetched"])).days < REFRESH_DAYS
    if fresh and not refresh:
        return cached["members"]
    members = {}
    try:
        for index in STORE_INDEXES:
            for m in sources.fetch_index_members(index):
                members.setdefault(m["ticker"], {k: m[k] for k in ("name", "sector", "index")})
    except Exception as exc:  # Wikipedia layout change / outage: stale beats nothing
        if cached:
            log("universe.stale_cache", error=str(exc)[:200], fetched=cached["fetched"])
            return cached["members"]
        raise
    write_json(path, {"fetched": dt.date.today().isoformat(), "members": members})
    log("universe.refreshed", members=len(members))
    return members


def scan_tickers(members):
    return sorted(t for t, m in members.items() if m["index"] in SCAN_INDEXES)
