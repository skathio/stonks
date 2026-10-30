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
| Green / red window | A past trade: green zone from entry to target 1, red zone from stop to entry. The stronger shade shows how it ended. The label gives R and % after costs. Dotted = still open |

## Panel

The header shows **which session is scored** and the verdict:

- **CONFIRM:** trend, market and relative strength all line up, and there's a setup on that bar.
- **CAUTION:** something is missing. The header names what.
- **AVOID:** a hard failure: below EMA50, extended more than 4 ATR, earnings within 4
  sessions, or below the pinned stop.

The compact panel shows the setup, volume, extension, next earnings date (as TradingView reports
it) and **Past signals**. The full panel adds the SPY gate, trend stack, RS vs SPY, distance to the
prior-20 and 52-week highs, base range, ATR % and the levels mode.

**Past signals** reads like `7 trades · 57% up`, `avg +0.6R · T1 3`: seven past trades, 57% closed
positive after costs, an average of +0.6R after costs, and three reached target 1. Under 30 trades
it says "small n" and stays grey, the same threshold the dashboard's Record tab uses. When pinned
to a dashboard date it adds "to today", because it still counts trades after that date. It's this one stock's history, so treat it as context, not as a track record. The
dashboard's Record tab is the real one.

### How past trades are counted

A past signal counts when the panel would have called it CONFIRM that day (earnings excepted):
SPY uptrend, trend stacked, RS rising, not extended, plus a breakout on at least 1.3× volume or a
pullback reclaim. It is then traded exactly as the dashboard's ledger trades a pick:

- Entry at the next session's open, skipped when that open is above the buy-up-to limit or at or
  below the stop.
- Exit at the stop (at the open if it gaps through), or at the close of the 20th session.
- Targets are marked, not taken.
- 0.2% round-trip costs, deducted in R.
- One trade at a time, so overlapping signals don't double-count the same move.

Values close to a threshold turn amber. Vendor data can differ slightly near a boundary.

## Inputs

| Group | Input | Default | What it does |
|---|---|---|---|
| Dashboard Hand-off | Pin to dashboard date | off | Off: scores the last closed session. On: scores the date below. |
| | Dashboard as_of (YYYY-MM-DD) | — | The session date from the dashboard |
| | Stop (ATR) | 2.0 | Stop distance for the stop line and for past trades |
| | Max chase (ATR) | 0.5 | Buy-up-to line above the reference close |
| | Target 1 / Target 2 (R) | 2 / 4 | Target lines as multiples of the stop distance (0 = off). Target 1 also sets the past-trade green zone |
| | Horizon (sessions) | 20 | Position of the horizon tick; flags earnings inside it. Past trades always hold 20 sessions, like the ledger |
| Display | EMAs, structure, levels, panel | on | Toggle each layer |
| | Borderline band (%) | 5 | How close to a threshold counts as amber |
| | Markers: last N bars | 120 | Older markers are hidden (0 = all) |
| Panel | Position / text size / compact | bottom right / small / on | Where and how big; compact shows the six rows you act on |
| | Tall panel | on | One narrow column, each label above its value, so it covers less of the chart on a phone. Off = two columns |
| History | Show past trade windows | on | Draw the past trades (the panel row is always on) |
| | History window (bars) | 504 | Only signals in the last N bars count (about two years; max 2000) |

Use the dashboard pick's stop, chase and target values. Adjusting them until one chart's past
trades look good is fitting to that stock, and it says nothing about the next trade.

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
