---
description: Diagnose an existing Pine script across technical, edge, regime, filter, risk, and overfit dimensions. Produces a prioritized improvement backlog written to notes/<slug>-analysis-<date>.md, each item carrying a ready /update-script invocation.
argument-hint: <script-name-or-keyword> [optional focus area]
---

You are diagnosing an existing Pine v6 script. The output's value is in **prioritization** and **honesty about what doesn't matter** — not in length. A 5-item backlog of high-leverage changes beats a 20-item list of churn.

The user's request:
$ARGUMENTS

# Step 0 — Locate target

Identify the target file in `indicators/`. Read it in full. Read any associated note in `notes/`. If no script matches, ask. If a focus area is specified (e.g. "just the entry logic", "only filters"), scope steps 2a–2e to that area but still run the technical audit in full.

# Step 1 — Technical audit (delegate to clean context)

Invoke the `pine-reviewer` subagent on the target file. Capture its findings verbatim — they merge into the synthesized backlog at Step 4. Do not re-derive technical findings in the main context; the subagent owns that layer.

# Step 2 — Financial analysis (main context)

Apply the `CLAUDE.md` §1 framework to the script **as implemented** (read from the code), not as claimed in any note. The point is to find drift.

## 2a. Edge re-derivation
From the code alone, what inefficiency is this script betting on? Name it explicitly (behavioral, structural, liquidity, microstructure, vol-of-vol, term-structure). Then compare to the edge claimed in the note (if one exists). Drift between claim and implementation is itself a finding.

## 2b. Regime assumptions
What market regime does the code implicitly assume? Inspect:
- Filter thresholds (RSI/ADX/ATR levels reveal the assumed dynamics).
- Lookback windows (short = trending bias; long = mean-reverting bias).
- `and`-chained conditions (each conjunction narrows the regime window — count them).
- Direction asymmetry (does the script treat longs and shorts symmetrically when the underlying instrument is asymmetric, e.g. equities)?

Name the regime. Then name where this **silently misfires** — concrete situations, not "in chop".

## 2c. Filter independence
For multi-filter signals, assess orthogonality:
- Are multiple oscillators measuring the same thing (RSI + Stoch RSI = both bounded momentum)?
- Does an "added confirmation" actually filter losing trades, or just delay a working signal?
- Confluence theater test: if you removed filter N, would the signal change for >20% of fires? If no, the filter isn't doing work.

## 2d. Risk framework integrity
- Stops/targets in ATR multiples or fixed units?
- Does position sizing scale with volatility?
- For strategies: commission + slippage realistic for the intended venue?
- Circuit breakers (daily loss cap, max consecutive losses, regime-detection halt)?
- Asymmetry between win-size and loss-size — is it intentional, or accidental?

## 2e. Overfit surface
Count free parameters that affect signal generation (input.* values used in entry/exit/filter logic). More than ~5 jointly-tunable parameters is a yellow flag; >8 is red. Also flag:
- Suspiciously specific values (`i_rsiOB = 73`, `i_adxMin = 17`) — round numbers smell better.
- Parameters set "to match the chart" — i.e., they only make sense on the symbol the script was developed on.
- Tunables that interact (changing one forces re-tuning of another).

## 2f. Companion-doc fidelity
Diff the public companion `indicators/<slug>.md` against the code: input list and defaults, signal/verdict logic, alert behavior, compatibility claims. Public-doc drift is a finding — it misleads users even when the code is right.

# Step 3 — Comparative context

If peer scripts exist in `indicators/`, briefly note:
- Does this script duplicate logic the companion already provides?
- Is there an opportunity to consolidate, or a clean separation worth preserving?

Keep this short — two or three bullets.

# Step 4 — Synthesize the prioritized backlog

Merge Step 1 (technical) and Step 2 (financial) into **one ranked list**. Do not produce two parallel lists.

**Ranking criteria, in order:**
1. **Impact** — how much does fixing this change outcomes? Repainting / look-ahead > broken risk framework > overfit surface > naming.
2. **Tractability** — cheap fixes ranked first within the same impact tier.
3. **Reversibility** — prefer changes that can be A/B-tested against the current version.

For each item:
- **Severity**: Blocker | Major | Minor | Nit
- **Layer**: Technical | Edge | Regime | Filter | Risk | Overfit
- **Evidence**: `indicators/<file>.pine:<line>` or section name
- **Why it matters**: one line, financially framed (not "the code does X" but "this misfires when Y")
- **Suggested action**: a ready, copy-pasteable `/update-script <slug> <specific change>` invocation

# Step 5 — Anti-churn section (MANDATORY)

List 2–4 changes that **look** like improvements but you recommend **not making**:
- "Optimizations" that would increase overfit surface.
- Filters that add correlated noise rather than orthogonal signal.
- Cosmetic refactors with zero behavioral impact.
- Parameter tweaks the user might be tempted by but that don't earn their complexity.

For each: one-line rationale for why it's not worth it.

The most common analysis failure mode is a long list where 70% is noise. This section forces honesty about that.

# Step 6 — Write the artifact

Write `notes/<script-slug>-analysis-YYYY-MM-DD.md` containing the output of Steps 2–5 in full. If an analysis for the same script + date already exists, append a new section with a timestamp suffix rather than overwriting.

The chat output should be a tight summary: verdict, top 3 items, link to the file. The file is the system of record.

---

Use TodoWrite for the six steps. The analysis is not done until Step 6 has produced the artifact.
