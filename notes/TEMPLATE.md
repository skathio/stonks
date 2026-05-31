# <Indicator / Hypothesis Name>

**Date:** YYYY-MM-DD
**Script:** `indicators/<filename>.pine` (or N/A if pre-implementation)
**Status:** draft / live / shelved / killed

---

## 1. Edge Hypothesis

One paragraph. What inefficiency does this exploit? Behavioral, structural, liquidity, microstructure, vol-of-vol, term-structure? Why should it produce non-random returns?

If you cannot state the edge in one paragraph without naming an indicator, there is no edge yet — go back.

---

## 2. Target Regime

- **Works in:** (trending / mean-reverting / high-vol / squeeze / post-event drift / etc.)
- **Breaks in:** (chop / gap-heavy sessions / low ADX / earnings weeks / illiquid hours / etc.)
- **Instrument scope:** (equities / FX / crypto / futures — and why this isn't universal if it isn't)
- **Timeframe scope:** (1m / 1h / 1D — and why)

---

## 3. Signal Logic

### Entry
- Trigger condition(s):
- Required filters (regime, trend, volatility):
- Confirmation:

### Invalidation
- Hard stop condition (in ATR multiples or structural):
- Soft exit condition (time-based, signal-fade):

### Exit (target)
- Target logic (ATR multiple, structure, trailing):
- Partial-exit rules if any:

---

## 4. Repainting Audit

- [ ] All `request.security` calls use `lookahead=barmerge.lookahead_off`
- [ ] Pivots are offset by their confirmation length when plotted
- [ ] No future-referencing series (`close[-n]` style)
- [ ] Signals tested with `barstate.isconfirmed` or prior-bar values
- [ ] No `varip` in signal-critical state

Notes on anything that *could* repaint and how it's mitigated:

---

## 5. Backtest Observations

| Window | Symbol | TF | Trades | Win % | Avg R | Max DD | Notes |
|--------|--------|----|--------|-------|-------|--------|-------|
|        |        |    |        |       |       |        |       |

Commission: ___ %  |  Slippage: ___ ticks  |  Sizing: ___ % equity

What surprised you. What was expected and confirmed. What was expected and *not* confirmed.

---

## 6. Known Failure Conditions

Concrete situations where this has produced or will produce bad signals. Be specific — "doesn't work in chop" is not specific. "Generates 3+ false signals per week when ADX(14) < 18 on the 1H chart" is specific.

-
-
-

---

## 7. Open Questions / Next Tests

What you'd want to know to either ship this with confidence or shelve it.

-
-

---

## 8. Decision Log

| Date | Change | Reason |
|------|--------|--------|
|      |        |        |
