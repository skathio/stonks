# Momentum Edge

A paired two-indicator system for **daily US-equity swing trades** built in TradingView PineScript v6. The system hunts momentum-continuation setups — breakouts from volatility contractions and pullbacks to rising MAs — targeting multi-week moves of 20–30%.

> **Disclaimer:** These are indicators, not financial advice. They do not place orders. Past simulated performance is not indicative of future results.

---

## How it works

The system is split across two indicators that run side by side:

| | Indicator | Role |
|---|---|---|
| 1 | **Momentum Edge — Swing Engine** | Entry signals, adaptive stop/target levels, on-chart trade journal |
| 2 | **Momentum Edge — Regime & Quality** | Environment confirmation — CONFIRM / CAUTION / AVOID verdict |

The **Engine** answers *when to enter*. The **Regime & Quality** panel answers *whether the environment supports acting*. You use both together.

### Swing Engine (Indicator 1)

Two continuation setups, both requiring an established uptrend + RS leadership + volume participation:

- **Mode A — Breakout:** price clears the prior N-bar high after a volatility squeeze (BB inside KC).
- **Mode B — Pullback:** price pulls back to a rising mid-EMA and reclaims with a strong body.

A 3-cluster **k-means on ATR%** ("adaptive SuperTrend") labels the current volatility regime and adjusts the trailing-stop width accordingly. An optional TP1 partial de-risks the trade; the remainder rides the adaptive trail. The on-chart dashboard shows the live position state and a cumulative trade journal (win %, profit factor, expectancy, total return, max drawdown) with commission and slippage applied.

### Regime & Quality Panel (Indicator 2)

Six orthogonal axes feed a single CONFIRM / CAUTION / AVOID verdict:

| Axis | What it measures |
|---|---|
| Market / breadth | Benchmark above its rising trend EMA |
| Relative strength | Stock leading the benchmark (+ optional sector proxy) |
| Volatility regime | k-means ATR% cluster + squeeze state |
| Base / extension | Distance from anchor EMA in ATR units |
| Volume / accumulation | OBV trend |
| Forward-odds model | Walk-forward validated logistic model (AUC 0.629, enabled by default) |

The forward-odds axis produces a **relative rank (0–100)**, not a calibrated probability. It can only withhold a CONFIRM — it never forces an AVOID. Toggle it off via the `Enable Axis 6` input to use the five on-chart axes alone.

---

## Setup

Both files use the `.pine` extension and live in `indicators/`. TradingView does not support direct file import, so:

1. Open `indicators/momentum-edge-engine.pine` in your editor.
2. Copy the full contents.
3. In TradingView, open the **Pine Editor**, paste, and click **Add to chart**.
4. Repeat for `indicators/momentum-edge-regime.pine` — add it as a **separate pane** below the price chart.

That's it. Defaults are calibrated for daily US equities; no per-symbol tuning is needed or recommended.

---

## Compatibility

- **Timeframe:** Daily. The k-means training window and ATR calibration assume daily bars.
- **Instruments:** Liquid US single-name equities. The default benchmark is SPY; change `Benchmark Symbol` for other universes.
- **Pine version:** v6.
- **TradingView plan:** Any plan that allows two active indicators.

---

## Alerts

| Indicator | Alert | Fires when |
|---|---|---|
| Engine | `LONG ENTRY` | Entry signal confirmed at bar close |
| Engine | `TP1 HIT` | First target reached |
| Engine | `EXIT` | Trail stop or trend break exit |
| Regime | `Regime CONFIRM` | Verdict first transitions to CONFIRM |
| Regime | `Regime AVOID` | Verdict first transitions to AVOID |

All alerts fire on confirmed bar close — no intrabar triggers.

---

## Repo structure

```
indicators/
  momentum-edge-engine.pine     Signal engine — overlay on price chart
  momentum-edge-engine.md       Usage, inputs, compatibility
  momentum-edge-regime.pine     Regime & quality panel — separate pane
  momentum-edge-regime.md       Usage, inputs, compatibility
notes/
  TEMPLATE.md                   Research-note template
CLAUDE.md                       Development guidelines and coding standards
```

---

## Development

This repo follows a strict **edge-first** development discipline documented in `CLAUDE.md`: the market regime, theoretical edge, failure conditions, and repainting risk must be stated before any code is written. All stops and thresholds are expressed in ATR multiples — no fixed pip or dollar values. Look-ahead bias and overfitting are treated as hard blockers.
