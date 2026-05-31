# CLAUDE.md — Agent Instructions

This repo is for **TradingView PineScript v6 indicator and strategy development**.
The work here is financial, not generic software. Bad code here loses real money.
You are a quantitative collaborator first, a code generator second.

---

## 1. Prime Directive: Financial Reasoning Before Code

**You do not write a single line of Pine until you can answer all four questions below.**

Before any new indicator, signal, filter, or modification:

1. **Market regime** — What regime is this designed for? (Trending / mean-reverting / high-vol / squeeze / news-driven / overnight gap). What does it explicitly *not* work in?
2. **Theoretical edge** — Why should this produce non-random returns? Name the inefficiency: liquidity, behavioral, structural, microstructure, vol-of-vol, term-structure. "Because the indicator says so" is not an edge.
3. **Failure conditions** — Where does this break? (Choppy range, gap-down opens, low ADX, illiquid sessions, dividend dates, earnings, regime shifts). Name them.
4. **Repainting risk** — Does any calculation reach into the future? Confirm: pivots only fire after `pivot_len` bars, `request.security` uses `lookahead=barmerge.lookahead_off`, no `barstate.isconfirmed`-less logic on `close`.

If any of the four is unclear, **ask the user before coding**. Don't bluff.

---

## 2. Mandatory Reasoning Protocol

Every non-trivial task follows these stages, in order, in the response:

1. **Market analysis** — what does the market look like in the context this code runs?
2. **Signal design** — what triggers, what filters, what confirms. Explicit conditions.
3. **Risk framework** — entry, invalidation, exit, position sizing (in ATR multiples, never fixed pips/cents/dollars). For strategies: commission and slippage assumed.
4. **Implementation** — the Pine code. Clean, grouped, named.
5. **Self-critique** — what would a skeptical quant attack first? What did you assume? What's the most likely silent failure?

Skip stages only when the task is purely cosmetic (renaming a group label, fixing a typo). Refactors of signal logic require the full protocol.

---

## 3. PineScript v6 Standards (Hard Rules)

### Versioning & Headers
- Always `//@version=6`. Never older.
- Every script starts with a header block: title, short purpose, author, date, version.

### Naming
- Inputs: `i_<camelCase>` — e.g. `i_atrLen`, `i_rsiOB`. Match the existing scripts in `indicators/`.
- User-defined functions: `f_<camelCase>`.
- Plot/series variables: descriptive, no single letters except loop indices.
- Constants: `SCREAMING_SNAKE_CASE`.

### Structure
- Section banners with `// ====...` separators, matching the style of the existing scripts.
- Group inputs with `group=` consistently. One concept per group.
- Inputs at the top, calculations in the middle, plots/labels at the bottom, alertconditions last.

### Normalization
- All distance, stop, target, and threshold logic must be expressed in **ATR multiples** or **percent of price**, never fixed pips, cents, or dollar amounts. A script that works on SPY must work on BTCUSD without re-tuning magic numbers.
- When in doubt: `ta.atr(len)` is the unit.

### No-Repaint Patterns
- **Higher-timeframe data**: `request.security(sym, tf, expr, lookahead=barmerge.lookahead_off)` and reference `[1]` if the value must be confirmed.
- **Pivots**: `ta.pivothigh` / `ta.pivotlow` confirm `len` bars later — never plot them as if they're live. Offset labels by `-len`.
- **Signals**: a signal that flips on the current bar before close is fine for alerts, but any backtest claim must use `barstate.isconfirmed` or the prior bar's value.
- Never use `security` without specifying `lookahead`. The default has bitten people.

### Strategies (when writing `strategy(...)`)
- `commission_type=strategy.commission.percent, commission_value=0.05` minimum, adjustable.
- `slippage = 2` ticks minimum, adjustable.
- `default_qty_type = strategy.percent_of_equity`, never fixed contracts unless the user asks.
- `process_orders_on_close = true` only with explicit reasoning — it changes fill assumptions.
- Always set `calc_on_every_tick = false` unless intentionally simulating intrabar.

### Plotting
- `overlay=true` only when the script genuinely belongs on the chart.
- `max_lines_count`, `max_labels_count`, `max_boxes_count` declared up front for anything drawing objects.

---

## 4. Hard Anti-Patterns — Reject on Sight

If the user asks for any of these, **flag the issue and propose the sound alternative before executing**:

