# =============================================================================
# Forward-tracked pick ledger: the only honest validation an LLM-driven
# analysis can have, because there is no look-ahead-free way to backtest it.
#
# Rules v2 (2026-10-30): position trades held 2-6 months. The ledger holds
# only rows made under the current rules; a rules change resets the data.
#
# Fill model (deliberately conservative):
#   - Entry is the open of the first session that opens (09:30 ET) AFTER the
#     pick was published, never the signal-day close. A scheduled 07:00 CET
#     run fills at the next session's open; a manual run during US hours
#     can't claim that day's already-printed open (look-ahead).
#   - Open above entry_max (chased too far) -> "not_filled".
#   - Open at or below the stop -> "gap_below_stop" (not filled).
#   - Stop hit intrabar -> exit at the stop, or at the open on a gap down
#     through it. The stop is a wide catastrophic stop; there are no profit
#     targets. `targets` holds the +20% reference level, and `targets_hit`
#     records when it traded before any stop.
#   - Round-trip costs: 0.10% commission + 0.10% slippage of entry, deducted
#     in R and in percent.
# Outcomes are marked at +21/42/63/126 session closes (a stopped trade keeps its
# exit) in R and in percent, next to SPY and RSP over the same window, with
# MFE/MAE in R. Rows are priced on their pick date: evaluate() takes bars in
# that basis (daily.py rescales split-adjusted bars back).
#
# Control arm: every in-context mechanical signal of the day (Chart Check's
# A/B rule, below), picked or not, is tracked with the same fill model at
# fixed default levels. Picked vs unpicked rows of the control, at identical
# levels, measure the agent's selection; picks vs the control measure
# selection and level choices together.
# =============================================================================
import datetime as dt
from zoneinfo import ZoneInfo

from . import features as feat_mod

RULES_VERSION = "v2"
COST_FRACTION = 0.002
HORIZONS = (21, 42, 63, 126)
HEADLINE = 63  # the horizon the dashboard leads with and the low-sample flag counts
LOW_SAMPLE = 30
UPSIDE_REF_PCT = 20.0  # reference marker only, never an exit
ET = ZoneInfo("America/New_York")
US_OPEN = dt.time(9, 30)
# The prompt's default levels. Fixed so the control never tunes itself.
CONTROL_STOP_ATR, CONTROL_CHASE_ATR = 4.5, 0.5


def control_setup(feat, risk_on):
    """Chart Check's in-context signal (hSignal): the SPY gate on, trend stacked, RS rising,
    not extended, and a breakout on volume or a pullback reclaim. Returns the setup or None."""
    if not (risk_on and feat and feat.get("eligible") and feat["trend_stack"] and feat["rs_rising"]):
        return None
    if feat["ext_ema21_atr"] is None or feat["ext_ema21_atr"] > feat_mod.MAX_EXT_ATR:
        return None
    tags = feat.get("tags") or []
    if "breakout" in tags and "volume_surge" in tags:
        return "breakout"
    return "pullback_reclaim" if "pullback_reclaim" in tags else None


def new_pick(as_of, candidate, lv, feat, sector, published_utc, size_scale=None):
    return {
        "id": f"{as_of}:{candidate['ticker']}", "rules_version": RULES_VERSION,
        "as_of": as_of, "published_utc": published_utc, "ticker": candidate["ticker"], "sector": sector,
        "setup": candidate["setup"], "conviction": candidate["conviction"],
        "stop_atr": candidate["stop_atr"], "horizon_sessions": candidate.get("horizon_sessions"),
        "ref_close": lv["ref_close"], "atr": lv["atr"], "stop": lv["stop"],
        "entry_max": lv["entry_max"], "targets": lv["targets"], "targets_r": lv.get("targets_r", []),
        "position_pct": lv.get("position_pct"),
        "status": "pending", "entry_date": None, "entry": None,
        "r": {}, "pct": {}, "spy_pct": {}, "rsp_pct": {}, "mfe_r": None, "mae_r": None, "mark": None,
        "exit_date": None, "exit_r": None, "exit_pct": None, "exit_reason": None, "tags": feat.get("tags", []),
        # Momentum-health size scale that day (features.momentum_health): recorded, never applied
        # to R, so the live ledger can test scaled vs unscaled results later.
        "size_scale": size_scale,
    }


