# =============================================================================
# The agent's output contract (runs/<as_of>/analysis.json) and the levels the
# pipeline derives from it.
#
# The agent supplies judgment: which names, why, conviction, and the stop
# width in ATR multiples. The pipeline supplies every price and size: stop,
# chase limit, the +20% reference level and the position size are computed
# here from the stored close and ATR. Any price the agent writes is ignored,
# so an arithmetic slip can't reach the dashboard or the track record.
#
# Contract v2 (2026-10-30): position trades held 2-6 months. Wide catastrophic
# stop, no profit targets, at most two new positions a day, and a review line
# for any held position the agent wants to comment on.
# =============================================================================
import re

from . import ledger

REGIME_LABELS = ("risk_on", "neutral", "risk_off")
EXPOSURE = ("full", "reduced", "minimal", "none")
SETUPS = ("breakout", "squeeze", "pullback_reclaim", "base", "other")
CONTRACT = "v2"
MAX_CANDIDATES, MAX_WATCH, MAX_AVOID, MAX_REVIEWS = 2, 25, 20, 15
REVIEW_ACTIONS = ("hold", "trim", "exit", "add")
STOP_ATR_RANGE, CHASE_ATR_RANGE, HORIZON_RANGE = (3.0, 6.0), (0.0, 1.5), (42, 126)
MAX_STOP_PCT = 15.0          # a stop wider than this from the close is not a stop
RISK_PER_TRADE_PCT = 1.0     # account % lost at the stop, before the momentum size scale
MAX_POSITION_PCT = 15.0
EARNINGS_HALF_SIZE_SESSIONS = 15  # a report this close: half size, so a gap can't double the risk
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AnalysisError(ValueError):
    pass


def _req(obj, key, kind, where):
    if key not in obj:
        raise AnalysisError(f"{where}: missing '{key}'")
    val = obj[key]
    if kind is float and isinstance(val, int) and not isinstance(val, bool):
        val = float(val)
    if not isinstance(val, kind):
        raise AnalysisError(f"{where}.{key}: expected {kind.__name__}, got {type(val).__name__}")
    return val


def _text(obj, key, where, max_len, required=True):
    if not required and key not in obj:
        return ""
    val = _req(obj, key, str, where).strip()
    if required and not val:
        raise AnalysisError(f"{where}.{key}: empty")
    if len(val) > max_len:
        raise AnalysisError(f"{where}.{key}: longer than {max_len} chars")
    return val


def _num(obj, key, where, lo, hi):
    val = _req(obj, key, float, where)
    if not lo <= val <= hi:
        raise AnalysisError(f"{where}.{key}: {val} outside [{lo}, {hi}]")
    return val


def _url(val, where):
    if val and not val.startswith("https://"):
        raise AnalysisError(f"{where}: only https:// URLs are allowed")
    return val


def _str_list(obj, key, where, max_items, max_len, required=True):
    if not required and key not in obj:
        return []
    items = _req(obj, key, list, where)
    if len(items) > max_items:
        raise AnalysisError(f"{where}.{key}: more than {max_items} items")
    out = []
    for i, item in enumerate(items):
        if not isinstance(item, str) or not item.strip() or len(item) > max_len:
            raise AnalysisError(f"{where}.{key}[{i}]: must be a non-empty string <= {max_len} chars")
        out.append(item.strip())
    return out


