---
name: pine-v6-patterns
description: Reference Pine v6 patterns for no-repaint HTF data, pivot plotting, ATR-based normalization, strategy declarations with realistic costs, confirmed-bar signals, alertcondition hygiene, and `varip` vs `var` choice. Load when writing or modifying Pine v6 code involving any of these idioms.
---

# Pine v6 Reference Patterns

Copy these patterns rather than improvising. Each one encodes a constraint that is easy to silently break — and a silent break here is a repainting or look-ahead bug that won't show up until live trading.

---

## 1. Safe higher-timeframe data

```pine
// Confirmed HTF value, no repaint
htfClose = request.security(syminfo.tickerid, "D", close[1], lookahead=barmerge.lookahead_off)
```

Rules:
- Pass `lookahead=barmerge.lookahead_off` **explicitly** every time. Never omit.
- Reference `[1]` on the inner expression if the value must be confirmed (not the still-forming HTF bar).
- For OHLC, that means `close[1]`, `high[1]`, `low[1]`, `open[1]`.

Wrong:
```pine
// Reads still-forming HTF bar — repaints intrabar
htfClose = request.security(syminfo.tickerid, "D", close)
```

---

## 2. No-repaint pivots

```pine
PIVOT_LEN = 10
ph = ta.pivothigh(high, PIVOT_LEN, PIVOT_LEN)
pl = ta.pivotlow(low,  PIVOT_LEN, PIVOT_LEN)

// Pivots confirm PIVOT_LEN bars AFTER the bar of the actual high/low.
// Plot offset by -PIVOT_LEN so the marker sits on the pivot bar — but understand
// the signal is only knowable PIVOT_LEN bars later.
plotshape(not na(ph), location=location.abovebar, offset=-PIVOT_LEN, style=shape.triangledown)
plotshape(not na(pl), location=location.belowbar, offset=-PIVOT_LEN, style=shape.triangleup)
```

A pivot signal cannot fire on the bar of the pivot itself. Any backtest that "trades on the pivot bar" without acknowledging the lag is repainting.

---

## 3. ATR-based normalization

```pine
i_atrLen   = input.int(14,   "ATR Length",         minval=1,                group="Risk")
i_atrStopX = input.float(2.0,"ATR Stop Multiplier",minval=0.1, step=0.1,    group="Risk")
i_atrTgtX  = input.float(3.0,"ATR Target Multiplier",minval=0.1, step=0.1,  group="Risk")

atr     = ta.atr(i_atrLen)
longStop = strategy.position_avg_price - i_atrStopX * atr
longTgt  = strategy.position_avg_price + i_atrTgtX  * atr

// Thresholds also in ATR units:
strongMove = math.abs(close - close[5]) > 1.5 * atr
```

Never write `close - entry > 0.50`. That literal is per-symbol and breaks the script on every other instrument.

---

## 4. Strategy declaration with realistic costs

```pine
//@version=6
strategy(
    title                   = "MyStrategy v1",
    overlay                 = true,
    initial_capital         = 10000,
    default_qty_type        = strategy.percent_of_equity,
    default_qty_value       = 10,
    commission_type         = strategy.commission.percent,
    commission_value        = 0.05,
    slippage                = 2,
    calc_on_every_tick      = false,
    process_orders_on_close = false,
    pyramiding              = 0
)
```

A backtest result quoted from a strategy without these is not a backtest — it's a fantasy. Always parameterize commission and slippage so they can be tuned per venue.

---

## 5. Confirmed-bar signal (no intrabar repaint)

```pine
longSignal = ta.crossover(ema1, ema2) and close > ta.ema(close, 200)

if barstate.isconfirmed and longSignal
    strategy.entry("L", strategy.long)

// For indicator alerts, gate on confirmed bar or use [1]:
alertcondition(longSignal[1], title="Long (confirmed)", message="...")
```

`barstate.isconfirmed` is true only at bar close. If you want intrabar alerts (with the trade-off that they may flip before close), label this in the script header so the user knows.

---

## 6. Alertcondition hygiene

```pine
alertcondition(
    condition = longSignal and barstate.isconfirmed,
    title     = "Long Entry",
    message   = "{{ticker}} long @ {{close}} | ATR={{plot_0}}"
)
```

