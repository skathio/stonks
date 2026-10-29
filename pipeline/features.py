# =============================================================================
# Per-ticker features and market regime.
#
# Definitions mirror the Momentum Edge Pine indicators (indicators/*.pine) so
# that what the agent reads matches what the chart shows in TradingView:
#   EMA 9/21/50, SPY EMA50 risk-on gate, RS = close/SPY smoothed by EMA20 and
#   "rising" over 5 bars, squeeze = BB(20, 2) inside KC(20, 1.5 x ATR),
#   breakout = close above prior 20-bar high, pullback = touch of a rising
#   EMA21 within 0.5 ATR in the last 8 bars then a reclaim with a body of at
#   least 0.5 ATR, volume surge = 1.3 x 20-bar average, extension cap 4 ATR.
#
# Every distance is in ATR multiples or percent, never in currency units.
# All values use completed daily bars only: the newest bar is the last closed
# session, so nothing here can repaint.
# =============================================================================
import math

MIN_BARS = 210
MIN_PRICE = 5.0              # SEC penny-stock line: eligibility, not a signal
MIN_ADV_USD = 20_000_000     # 20-day average dollar volume floor
ATR_LEN = 14
EMA_FAST, EMA_MID, EMA_BASE = 9, 21, 50
BB_LEN, BB_STD, KC_MULT = 20, 2.0, 1.5
SQUEEZE_RECENCY = 15
BREAKOUT_LEN = 20
PULL_LOOK, PULL_SLOPE, PULL_TOL_ATR, BODY_ATR = 8, 10, 0.5, 0.5
VOL_MA, VOL_SURGE = 20, 1.3
MAX_EXT_ATR = 4.0
RS_EMA, RS_RISING = 20, 5
# A one-day close-to-close move this large in an S&P 900 name, after split
# adjustment, is almost always a ticker re-use (e.g. BNY was a closed-end fund
# before BNY Mellon took the symbol) or a bad print, not a real move.
HISTORY_BREAK_MOVE = 0.60


# =============================================================================
# Series primitives
# =============================================================================
def ema(values, length):
    out, k, prev = [], 2.0 / (length + 1), None
    for v in values:
        prev = v if prev is None else prev + k * (v - prev)
        out.append(prev)
    return out


def sma(values, length):
    out, run = [], 0.0
    for i, v in enumerate(values):
        run += v
        if i >= length:
            run -= values[i - length]
        out.append(run / length if i >= length - 1 else None)
    return out


def atr_wilder(highs, lows, closes, length=ATR_LEN):
    trs = []
    for i in range(len(closes)):
        if i == 0:
            trs.append(highs[0] - lows[0])
        else:
            pc = closes[i - 1]
            trs.append(max(highs[i] - lows[i], abs(highs[i] - pc), abs(lows[i] - pc)))
    out, prev = [], None
    for i, tr in enumerate(trs):
        if i < length - 1:
            out.append(None)
        elif i == length - 1:
            prev = sum(trs[:length]) / length
            out.append(prev)
        else:
            prev = (prev * (length - 1) + tr) / length
            out.append(prev)
    return out


def stdev(values, length):
    out = []
    for i in range(len(values)):
        if i < length - 1:
            out.append(None)
            continue
        window = values[i - length + 1:i + 1]
        mean = sum(window) / length
        out.append(math.sqrt(sum((x - mean) ** 2 for x in window) / length))
    return out


def pct_return(closes, n):
    if len(closes) <= n or closes[-n - 1] <= 0:
        return None
    return closes[-1] / closes[-n - 1] - 1.0


def percentile_ranks(values):
    """{key: 0-100 percentile} for a {key: number} dict, ignoring None."""
    items = sorted((v, k) for k, v in values.items() if v is not None)
    n = len(items)
    return {k: round(100.0 * i / (n - 1), 1) if n > 1 else 50.0 for i, (_, k) in enumerate(items)}


def history_break(bars):
    """Index into `bars` after the last implausible jump, or 0 if the series is continuous."""
    prev, cut = None, 0
    for i, b in enumerate(bars):
        if b is None:
            continue
        if prev is not None and prev > 0 and abs(b[3] / prev - 1) > HISTORY_BREAK_MOVE:
            cut = i
        prev = b[3]
    return cut


def _clean(bars):
    """Drop days with no bar (halts / pre-listing). Returns aligned lists."""
    rows = [b for b in bars if b is not None]
    return ([r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows],
            [r[3] for r in rows], [r[4] for r in rows])


def _r(x, nd=2):
    return None if x is None else round(x, nd)


