# Momentum Edge — Regime & Quality

An environment-confirmation panel for daily US-equity swing trades. It scores the trading **context** across several orthogonal axes and returns a single **CONFIRM / CAUTION / AVOID** verdict. It does **not** generate entries.

This is **Indicator 2 of 2**. Run it under **Momentum Edge — Swing Engine** (which provides the entry triggers). The Engine says *when*; this panel says *whether the environment supports acting*.

> Indicator only — not financial advice.

## The axes

| Axis | Measures | Orthogonal because |
|---|---|---|
| Market / breadth | Benchmark above its rising trend EMA (risk-on/off) | About the market, not the stock |
| Relative strength | Stock leading the benchmark (and optionally its sector) | Relative, not absolute |
| Volatility regime | 3-cluster k-means on ATR (Low/Mid/High) + squeeze | Second moment, not first |
| Base / extension | Distance from anchor EMA in ATR units | Position within the move |
| Volume / accumulation | OBV trend | Participation, not price geometry |
| Forward-odds *(optional)* | Offline-trained probability of a large up-move | Statistical odds, off by default |

The pane plots a 0–100 **Quality Score** (composite of the on-chart axes), colored by verdict; the **Forward-Odds %** line is overlaid when axis 6 is enabled.

## Verdict logic

- **AVOID** — market risk-off, OR relative strength lagging, OR over-extended.
- **CONFIRM** — risk-on **and** leading **and** in a fresh base **and** accumulating **and** a supportive volatility regime (**and** the forward-odds model passes, if enabled).
- **CAUTION** — anything mixed; use discretion.

## Inputs

| Group | Key inputs |
|---|---|
| Benchmark / Market | Benchmark symbol, Market Trend EMA |
| Relative Strength | RS smoothing/lookback, optional Sector Proxy |
| Volatility Regime (k-means) | ATR length, training window, iterations, squeeze BB/KC |
| Base / Extension | Anchor EMA, Max Extension (ATR) |
| Volume | OBV EMA length |
| Forward-Odds Model (axis 6) | Enable toggle, Min probability for CONFIRM |
| Display | Show Verdict Panel |

## Axis 6 — Forward-Odds Model

**Enabled by default.** The model was trained using a walk-forward validated logistic classifier (AUC 0.629, 5 forward folds with a 60-bar embargo) labelled on whether price reached +25% before −10% within 60 days. Its weights are frozen inside the indicator; features are reproduced bar-for-bar in Pine using trailing-only data (no look-ahead).

The displayed value is a **relative odds-score (0–100), not a calibrated probability** — a score ≥ 50 corresponds to roughly 1.7× the base-rate hit on +25% moves. It can only *withhold* a CONFIRM, never force an AVOID, and is gated by the market-regime axis. Toggle it off to compare against the 5-axis verdict.

## Compatibility

- **Timeframe:** Daily. **Instruments:** liquid US single-name equities (benchmark RS assumes a US-equity benchmark). **Pine:** v6, separate pane (`overlay=false`).

## Alerts

`Regime CONFIRM`, `Regime AVOID` — fire on the confirmed bar where the verdict first changes.