def validate(raw, as_of, features, held=()):
    """Return a normalized copy of the analysis or raise AnalysisError listing the first problem.

    `held`: tickers with an open position (the agent reviews them; it can't open them again)."""
    if not isinstance(raw, dict):
        raise AnalysisError("analysis must be a JSON object")
    if raw.get("as_of") != as_of:
        raise AnalysisError(f"as_of must be '{as_of}' (the last closed session), got {raw.get('as_of')!r}")
    if raw.get("contract") != CONTRACT:
        raise AnalysisError(f"contract must be '{CONTRACT}' (position trades; see agent/PROMPT.md)")

    reg = _req(raw, "regime", dict, "analysis")
    regime = {
        "label": _text(reg, "label", "regime", 20),
        "exposure": _text(reg, "exposure", "regime", 20),
        "summary": _text(reg, "summary", "regime", 1200),
        "evidence": _str_list(reg, "evidence", "regime", 10, 300),
        "disagrees_with_baseline": bool(reg.get("disagrees_with_baseline", False)),
    }
    if regime["label"] not in REGIME_LABELS:
        raise AnalysisError(f"regime.label must be one of {REGIME_LABELS}")
    if regime["exposure"] not in EXPOSURE:
        raise AnalysisError(f"regime.exposure must be one of {EXPOSURE}")

    candidates, seen = [], set()
    for i, c in enumerate(_req(raw, "candidates", list, "analysis")):
        where = f"candidates[{i}]"
        if not isinstance(c, dict):
            raise AnalysisError(f"{where}: must be an object")
        ticker = _text(c, "ticker", where, 10).upper()
        if not TICKER_RE.match(ticker) or ticker not in features:
            raise AnalysisError(f"{where}.ticker: {ticker} is not in today's feature table")
        if not features[ticker]["eligible"]:
            raise AnalysisError(f"{where}.ticker: {ticker} fails the price/liquidity floor")
        if ticker in seen:
            raise AnalysisError(f"{where}.ticker: duplicate {ticker}")
        if ticker in held:
            raise AnalysisError(f"{where}.ticker: {ticker} is already held (review it under 'reviews' instead)")
        seen.add(ticker)
        setup = _text(c, "setup", where, 30)
        if setup not in SETUPS:
            raise AnalysisError(f"{where}.setup must be one of {SETUPS}")
        catalysts = []
        for j, cat in enumerate(c.get("catalysts", [])[:6]):
            cw = f"{where}.catalysts[{j}]"
            if not isinstance(cat, dict):
                raise AnalysisError(f"{cw}: must be an object")
            date = _text(cat, "date", cw, 10)
            if not DATE_RE.match(date):
                raise AnalysisError(f"{cw}.date: YYYY-MM-DD required (undated claims are not allowed)")
            catalysts.append({"date": date, "text": _text(cat, "text", cw, 300),
                              "source_url": _url(_text(cat, "source_url", cw, 500, required=False), cw)})
        candidates.append({
            "ticker": ticker, "setup": setup,
            "conviction": int(_num(c, "conviction", where, 1, 5)),
            "thesis": _text(c, "thesis", where, 1500),
            "stop_atr": _num(c, "stop_atr", where, *STOP_ATR_RANGE),
            "max_chase_atr": _num(c, "max_chase_atr", where, *CHASE_ATR_RANGE),
            "horizon_sessions": int(_num(c, "horizon_sessions", where, *HORIZON_RANGE)),
            "upside_case": _text(c, "upside_case", where, 600),
            "invalidation": _text(c, "invalidation", where, 400),
            "risks": _str_list(c, "risks", where, 6, 300),
            "chart_checks": _str_list(c, "chart_checks", where, 6, 200, required=False),
            "earnings_plan": _text(c, "earnings_plan", where, 300),
            "catalysts": catalysts,
        })
    if len(candidates) > MAX_CANDIDATES:
        raise AnalysisError(f"at most {MAX_CANDIDATES} new positions a day (put the rest on the watchlist)")
    for c in candidates:
        stop_pct = c["stop_atr"] * features[c["ticker"]]["atr"] / features[c["ticker"]]["close"] * 100
        if stop_pct > MAX_STOP_PCT:
            raise AnalysisError(f"{c['ticker']}: a {c['stop_atr']} ATR stop is {stop_pct:.1f}% below the close "
                                f"(max {MAX_STOP_PCT}%); narrow it or skip the name")
    if regime["exposure"] == "none" and candidates:
        raise AnalysisError("regime.exposure is 'none' but candidates were listed")

    def _named_list(key, cap, fields):
        out = []
        for i, item in enumerate(raw.get(key, [])):
            where = f"{key}[{i}]"
            if not isinstance(item, dict):
                raise AnalysisError(f"{where}: must be an object")
            ticker = _text(item, "ticker", where, 10).upper()
            if ticker not in features:
                raise AnalysisError(f"{where}.ticker: {ticker} is not in today's feature table")
            out.append({"ticker": ticker, **{f: _text(item, f, where, n) for f, n in fields}})
        if len(out) > cap:
            raise AnalysisError(f"at most {cap} {key} entries")
        return out

    reviews = []
    for i, item in enumerate(raw.get("reviews", [])):
        where = f"reviews[{i}]"
        if not isinstance(item, dict):
            raise AnalysisError(f"{where}: must be an object")
        ticker = _text(item, "ticker", where, 10).upper()
        if ticker not in held:
            raise AnalysisError(f"{where}.ticker: {ticker} is not an open position")
        action = _text(item, "action", where, 10)
        if action not in REVIEW_ACTIONS:
            raise AnalysisError(f"{where}.action must be one of {REVIEW_ACTIONS}")
        reviews.append({"ticker": ticker, "action": action, "note": _text(item, "note", where, 400)})
    if len(reviews) > MAX_REVIEWS:
        raise AnalysisError(f"at most {MAX_REVIEWS} reviews")

    return {
        "as_of": as_of,
        "contract": CONTRACT,
        "prompt_version": _text(raw, "prompt_version", "analysis", 20),
        "regime": regime,
        "candidates": candidates,
        "reviews": reviews,
        "watchlist": _named_list("watchlist", MAX_WATCH, (("trigger", 300), ("note", 400))),
        "avoid": _named_list("avoid", MAX_AVOID, (("reason", 300),)),
        "market_notes": _str_list(raw, "market_notes", "analysis", 8, 400, required=False),
        "data_issues": _str_list(raw, "data_issues", "analysis", 10, 300, required=False),
    }


def levels(candidate, feat):
    """Prices derived from the last close and ATR. Long-only. `targets` holds the +20% reference
    level (a marker for the ledger, never an exit) and `targets_r` its distance in R."""
    close, atr = feat["close"], feat["atr"]
    stop = close - candidate["stop_atr"] * atr
    risk = close - stop
    upside = close * (1 + ledger.UPSIDE_REF_PCT / 100)
    return {
        "ref_close": round(close, 2),
        "atr": round(atr, 3),
        "stop": round(stop, 2),
        "stop_pct": round(100 * (stop / close - 1), 2),
        "entry_max": round(close + candidate["max_chase_atr"] * atr, 2),
        "targets": [round(upside, 2)],
        "targets_r": [round((upside - close) / risk, 2)],
    }


def position_size(stop_pct, size_scale, earn_sessions):
    """Account % to put in the position: RISK_PER_TRADE_PCT lost at the stop, times the momentum
    size scale, halved when a report is under EARNINGS_HALF_SIZE_SESSIONS away, capped."""
    if not stop_pct:
        return None
    size = RISK_PER_TRADE_PCT / abs(stop_pct) * 100 * (size_scale if size_scale is not None else 1.0)
    if earn_sessions is not None and earn_sessions < EARNINGS_HALF_SIZE_SESSIONS:
        size /= 2
    return round(min(MAX_POSITION_PCT, size), 1)