def is_open(row):
    return row["status"] in ("pending", "open")


def _sessions_after(days, bars, as_of):
    return [(d.isoformat(), b) for d, b in zip(days, bars) if d.isoformat() > as_of and b is not None]


def _opens_after(day_iso, published_utc):
    if not published_utc:
        return True
    open_et = dt.datetime.combine(dt.date.fromisoformat(day_iso), US_OPEN, ET)
    return open_et > dt.datetime.fromisoformat(published_utc)


def evaluate(pick, days, bars, spy_bars, rsp_bars=None):
    """Recompute a pick's outcome from stored bars (idempotent). Returns the pick.

    `bars` must be in the pick's price basis (see daily._evaluate_and_write for splits)."""
    if not days or days[0].isoformat() > pick["as_of"]:
        return pick  # the entry bar may be older than the stored window: don't refill from a later open
    after = [(d, b) for d, b in _sessions_after(days, bars, pick["as_of"])
             if _opens_after(d, pick.get("published_utc"))]
    bench = {"spy": dict(_sessions_after(days, spy_bars, pick["as_of"])),
             "rsp": dict(_sessions_after(days, rsp_bars, pick["as_of"])) if rsp_bars else {}}
    if not after:
        return pick
    entry_day, (o, h, l, c, _) = after[0]
    if o > pick["entry_max"]:
        pick.update(status="not_filled", entry_date=entry_day, exit_reason="opened_above_entry_max")
        return pick
    if o <= pick["stop"]:
        pick.update(status="gap_below_stop", entry_date=entry_day, exit_reason="opened_below_stop")
        return pick

    entry = o
    risk = entry - pick["stop"]
    cost_r, cost_pct = COST_FRACTION * entry / risk, 100 * COST_FRACTION
    bench_entry = {k: v.get(entry_day, (None,))[0] for k, v in bench.items()}

    def bench_pct(day):
        out = {}
        for k, series in bench.items():
            close = series.get(day, (None, None, None, None))[3]
            if bench_entry[k] and close:
                out[k] = round(100 * (close / bench_entry[k] - 1), 2)
        return out

    pick.update(entry_date=entry_day, entry=round(entry, 2), r={}, pct={}, spy_pct={}, rsp_pct={},
                exit_date=None, exit_r=None, exit_pct=None, exit_reason=None)
    mfe = mae = 0.0
    exit_px = None
    targets_hit = [None] * len(pick["targets"])
    held = after[:max(HORIZONS)]
    for i, (day, (bo, bh, bl, bc, _)) in enumerate(held):
        if exit_px is None:
            if bl <= pick["stop"]:
                exit_px = min(bo, pick["stop"]) if i > 0 else pick["stop"]
                mae = max(mae, (entry - bl) / risk)
                pick.update(exit_date=day, exit_reason="stop")
            else:
                mfe = max(mfe, (bh - entry) / risk)
                mae = max(mae, (entry - bl) / risk)
                for k, target in enumerate(pick["targets"]):
                    if targets_hit[k] is None and bh >= target:
                        targets_hit[k] = day
        session_no = i + 1
        if session_no in HORIZONS:
            px = exit_px if exit_px is not None else bc
            key = str(session_no)
            pick["r"][key] = round((px - entry) / risk - cost_r, 2)
            pick["pct"][key] = round(100 * (px / entry - 1) - cost_pct, 2)
            bp = bench_pct(day)
            if "spy" in bp:
                pick["spy_pct"][key] = bp["spy"]
            if "rsp" in bp:
                pick["rsp_pct"][key] = bp["rsp"]

    last_day, last_bar = held[-1]
    px = exit_px if exit_px is not None else last_bar[3]
    pick["mark"] = {"date": last_day, "sessions": len(held), "pct": round(100 * (px / entry - 1) - cost_pct, 2),
                    **{f"{k}_pct": v for k, v in bench_pct(last_day).items()}}
    pick["mfe_r"], pick["mae_r"] = round(mfe, 2), round(mae, 2)
    pick["targets_hit"] = targets_hit
    if exit_px is not None:
        pick.update(status="stopped", exit_r=round((exit_px - entry) / risk - cost_r, 2),
                    exit_pct=round(100 * (exit_px / entry - 1) - cost_pct, 2))
    elif len(held) >= max(HORIZONS):
        last = str(max(HORIZONS))
        pick.update(status="complete", exit_r=pick["r"][last], exit_pct=pick["pct"][last], exit_reason="time")
    else:
        pick["status"] = "open"
    return pick


