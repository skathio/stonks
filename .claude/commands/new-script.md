---
description: Start a new Pine v6 indicator or strategy via the full reasoning protocol (edge gate → note → 5-stage protocol → review).
argument-hint: [one-line description of what you want to build]
---

You are starting a new Pine v6 script. Follow `CLAUDE.md` strictly. The protocol below is non-optional.

The user's request:
$ARGUMENTS

# Step 0 — Intake

If the request above is empty or doesn't pin down all three of (a) indicator vs strategy, (b) intended edge, (c) primary instrument and timeframe — ask **one** focused question covering whatever's missing. Do not proceed without all three.

# Step 1 — Edge gate (HARD GATE — no code until passed)

Out loud, answer the four prime-directive questions from `CLAUDE.md` §1:

1. **Market regime** — where this works / where it explicitly does not.
2. **Theoretical edge** — what inefficiency, named (behavioral / structural / liquidity / microstructure / vol-of-vol / term-structure). "The indicator says so" is not an edge.
3. **Failure conditions** — concrete situations where this will misfire.
4. **Repainting risk** — where in the planned logic could the future leak in.

**Gate rules:**
- If you can't answer any of the four → push back with one specific question, stop, wait.
- If the edge is vague, indicator-tautological, or smells overfit → say so explicitly, propose a stronger framing, stop, wait.
- Do **not** silently proceed past this gate.

# Step 2 — Write the research note FIRST

Before writing any Pine, create `notes/<slug>.md` from `notes/TEMPLATE.md`. Fill out:
- Edge hypothesis (the answer to §1 question 2, in one paragraph).
- Target regime.
- Signal logic (entry / invalidation / exit) — what you intend to build.
- Repainting audit checklist (what you will guard against).
- Known failure conditions.

The note is the spec. The code follows the note. If you can't write the note coherently, you can't write the code.

# Step 3 — 5-stage reasoning protocol (`CLAUDE.md` §2)

Run all five stages in the response, explicitly:

1. Market analysis.
2. Signal design (triggers, filters, confirmations).
3. Risk framework — ATR multiples, no fixed pip values. For strategies: commission + slippage.
4. Implementation (the code — next step).
5. Self-critique — what would a skeptical quant attack first? What did you assume? What's the most likely silent failure?

# Step 4 — Implement

Before writing Pine, invoke the `pine-v6-patterns` skill if any of these apply to your design: HTF data, pivots, ATR normalization, strategy declaration, alertconditions, confirmed-bar signals. Copy the patterns; don't improvise on the high-risk idioms.

Create `indicators/<slug>.pine`. Match the header / banner / group / alignment style of the current scripts in `indicators/`. After implementation, also create a slim public-facing `indicators/<slug>.md` (usage + inputs + compatibility, **no edge IP**). The deep research note in `notes/` (per Step 2) stays private.

# Step 5 — Review

Invoke the `pine-reviewer` subagent on the new file. Address every **Blocker** and **Major** finding before claiming the work is done. Minor and Nit findings — fix or explicitly defer with reasoning.

# Step 6 — Backfill the note

Update `notes/<slug>.md` to reflect what was actually shipped:
- Final signal logic (any deltas from intent).
- Repaint mitigations actually applied.
- First entry in the Decision Log: date, "initial implementation", and the link between edge → code.

The note must match the code. Drift is a future bug.

---

Use TodoWrite to track these six steps. Do not skip steps. Do not collapse the edge gate.
