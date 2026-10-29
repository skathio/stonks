# Momentum Edge

A **daily US-equity swing-trading** toolkit for momentum continuation: breakouts from volatility
contractions and pullbacks to rising averages, aimed at multi-week moves. It has two parts:

1. **A daily scan dashboard.** A scheduled agent analyses the S&P 500 + 400 every morning and
   publishes candidates with ATR-based levels (see [Daily scan dashboard](#daily-scan-dashboard)).
2. **A TradingView indicator, Momentum Edge — Chart Check.** You open a flagged stock and the
   chart confirms or contradicts the call at a glance.

> **Disclaimer:** These are research tools, not financial advice. Nothing here places orders.

---

## Chart Check indicator

One daily overlay ([`indicators/momentum-edge-chart-check.pine`](indicators/momentum-edge-chart-check.pine), [docs](indicators/momentum-edge-chart-check.md)):

- **Setup markers:** **A** squeeze breakout, **b** breakout without a squeeze, **B** pullback
  reclaim. Solid when volume confirms; grey when the trend isn't stacked.
- **Structure:** EMA 9/21/50 and SMA200, the prior-20-bar high, the 52-week high, the 15-bar base
  box, and an extension tint above 4 ATR.
- **Levels:** stop, buy-up-to limit and R-multiple targets. Type in a dashboard pick's values and
  the lines match its prices.
- **Panel:** CONFIRM / CAUTION / AVOID for the scored session (its date is printed), with the
  SPY gate, trend, relative strength, setup, volume, extension and earnings rows.

Its definitions are fixed to match the dashboard's feature calculations exactly, so the chart and
the dashboard always agree on the facts.

### Setup

TradingView doesn't import files, so:

1. Open `indicators/momentum-edge-chart-check.pine` and copy its contents.
2. In TradingView open the **Pine Editor**, paste, and click **Add to chart**. Use a **daily** chart.

### Alerts

| Alert | Fires when |
|---|---|
| `A squeeze breakout (in context)` | A breakout on volume, with the SPY gate on, the trend stacked and not extended |
| `B pullback reclaim (in context)` | A pullback reclaim, with the SPY gate on, the trend stacked and not extended |
| `close below pinned stop` | The session closes below the dashboard stop you pinned |
| `turned AVOID` | Price drops below EMA50 or extends past 4 ATR |

All alerts fire on the bar close.

---

## Repo structure

```
indicators/
  momentum-edge-chart-check.pine  Chart Check — daily overlay (markers, structure, levels, panel)
  momentum-edge-chart-check.md    Usage, inputs, compatibility
notes/
  TEMPLATE.md                   Research-note template
pipeline/                       Daily agent data pipeline (stdlib Python)
site/                           Encrypted daily-scan dashboard (React + Tailwind, GitHub Pages)
tools/                          Dashboard build + payload encryption (Node)
tests/                          Python + Node tests
agent/ROUTINE.md                How the daily agent routine is wired
CLAUDE.md                       Development guidelines and coding standards
```

---

## Daily scan dashboard

A scheduled Claude agent analyses the S&P 500 + S&P 400 every morning (07:00 CET), after the US session's
data is final. It publishes long swing-trade candidates (regime read, setup, conviction, ATR-based
stop/targets, earnings timing) and a forward-tracked record of every past pick to GitHub Pages.

The published data is **encrypted** (AES-256-GCM, random 256-bit key) and decrypted in the browser. The key
is delivered once per device through an unlock link's `#fragment`, which never reaches the server. The free market-data feeds it uses only allow personal, non-public use, so the site is a
private dashboard that happens to be hosted on Pages. See [`agent/ROUTINE.md`](agent/ROUTINE.md).

---

## Development

This repo follows a strict **edge-first** development discipline documented in `CLAUDE.md`: the market regime, theoretical edge, failure conditions, and repainting risk must be stated before any code is written. All stops and thresholds are expressed in ATR multiples — no fixed pip or dollar values. Look-ahead bias and overfitting are treated as hard blockers.
