# =============================================================================
# The agent's output contract (runs/<as_of>/analysis.json) and the levels the
# pipeline derives from it.
#
# The agent supplies judgment: which names, why, conviction, and stop/target
# sizing in ATR multiples. The pipeline supplies every price: stop, chase
# limit and targets are computed here from the stored close and ATR. Any
# price the agent writes is ignored, so an arithmetic slip can't reach the
# dashboard or the track record.
# =============================================================================
import re

REGIME_LABELS = ("risk_on", "neutral", "risk_off")
EXPOSURE = ("full", "reduced", "minimal", "none")
SETUPS = ("breakout", "squeeze", "pullback_reclaim", "base", "other")
MAX_CANDIDATES, MAX_WATCH, MAX_AVOID = 12, 25, 20
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


def validate(raw, as_of, features):
    """Return a normalized copy of the analysis or raise AnalysisError listing the first problem."""
    if not isinstance(raw, dict):
        raise AnalysisError("analysis must be a JSON object")
    if raw.get("as_of") != as_of:
        raise AnalysisError(f"as_of must be '{as_of}' (the last closed session), got {raw.get('as_of')!r}")

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
        seen.add(ticker)
        setup = _text(c, "setup", where, 30)
        if setup not in SETUPS:
            raise AnalysisError(f"{where}.setup must be one of {SETUPS}")
        targets = _req(c, "targets_r", list, where)
        if not 1 <= len(targets) <= 3 or not all(isinstance(t, (int, float)) and 1.0 <= t <= 10.0 for t in targets):
            raise AnalysisError(f"{where}.targets_r: 1-3 numbers between 1 and 10 (R multiples)")
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
            "stop_atr": _num(c, "stop_atr", where, 1.0, 4.0),
            "max_chase_atr": _num(c, "max_chase_atr", where, 0.0, 2.0),
            "targets_r": sorted(float(t) for t in targets),
            "horizon_sessions": int(_num(c, "horizon_sessions", where, 5, 60)),
            "invalidation": _text(c, "invalidation", where, 400),
            "risks": _str_list(c, "risks", where, 6, 300),
            "chart_checks": _str_list(c, "chart_checks", where, 6, 200, required=False),
            "earnings_plan": _text(c, "earnings_plan", where, 300, required=False),
            "catalysts": catalysts,
        })
    if len(candidates) > MAX_CANDIDATES:
        raise AnalysisError(f"at most {MAX_CANDIDATES} candidates")
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

    return {
        "as_of": as_of,
        "regime": regime,
        "candidates": candidates,
        "watchlist": _named_list("watchlist", MAX_WATCH, (("trigger", 300), ("note", 400))),
        "avoid": _named_list("avoid", MAX_AVOID, (("reason", 300),)),
        "market_notes": _str_list(raw, "market_notes", "analysis", 8, 400, required=False),
        "data_issues": _str_list(raw, "data_issues", "analysis", 10, 300, required=False),
    }


def levels(candidate, feat):
    """Prices derived from the last close and ATR. Long-only."""
    close, atr = feat["close"], feat["atr"]
    stop = close - candidate["stop_atr"] * atr
    risk = close - stop
    return {
        "ref_close": round(close, 2),
        "atr": round(atr, 3),
        "stop": round(stop, 2),
        "stop_pct": round(100 * (stop / close - 1), 2),
        "entry_max": round(close + candidate["max_chase_atr"] * atr, 2),
        "targets": [round(close + r * risk, 2) for r in candidate["targets_r"]],
    }
