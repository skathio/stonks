# =============================================================================
# Forward-tracked pick ledger: the only honest validation an LLM-driven
# analysis can have, because there is no look-ahead-free way to backtest it.
#
# Fill model (deliberately conservative):
#   - Entry is the open of the first session that opens (09:30 ET) AFTER the
#     pick was published, never the signal-day close. A scheduled 07:00 CET
#     run fills at the next session's open; a manual run during US hours
#     can't claim that day's already-printed open (look-ahead).
#   - Open above entry_max (chased too far) -> "not_filled".
#   - Open at or below the stop -> "gap_below_stop" (not filled).
#   - Stop hit intrabar -> exit at the stop, or at the open on a gap down
#     through it.
#   - Targets are not exits: outcomes are marked to market at fixed horizons.
#     `targets_hit` records whether each target traded before any stop. On the
#     bar where the stop is hit, targets don't count (conservative).
#   - Round-trip costs: 0.10% commission + 0.10% slippage of entry, deducted
#     in R terms.
# Outcomes are marked at +5/+10/+20 session closes, with MFE/MAE in R. SPY's
# return over the same window is recorded as the benchmark.
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

COST_FRACTION = 0.002
HORIZONS = (5, 10, 20)
LOW_SAMPLE = 30
ET = ZoneInfo("America/New_York")
US_OPEN = dt.time(9, 30)
# The prompt's default levels. Fixed so the control never tunes itself.
CONTROL_STOP_ATR, CONTROL_CHASE_ATR, CONTROL_TARGETS_R = 2.0, 0.5, [2, 4]


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


def new_pick(as_of, candidate, lv, feat, sector, published_utc):
    return {
        "id": f"{as_of}:{candidate['ticker']}",
        "as_of": as_of, "published_utc": published_utc, "ticker": candidate["ticker"], "sector": sector,
        "setup": candidate["setup"], "conviction": candidate["conviction"],
        "stop_atr": candidate["stop_atr"], "targets_r": candidate["targets_r"],
        "ref_close": lv["ref_close"], "atr": lv["atr"], "stop": lv["stop"],
        "entry_max": lv["entry_max"], "targets": lv["targets"],
        "status": "pending", "entry_date": None, "entry": None,
        "r": {}, "spy_pct": {}, "mfe_r": None, "mae_r": None,
        "exit_date": None, "exit_r": None, "exit_reason": None, "tags": feat.get("tags", []),
    }


def _sessions_after(days, bars, as_of):
    return [(d.isoformat(), b) for d, b in zip(days, bars) if d.isoformat() > as_of and b is not None]


def _opens_after(day_iso, published_utc):
    if not published_utc:
        return True
    open_et = dt.datetime.combine(dt.date.fromisoformat(day_iso), US_OPEN, ET)
    return open_et > dt.datetime.fromisoformat(published_utc)


def evaluate(pick, days, bars, spy_bars):
    """Recompute a pick's outcome from stored bars (idempotent). Returns the pick."""
    after = [(d, b) for d, b in _sessions_after(days, bars, pick["as_of"])
             if _opens_after(d, pick.get("published_utc"))]
    spy_after = dict(_sessions_after(days, spy_bars, pick["as_of"]))
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
    cost_r = COST_FRACTION * entry / risk
    spy_entry = spy_after.get(entry_day, (None,))[0]
    pick.update(entry_date=entry_day, entry=round(entry, 2), r={}, spy_pct={})
    mfe = mae = 0.0
    exit_r = None
    targets_hit = [None] * len(pick["targets"])
    for i, (day, (bo, bh, bl, bc, _)) in enumerate(after[:max(HORIZONS)]):
        if exit_r is None:
            if bl <= pick["stop"]:
                fill = min(bo, pick["stop"]) if i > 0 else pick["stop"]
                exit_r = (fill - entry) / risk - cost_r
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
            pick["r"][str(session_no)] = round(exit_r if exit_r is not None else (bc - entry) / risk - cost_r, 2)
            spy_close = spy_after.get(day, (None, None, None, None))[3]
            if spy_entry and spy_close:
                pick["spy_pct"][str(session_no)] = round(100 * (spy_close / spy_entry - 1), 2)

    held = len(after[:max(HORIZONS)])
    pick["mfe_r"], pick["mae_r"] = round(mfe, 2), round(mae, 2)
    pick["targets_hit"] = targets_hit
    if exit_r is not None:
        pick.update(status="stopped", exit_r=round(exit_r, 2))
    elif held >= max(HORIZONS):
        pick.update(status="complete", exit_r=pick["r"][str(max(HORIZONS))], exit_reason="time")
    else:
        pick["status"] = "open"
    return pick


def summarize(group):
    """Aggregate one group of picks. Small samples are flagged, never hidden."""
    filled = [p for p in group if p["entry"] is not None]
    out = {"picks": len(group), "filled": len(filled),
           "not_filled": sum(p["status"] in ("not_filled", "gap_below_stop") for p in group),
           "stopped": sum(p["status"] == "stopped" for p in group)}
    for h in HORIZONS:
        vals = [p["r"][str(h)] for p in filled if str(h) in p["r"]]
        spy = [p["spy_pct"][str(h)] for p in filled if str(h) in p["spy_pct"]]
        out[f"n_{h}"] = len(vals)
        out[f"avg_r_{h}"] = round(sum(vals) / len(vals), 2) if vals else None
        out[f"win_rate_{h}"] = round(100 * sum(v > 0 for v in vals) / len(vals), 1) if vals else None
        out[f"spy_avg_pct_{h}"] = round(sum(spy) / len(spy), 2) if spy else None
    mfes = [p["mfe_r"] for p in filled if p["mfe_r"] is not None]
    out["avg_mfe_r"] = round(sum(mfes) / len(mfes), 2) if mfes else None
    out["low_sample"] = out[f"n_{max(HORIZONS)}"] < LOW_SAMPLE
    return out


def control_stats(rows):
    return {"all": summarize(rows),
            "picked": summarize([r for r in rows if r["picked"]]),
            "unpicked": summarize([r for r in rows if not r["picked"]]),
            # The control is mostly pullbacks, the picks mostly breakouts: compare within a setup.
            "by_setup": {f"{label} · {'picked' if arm else 'passed on'}":
                         summarize([r for r in rows if r["setup"] == setup and r["picked"] == arm])
                         for setup, label in (("breakout", "Breakout"), ("pullback_reclaim", "Pullback")) for arm in (True, False)},
            "rule": (f"Every in-context A/B signal (SPY gate on, trend stacked, RS rising, not extended, "
                     f"breakout on {feat_mod.VOL_SURGE}x volume or pullback reclaim) at fixed levels: "
                     f"stop {CONTROL_STOP_ATR} ATR, buy up to +{CONTROL_CHASE_ATR} ATR")}


def stats(picks):
    """Aggregate track record. Small samples are flagged, never hidden."""
    by_conviction = {str(k): summarize([p for p in picks if p["conviction"] == k]) for k in range(1, 6)}
    by_setup = {}
    for p in picks:
        by_setup.setdefault(p["setup"], []).append(p)
    return {"all": summarize(picks),
            "by_conviction": {k: v for k, v in by_conviction.items() if v["picks"]},
            "by_setup": {k: summarize(v) for k, v in sorted(by_setup.items())},
            "cost_assumption": "Costs: 0.10% commission + 0.10% slippage round trip"}