def _avg(vals, nd=2):
    return round(sum(vals) / len(vals), nd) if vals else None


def summarize(group):
    """Aggregate one group of picks. Small samples are flagged, never hidden."""
    filled = [p for p in group if p["entry"] is not None]
    out = {"picks": len(group), "filled": len(filled),
           "not_filled": sum(p["status"] in ("not_filled", "gap_below_stop") for p in group),
           "stopped": sum(p["status"] == "stopped" for p in group),
           "open": sum(p["status"] == "open" for p in group),
           "reached_upside": sum(bool(p.get("targets_hit") and p["targets_hit"][0]) for p in filled)}
    for h in HORIZONS:
        key = str(h)
        done = [p for p in filled if key in p.get("pct", {})]
        pct = [p["pct"][key] for p in done]
        ex_rsp = [p["pct"][key] - p["rsp_pct"][key] for p in done if key in p.get("rsp_pct", {})]
        ex_spy = [p["pct"][key] - p["spy_pct"][key] for p in done if key in p.get("spy_pct", {})]
        out[f"n_{h}"] = len(done)
        # Same-week entries share the market: distinct entry weeks are the honest sample size.
        out[f"weeks_{h}"] = len({dt.date.fromisoformat(p["entry_date"]).isocalendar()[:2] for p in done})
        out[f"avg_pct_{h}"] = _avg(pct)
        out[f"avg_r_{h}"] = _avg([p["r"][key] for p in done if key in p["r"]])
        out[f"win_rate_{h}"] = round(100 * sum(v > 0 for v in pct) / len(pct), 1) if pct else None
        out[f"avg_ex_rsp_{h}"] = _avg(ex_rsp)
        out[f"avg_ex_spy_{h}"] = _avg(ex_spy)
        out[f"beat_rsp_{h}"] = round(100 * sum(v > 0 for v in ex_rsp) / len(ex_rsp), 1) if ex_rsp else None
    marks = [p["mark"] for p in filled if p.get("mark")]
    out["avg_mark_pct"] = _avg([m["pct"] for m in marks])
    out["avg_mark_ex_rsp"] = _avg([m["pct"] - m["rsp_pct"] for m in marks if "rsp_pct" in m])
    out["avg_mfe_r"] = _avg([p["mfe_r"] for p in filled if p["mfe_r"] is not None])
    out["low_sample"] = out[f"n_{HEADLINE}"] < LOW_SAMPLE
    return out


def control_stats(rows):
    """Agent selection vs the bare signal (identical levels)."""
    return {"version": RULES_VERSION,
            "all": summarize(rows),
            "picked": summarize([r for r in rows if r["picked"]]),
            "unpicked": summarize([r for r in rows if not r["picked"]]),
            # The control is mostly pullbacks, the picks mostly breakouts: compare within a setup.
            "by_setup": {f"{label} · {'picked' if arm else 'passed on'}":
                         summarize([r for r in rows if r["setup"] == setup and r["picked"] == arm])
                         for setup, label in (("breakout", "Breakout"), ("pullback_reclaim", "Pullback")) for arm in (True, False)},
            "rule": (f"Every in-context A/B signal (SPY gate on, trend stacked, RS rising, not extended, "
                     f"breakout on {feat_mod.VOL_SURGE}x volume or pullback reclaim) at fixed levels: "
                     f"stop {CONTROL_STOP_ATR} ATR, buy up to +{CONTROL_CHASE_ATR} ATR, one open row per ticker")}


def stats(picks):
    """Aggregate track record. Small samples are flagged, never hidden."""
    by_conviction = {str(k): summarize([p for p in picks if p["conviction"] == k]) for k in range(1, 6)}
    by_setup = {}
    for p in picks:
        by_setup.setdefault(p["setup"], []).append(p)
    return {"version": RULES_VERSION, "headline": HEADLINE, "horizons": list(HORIZONS),
            "all": summarize(picks),
            "by_conviction": {k: v for k, v in by_conviction.items() if v["picks"]},
            "by_setup": {k: summarize(v) for k, v in sorted(by_setup.items())},
            "cost_assumption": "Costs: 0.10% commission + 0.10% slippage round trip"}
