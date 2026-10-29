# Momentum Edge — Chart Check

A single daily overlay for checking a flagged stock at a glance. It marks
continuation setups on the chart, draws the structure around them, and shows a
one-glance verdict panel. It replaces the earlier two-indicator pair (Swing Engine +
Regime & Quality).

> **Disclaimer:** This is an indicator, not financial advice. It places no orders.

## What you see

| Element | Meaning |
|---|---|
| **A** marker | Breakout above the prior 20-bar high, within 15 bars of a volatility squeeze |
| **b** marker | Breakout with no recent squeeze |
| **B** marker | Pullback to a rising EMA21, then a strong reclaim |
| Marker shade | Solid = volume at least 1.3× its 20-day average · faded = below · grey = trend not stacked |
| Small dots under bars | Volatility squeeze (Bollinger Bands inside the Keltner Channel) |
| Step line | Prior 20-bar high (the breakout level) |
| Dotted green line | 52-week high |
| Grey box | The last 15 bars (the base), labelled with its range in ATR |
| Red background | Price more than 4 ATR above EMA21 (extended) |
| Dashed lines | Reference close, buy-up-to limit, stop, and R-multiple targets |
| Short vertical tick | End of the holding horizon |

## Panel

The header shows **which session is scored** and the verdict:

- **CONFIRM:** trend, market and relative strength all line up, and there's a setup on that bar.
- **CAUTION:** something is missing. The header names what.
- **AVOID:** a hard failure: below EMA50, extended more than 4 ATR, earnings within 4
  sessions, or below the pinned stop.

The rows below it are the SPY gate, trend stack, RS vs SPY, setup, volume, extension,
distance to the prior-20 and 52-week highs, base range, ATR %, and the next earnings date
(as TradingView reports it).

Values close to a threshold turn amber. Vendor data can differ slightly near a boundary.

## Inputs

| Group | Input | Default | What it does |
|---|---|---|---|
| Dashboard Hand-off | Pin to dashboard date | off | Off: scores the last closed session. On: scores the date below. |
| | Dashboard as_of (YYYY-MM-DD) | — | The session date from the dashboard |
| | Stop (ATR) | 2.0 | Stop distance used for the stop line |
| | Max chase (ATR) | 0.5 | Buy-up-to line above the reference close |
| | Target 1 / Target 2 (R) | 2 / 4 | Target lines as multiples of the stop distance (0 = off) |
| | Horizon (sessions) | 20 | Position of the horizon tick; flags earnings inside it |
| Display | EMAs, structure, levels, panel | on | Toggle each layer |
| | Borderline band (%) | 5 | How close to a threshold counts as amber |

The signal definitions are fixed on purpose and have no inputs. To match a dashboard pick,
type in its as_of date, stop and targets, and the lines will line up with its prices.

## Alerts

All alerts fire on the bar close:
- A squeeze breakout
- B pullback reclaim
- Close below the pinned stop
- Turned AVOID

## Compatibility

- TradingView, Pine Script v6, **daily timeframe only**. Other timeframes show a notice.
- US equities, benchmarked against SPY.
- Leave dividend adjustment **off** to match the split-adjusted daily data the dashboard uses.