# =============================================================================
# Per-ticker features
# =============================================================================
def ticker_features(bars, spy_closes_by_day, days):
    """Feature dict for one ticker, or None if history is too short.

    bars: list aligned with `days` of (o,h,l,c,v) or None.
    spy_closes_by_day: {day: spy close} for the RS line.
    """
    if bars[-1] is None:
        return None  # no bar on the latest session (halted / delisted)
    cut = history_break(bars)
    if cut:
        bars, days = bars[cut:], days[cut:]
    present_days = [d for d, b in zip(days, bars) if b is not None]
    opens, highs, lows, closes, vols = _clean(bars)
    n = len(closes)
    if n < MIN_BARS:
        return None

    close, open_ = closes[-1], opens[-1]
    atr = atr_wilder(highs, lows, closes)[-1]
    if not atr or atr <= 0:
        return None
    e9, e21, e50 = ema(closes, EMA_FAST), ema(closes, EMA_MID), ema(closes, EMA_BASE)
    s50, s200 = sma(closes, 50), sma(closes, 200)

    # Squeeze: Bollinger Bands inside Keltner Channel (basis SMA20, ATR14).
    basis, sd = sma(closes, BB_LEN), stdev(closes, BB_LEN)
    atr_series = atr_wilder(highs, lows, closes)
    squeeze = [None if basis[i] is None or atr_series[i] is None else
               (basis[i] + BB_STD * sd[i] <= basis[i] + KC_MULT * atr_series[i])
               for i in range(n)]
    recent_sq = [i for i in range(n - SQUEEZE_RECENCY, n) if squeeze[i]]
    bars_since_squeeze = (n - 1 - recent_sq[-1]) if recent_sq else None

    prior_high = max(highs[-BREAKOUT_LEN - 1:-1])
    breakout_today = close > prior_high
    hi252 = max(highs[-252:])
    lo252 = min(lows[-252:])

    ema21_rising = e21[-1] > e21[-1 - PULL_SLOPE]
    touched = any(lows[i] <= e21[i] + PULL_TOL_ATR * atr for i in range(n - PULL_LOOK, n))
    reclaim_today = close > e21[-1] and (close - open_) >= BODY_ATR * atr
    pullback_reclaim = ema21_rising and touched and reclaim_today and e21[-1] > e50[-1]

    vol_ma = sum(vols[-VOL_MA:]) / VOL_MA
    adv_usd = sum(c * v for c, v in zip(closes[-VOL_MA:], vols[-VOL_MA:])) / VOL_MA

    # RS line vs SPY on common days, EMA20-smoothed, rising over 5 bars.
    rs = [c / spy_closes_by_day[d] for d, c in zip(present_days, closes) if spy_closes_by_day.get(d)]
    rs_e = ema(rs, RS_EMA) if len(rs) > RS_EMA + RS_RISING else None
    rs_rising = bool(rs_e and rs_e[-1] > rs_e[-1 - RS_RISING])

    ext_atr = (close - e21[-1]) / atr
    dist_high_atr = (hi252 - close) / atr
    base_range_atr = (max(highs[-15:]) - min(lows[-15:])) / atr

    tags = []
    if breakout_today:
        tags.append("breakout")
    if bars_since_squeeze is not None:
        tags.append("squeeze" if bars_since_squeeze == 0 else "post_squeeze")
    if pullback_reclaim:
        tags.append("pullback_reclaim")
    if dist_high_atr <= 2.0:
        tags.append("near_52w_high")
    if ext_atr > MAX_EXT_ATR:
        tags.append("extended")
    if vols[-1] >= VOL_SURGE * vol_ma:
        tags.append("volume_surge")

    trend_stack = close > e50[-1] and e21[-1] > e50[-1] and (s200[-1] is None or s50[-1] > s200[-1])
    return {
        "close": _r(close), "atr": _r(atr, 3), "atr_pct": _r(100 * atr / close),
        "chg_1d_pct": _r(100 * (close / closes[-2] - 1)),
        "ret_5d_pct": _r(100 * pct_return(closes, 5)), "ret_21d_pct": _r(100 * pct_return(closes, 21)),
        "ret_63d_pct": _r(100 * pct_return(closes, 63)), "ret_126d_pct": _r(100 * pct_return(closes, 126)),
        "ret_252d_pct": _r(100 * pct_return(closes, 252)) if n > 252 else None,
        "ext_ema21_atr": _r(ext_atr), "close_vs_ema50_atr": _r((close - e50[-1]) / atr),
        "close_vs_sma200_pct": _r(100 * (close / s200[-1] - 1)) if s200[-1] else None,
        "ema21_slope_atr": _r((e21[-1] - e21[-1 - PULL_SLOPE]) / atr),
        "sma200_rising": bool(s200[-1] and s200[-21] and s200[-1] > s200[-21]),
        "trend_stack": trend_stack,
        "dist_52wh_atr": _r(dist_high_atr), "pct_off_52wh": _r(100 * (close / hi252 - 1)),
        "pct_above_52wl": _r(100 * (close / lo252 - 1)),
        "base_range_15d_atr": _r(base_range_atr),
        "bars_since_squeeze": bars_since_squeeze,
        "prior_20d_high_dist_atr": _r((prior_high - close) / atr),
        "vol_ratio": _r(vols[-1] / vol_ma) if vol_ma else None,
        "adv20_usd_m": _r(adv_usd / 1e6, 1),
        "rs_rising": rs_rising,
        "tags": tags,
        "eligible": close >= MIN_PRICE and adv_usd >= MIN_ADV_USD,
        "history_break": bool(cut),
        "_rs_composite": _rs_composite(closes),
        "_sma50": s50[-1], "_sma200": s200[-1], "_ema21": e21[-1], "_ema50": e50[-1],
        "_hi252": hi252, "_lo252": lo252, "_high": highs[-1], "_low": lows[-1],
    }


