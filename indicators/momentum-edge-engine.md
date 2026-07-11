# Momentum Edge — Swing Engine

A long-only **momentum-continuation** signal engine for daily US-equity swing trades. It marks entries, draws the adaptive stop / target levels, and keeps a live on-chart trade journal (win rate, profit factor, expectancy, total return, max drawdown).

This is **Indicator 1 of 2**. Run it alongside **Momentum Edge — Regime & Quality** for environment confirmation.

> Indicator only — not financial advice. It simulates a single-unit position for journaling; it does not place orders. The journal applies commission **and** slippage (both adjustable, per side) but assumes clean fills at the bar close and a survivorship-filtered universe — so treat its numbers as an optimistic ceiling, not a promise.

## What it does

- Detects two continuation setups in an established uptrend:
  - **Mode A — Breakout:** price breaks above the prior N-bar high after a volatility squeeze.
  - **Mode B — Pullback:** price pulls back to a rising mid-EMA and reclaims with a strong bar.
- Requires the benchmark itself to be in an uptrend (risk-on) — the same market test as the Regime & Quality panel's first axis; toggleable, on by default.
- Requires relative-strength leadership vs a benchmark and a volume surge; blocks chases that are too extended.
- Adapts the trailing-stop width to the current volatility regime via a 3-cluster k-means on ATR.
- Banks an optional partial at TP1 and rides the remainder on the adaptive trail; exits on trail breach, trend break, or (optional) time stop.

## Inputs

| Group | Key inputs | Notes |
|---|---|---|
| Trend | EMA Fast / Mid / Base (9 / 21 / 50) | Defines the uptrend filter. |
| Volatility Regime (k-means) | ATR Length, Training Window, Iterations | Powers the adaptive trail + regime label. |
| Breakout (Mode A) | Breakout Lookback, Squeeze BB/KC, Squeeze Recency | Enable/disable Mode A. |
| Pullback (Mode B) | Pullback Lookback, Touch Tol (ATR), Reclaim Body | Enable/disable Mode B. |
| Relative Strength | Benchmark, RS smoothing/lookback, Require RS gate | Default benchmark SPY. |
| Market Regime | Require Benchmark Uptrend, Benchmark Trend EMA (50) | Blocks entries while the benchmark closes below its trend EMA. |
| Volume | Volume MA, Surge multiplier | Participation filter. |
| Filters | Max Extension from Mid (ATR) | Anti-chase cap. |
| Risk / Exit | Initial Stop, Trail, TP1 distance/%, Time Stop | All distances in ATR multiples. |
| Signal | Cooldown | Re-entry throttle. |
| Journal Costs | Commission %, Slippage % | Applied per side to every journal fill; entry-side costs are reflected in the open-P&L mark. |
| Display | Show Dashboard, Show Lines | UI toggles. |

All stops, targets, and thresholds are expressed in **ATR multiples** — defaults are intended to transfer across symbols without per-symbol tuning.

> The Engine's hard extension cap (4 ATR) is deliberately looser than the Regime & Quality panel's AVOID line (3 ATR). Signals in the 3–4 ATR band are environment-vetoed by the panel — by design, the panel is the stricter initiation standard.

## Compatibility

- **Timeframe:** Daily (the k-means window and ATR calibration assume daily bars).
- **Instruments:** Liquid US single-name equities. The benchmark RS filter assumes a US-equity benchmark (SPY); change it for other universes.
- **Pine:** v6. Uses `overlay=true`.

## Alerts

`LONG ENTRY`, `TP1 HIT`, `EXIT` — all fire on confirmed bar close.

## Reading the dashboard

Top block = current state (position, open P&L, market regime, trend, RS, volatility regime, squeeze, extension). Lower block = the trade journal accumulated over the loaded history.