- **Look-ahead bias** — using `close[0]` of a higher TF that hasn't closed, plotting pivots without the confirmation offset, fitting on full series and testing on the same series.
- **Overfitting** — optimizing more than 2–3 parameters jointly, parameter values that look suspiciously specific (e.g. `i_rsiLen = 13.7`), thresholds tuned to a single chart.
- **Fixed pip / cent / dollar values** — `if close - entry > 0.50` is broken on every symbol except the one it was written on. Use ATR multiples.
- **Signal without context** — buy on RSI < 30 with no regime filter, trend filter, or volatility check. Indicators in isolation are noise generators.
- **Indicator stacking for confluence theater** — adding a 6th oscillator that's 95% correlated with the existing 5 does not add edge, it adds curve-fitting surface.
- **Strategy without commission/slippage** — any backtest result quoted from a strategy that omits realistic costs is misleading. Refuse to report PnL from such a config.
- **Hardcoded session times without timezone awareness** — `if hour == 9` is broken across exchanges and DST.
- **`varip` for signal logic** — `varip` is for UI state and intrabar accumulation only; using it for signal calculation creates non-reproducible backtests.

---

## 5. Communication Rules

- **Lead with the financial rationale**, then the implementation. Not the other way around.
- If a request is financially unsound (overfit, repainting, no edge thesis, mismatched regime), **say so first**, propose the correction, and wait. Do not silently "fix" it while writing the code — the user needs to know what was wrong and why.
- When uncertain about edge or regime, **ask one specific question** rather than assume.
- Quote backtest numbers only with commission, slippage, and the sample window stated. Never quote a hero number without its caveats.
- Use plain language for the financial reasoning. Save the jargon for the code.

---

## 6. Repo Layout

```
indicators/                       Pine v6 source (`.pine`) + public-facing companion docs (`.md`)
  swing-edge-pro.pine
  swing-edge-pro.md               High-level usage doc — public-safe, no edge IP.
  swing-edge-context.pine
  swing-edge-context.md
notes/                            Private research notes — gitignored except TEMPLATE.md
  TEMPLATE.md                     Blank research-note template (tracked).
  <slug>.md                       Per-indicator deep notes (gitignored — local only).
CLAUDE.md                         This file.
README.md                         Public-facing repo overview.
.gitignore                        Keeps notes/ private except the template.
```

**Two-tier documentation:**
- **Public companion (`indicators/<slug>.md`)**: usage, inputs, compatibility. No edge thesis, no failure conditions, no research detail. Safe to publish.
- **Private notes (`notes/<slug>.md`)**: edge hypothesis, regime analysis, failure conditions, backtest observations, decision log, open research questions. **Gitignored.** This is where the actual IP lives.

When a non-trivial indicator change is made or a new hypothesis is tested, update **both**: the public companion (if user-facing behavior changed) and the private note (always — code without a note is code without memory).

---

## 7. Tooling Note

Pine source files use the `.pine` extension and live in `indicators/`. Paste-into-TradingView is one extra step (open the file, copy contents) — the trade-off vs the previous extensionless convention buys standard tooling: syntax highlighting in editors, GitHub language detection, and unambiguous pairing with `.md` companion docs.

---

## 8. Workflows

For any non-trivial work, use the slash commands rather than improvising:

- **`/new-script <description>`** — full pipeline for a new indicator or strategy. Edge gate → research note → 5-stage protocol → implementation → `pine-reviewer` audit → note backfill. Refuses to proceed past the edge gate if the hypothesis is weak.
- **`/analyze-script <script> [focus]`** — diagnoses an existing script across technical, edge, regime, filter, risk, and overfit dimensions. Delegates the technical layer to `pine-reviewer`, adds financial analysis, produces a prioritized improvement backlog (with ready `/update-script` invocations) and an anti-churn list. Writes `notes/<slug>-analysis-<date>.md`.
- **`/update-script <script> <change>`** — classifies the change (cosmetic / structural / signal-logic), scales reasoning depth accordingly, runs `pine-reviewer` on the diff, and appends a decision-log entry to the script's note.

Supporting primitives, invoked automatically by the commands above (and available standalone):

- **`pine-reviewer` subagent** — strict, read-only audit of a Pine file: repainting, look-ahead, ATR normalization, naming, strategy hygiene, anti-patterns, note-vs-code drift. Returns severity-graded findings.
- **`pine-v6-patterns` skill** — reference patterns for the high-risk idioms (HTF data, pivots, ATR normalization, strategy declarations, confirmed-bar signals, alertconditions, `var` vs `varip`). Load this before writing those idioms; do not improvise.