def _rs_composite(closes):
    """IBD-style weighting of 3/6/9/12-month returns (recent quarter double-weighted)."""
    parts = [(pct_return(closes, 63), 2), (pct_return(closes, 126), 1),
             (pct_return(closes, 189), 1), (pct_return(closes, 252), 1)]
    usable = [(r, w) for r, w in parts if r is not None]
    if not usable:
        return None
    return sum(r * w for r, w in usable) / sum(w for _, w in usable)


def finalize_rs(features):
    """Add universe-relative RS percentile (0-100) and strip private fields."""
    ranks = percentile_ranks({t: f["_rs_composite"] for t, f in features.items()})
    for t, f in features.items():
        f["rs_rank"] = ranks.get(t)
    return features


# =============================================================================
# Market regime and breadth
# =============================================================================
def benchmark_state(bars):
    opens, highs, lows, closes, _ = _clean(bars)
    if len(closes) < 60:
        return None
    e50 = ema(closes, 50)
    s200 = sma(closes, 200)
    atr = atr_wilder(highs, lows, closes)[-1]
    hi252 = max(highs[-252:])
    return {
        "close": _r(closes[-1]),
        "above_ema50": closes[-1] > e50[-1],
        "ema50_rising": e50[-1] > e50[-6],      # i_mktEmaLen / RS-rising lookback
        "risk_on_gate": closes[-1] > e50[-1] and e50[-1] > e50[-6],
        "close_vs_sma200_pct": _r(100 * (closes[-1] / s200[-1] - 1)) if s200[-1] else None,
        "ret_5d_pct": _r(100 * pct_return(closes, 5)), "ret_21d_pct": _r(100 * pct_return(closes, 21)),
        "ret_63d_pct": _r(100 * pct_return(closes, 63)),
        "drawdown_from_52wh_pct": _r(100 * (closes[-1] / hi252 - 1)),
        "atr_pct": _r(100 * atr / closes[-1]) if atr else None,
    }


def breadth(panel, tickers, days, lookback=20):
    """Breadth over the scan universe for the last `lookback` sessions (oldest first)."""
    series = []
    for offset in range(lookback - 1, -1, -1):
        end = len(days) - offset
        above50 = above200 = adv = dec = highs = lows = counted = 0
        for t in tickers:
            bars = [b for b in panel[t][:end] if b is not None]
            if len(bars) < 201 or panel[t][end - 1] is None:
                continue
            closes = [b[3] for b in bars]
            c = closes[-1]
            counted += 1
            above50 += c > sum(closes[-50:]) / 50
            above200 += c > sum(closes[-200:]) / 200
            adv += c > closes[-2]
            dec += c < closes[-2]
            window = bars[-252:]
            highs += bars[-1][1] >= max(b[1] for b in window)
            lows += bars[-1][2] <= min(b[2] for b in window)
        if counted:
            series.append({
                "date": days[end - 1].isoformat(), "n": counted,
                "pct_above_sma50": _r(100 * above50 / counted, 1),
                "pct_above_sma200": _r(100 * above200 / counted, 1),
                "advancers": adv, "decliners": dec, "new_52w_highs": highs, "new_52w_lows": lows,
            })
    return series


def baseline_regime(spy, breadth_series, vix):
    """Mechanical reference label. The agent may disagree but must say why."""
    latest = breadth_series[-1] if breadth_series else {}
    score = 0
    score += 1 if spy and spy["risk_on_gate"] else -1
    score += 1 if latest.get("pct_above_sma50", 50) >= 55 else (-1 if latest.get("pct_above_sma50", 50) < 40 else 0)
    score += 1 if latest.get("pct_above_sma200", 50) >= 55 else (-1 if latest.get("pct_above_sma200", 50) < 40 else 0)
    if vix is not None:
        score += 1 if vix < 18 else (-1 if vix > 26 else 0)
    label = "risk_on" if score >= 2 else ("risk_off" if score <= -2 else "neutral")
    return {"label": label, "score": score, "rule": "SPY EMA50 gate +/-1, %>SMA50 and %>SMA200 (55/40) +/-1 each, VIX (18/26) +/-1"}