Every `alertcondition` needs:
- A confirmation guard — `barstate.isconfirmed` or `[1]` on the condition.
- A unique, descriptive `title`.
- A `message` carrying `{{ticker}}`, `{{close}}`, and any context the user needs at execution time.

---

## 7. `var` vs `varip` — pick correctly

```pine
// OK — UI state that should survive intrabar
varip int lastUserClickBar = na

// NOT OK for signal state — varip updates every tick, breaks bar-replay reproducibility
// varip float runningHigh = na

// Use `var` for signal/persistent state
var float runningHigh = na
if high > nz(runningHigh, high)
    runningHigh := high
```

Rule of thumb: if removing this state would change a backtest result, it must be `var`, never `varip`.

---

## 8. Input + group layout (match repo convention)

```pine
// ===========================================================
// INPUTS
// ===========================================================

i_emaFast = input.int(9,     "EMA Fast",                  minval=1,                group="EMA")
i_emaSlow = input.int(21,    "EMA Slow",                  minval=1,                group="EMA")

i_atrLen  = input.int(14,    "ATR Length",                minval=1,                group="Risk")
i_atrMult = input.float(2.0, "ATR Stop Multiplier",       minval=0.1, step=0.1,    group="Risk")

i_useRS   = input.bool(true, "Use Relative Strength Filter",                       group="Filters")
```

Match the column alignment, capitalization, and group casing used by the current scripts in `indicators/`. Visual consistency is part of code quality here — these scripts live side by side in the TradingView editor.

---

## 9. Section banner style

```pine
// ============================================================
// 1. MARKET STRUCTURE — HH / HL / LH / LL + BOS / ChoCH
// ============================================================
```

Use the same banner format the existing scripts use. Number sections when there are more than three.

---

## 10. Defensive request.security with helper

If you have multiple HTF reads, wrap the pattern in a helper to make it impossible to forget `lookahead_off`:

```pine
f_secureHtf(sym, tf, src) =>
    request.security(sym, tf, src[1], lookahead=barmerge.lookahead_off)

dailyClose = f_secureHtf(syminfo.tickerid, "D", close)
weeklyHigh = f_secureHtf(syminfo.tickerid, "W", high)
```

One place to enforce the rule, applied everywhere.

---

## 11. Variable-offset history reads need `max_bars_back`

When a loop or function reads a series with a runtime-variable offset (`src[i]` where the range comes from an input), Pine cannot infer the buffer size — deep history reads will error or silently truncate. Reserve the buffer explicitly, sized to the input's **maxval** with headroom:

```pine
i_trainLen = input.int(100, "Training Window", minval=20, maxval=300)
atrPct = ta.atr(14) / close * 100.0
max_bars_back(atrPct, 350)   // ≥ the input's maxval, with headroom — NOT the default

f_windowStat(float src, int len) =>
    float acc = 0.0
    for i = 1 to len
        acc += nz(src[i])
    acc / len
```

Rules:
- Buffer ≥ the length input's `maxval`, not its default.
- Start the window at `[1]`, not `[0]`, if the statistic must be past-only (no forming-bar leak).

---

## 12. Frozen offline-model inference (train/serve parity)

When porting an offline-trained model (logistic weights, centroids) into Pine:

```pine
// Features use FROZEN training constants — NOT the display inputs — for exact
// train/serve parity with <training script>. DO NOT parameterize or "deduplicate"
// these with the script's inputs; changing any constant silently breaks parity.
mlAtr   = ta.atr(14)          // FROZEN (training used ATR14)
mlEma20 = ta.ema(close, 20)   // FROZEN

const float W0   = +0.038264   // feature_name — exported YYYY-MM-DD, <source>
const float BIAS = -0.028780
score = 1.0 / (1.0 + math.exp(-(BIAS + W0 * f0 /* + ... */)))
```

Rules:
- Weights are `const`, one per line, each commented with its feature name and export provenance.
- Feature constants are hardcoded and marked FROZEN — the one sanctioned exception to "parameterize via `input.*`" (pine-reviewer checks 3 / 8).
- All features trailing-only; document any sanctioned same-bar read in the note with why it is not a leak.
- Record the validation (method, metric, date) in the private note; re-export weights only through the training pipeline, never hand-edit.
