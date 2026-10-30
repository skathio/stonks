# Momentum Edge — Chart Check

A single daily overlay for checking a flagged stock at a glance. It marks
continuation setups on the chart, draws the structure around them, and shows a
one-glance verdict panel. It is set up for position trades held 2–6 months: a wide
stop, no profit targets, and a size for each position. It replaces the earlier two-indicator pair (Swing Engine +
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
| Dashed lines | Reference close, buy-up-to limit and stop |
| Dotted green line | +20% above the reference close: a reference level, not a target or an exit |
| Short vertical tick | End of the planned hold (when a full review is due) |
| Green / red window | A past trade: green zone from entry to the +20% level, red zone from stop to entry. The stronger shade shows how it ended. The label gives % and R after costs. Dotted = still open |

## Panel

The header shows **which session is scored** and the verdict:

- **CONFIRM:** trend, market and relative strength all line up, and there's a setup on that bar.
- **CAUTION:** something is missing. The header names what.
- **AVOID:** a hard failure: below EMA50, extended more than 4 ATR, earnings within 4
  sessions (no new entry; later reports are held through), or below the pinned stop.

The compact panel shows the setup, volume, extension, next earnings date (as TradingView reports
it; amber within 15 sessions, where positions are opened at half size), **Position size** and
**Past signals**. The full panel adds the SPY gate, trend stack, RS vs SPY, distance to the
prior-20 and 52-week highs, base range, ATR % and the levels mode.

**Position size** is the account % to put in: the risk per trade divided by the stop distance,
times the momentum size scale you copy from the dashboard, halved within 15 sessions of a report and
capped at 15%. A stop more than 15% below the price shows a warning instead: the dashboard won't take
it.

**Past signals** reads like `4 trades · 50% up`, `avg +6.1% (63d +2.3%)`, `vs RSP +1.8% (trade window) · +20% 1`:
four past trades, half closed positive after costs, an average of +6.1% at the exit and +2.3% at 63
sessions, 1.8 points ahead of the equal-weight S&P 500 (RSP) over each trade's own holding period ("trade window"), and one traded
+20%. Under 30 trades
it says "small n" and stays grey, the same threshold the dashboard's Record tab uses. When pinned
to a dashboard date it adds "to today", because it still counts trades after that date. It's this one stock's history, so treat it as context, not as a track record. The
dashboard's Record tab is the real one.

### How past trades are counted

A past signal counts when the panel would have called it CONFIRM that day (earnings excepted):
SPY uptrend, trend stacked, RS rising, not extended, plus a breakout on at least 1.3× volume or a
pullback reclaim. It is then traded exactly as the dashboard's ledger trades a pick:

- Entry at the next session's open, skipped when that open is above the buy-up-to limit or at or
  below the stop.
- Exit at the stop (at the open if it gaps through), or at the close of the 126th session.
- No profit targets. The +20% level is only marked.
- 0.2% round-trip costs.
- RSP is compared over each trade's own holding period.
- One trade at a time, so overlapping signals don't double-count the same move.

Values close to a threshold turn amber. Vendor data can differ slightly near a boundary.

## Inputs

| Group | Input | Default | What it does |
|---|---|---|---|
| Dashboard Hand-off | Pin to dashboard date | off | Off: scores the last closed session. On: scores the date below. |
| | Dashboard as_of (YYYY-MM-DD) | — | The session date from the dashboard |
| | Stop (ATR) | 4.5 | Stop distance for the stop line and for past trades (3–6) |
| | Max chase (ATR) | 0.5 | Buy-up-to line above the reference close (up to 1.5) |
| | Planned hold (sessions) | 84 | Position of the review tick (42–126). Past trades always run to 126 sessions or the stop, like the ledger |
| Sizing | Risk per trade (%) | 1.0 | Account % lost at the stop (0 = hide the size) |
| | Momentum size scale | 1.0 | Copy from the dashboard; 1.0 = full size |
| Display | EMAs, structure, levels, panel | on | Toggle each layer |
| | Borderline band (%) | 5 | How close to a threshold counts as amber |
| | Markers: last N bars | 120 | Older markers are hidden (0 = all) |
| Panel | Position / text size / compact | bottom right / small / on | Where and how big; compact shows the seven rows you act on |
| | Tall panel | on | One narrow column, each label above its value, so it covers less of the chart on a phone. Off = two columns |
| History | Show past trade windows | on | Draw the past trades (the panel row is always on) |
| | History window (bars) | 1260 | Only signals in the last N bars count (about five years; max 2000). At 126-session holds that is still only a handful of trades |

Use the dashboard pick's stop and chase values. Adjusting them until one chart's past
trades look good is fitting to that stock, and it says nothing about the next trade.

The signal definitions are fixed on purpose and have no inputs. To match a dashboard pick,
type in its as_of date and stop, and the lines will line up with its prices.

## Alerts

All alerts fire on the bar close:
- A squeeze breakout
- B pullback reclaim
- Close below the pinned stop
- Turned AVOID

## Compatibility

- TradingView, Pine Script v6, **daily timeframe only**. Other timeframes show a notice.
- US equities, benchmarked against SPY (trend gate, relative strength) and RSP (past trades).
- Leave dividend adjustment **off** to match the split-adjusted daily data the dashboard uses.
