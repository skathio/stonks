---
description: Update an existing Pine script with reasoning depth scaled to the change (cosmetic / structural / signal-logic).
argument-hint: <script-name-or-keyword> <what you want to change>
---

You are modifying an existing Pine v6 script. Follow `CLAUDE.md` strictly.

The user's request:
$ARGUMENTS

# Step 0 — Locate the target

Identify the target file in `indicators/`. If the request is ambiguous about which script, ask. If no script matches, suggest `/new-script` instead.

Read the file in full. Read any associated note in `notes/`. You need to understand the existing edge claim before you can responsibly change anything.

# Step 1 — Classify the change

State the classification before doing anything else:

- **Cosmetic** — rename, format, comment fix, group label change, plot color. Signal logic and parameters untouched.
- **Structural** — input default change, new visualization, new dashboard cell, refactor of unchanged logic. Signal semantics untouched.
- **Signal-logic** — anything that affects when/why/where a signal fires, what filters apply, how risk/stops/targets are computed, exit logic, position sizing.

If you're unsure between Structural and Signal-logic, treat it as Signal-logic.

# Step 2 — Reasoning depth (gated by classification)

**Cosmetic:** implement directly. Skip steps 3 and 4. Still run the review (Step 5).

**Structural:** state one paragraph of rationale + confirm regime impact is zero. Run abbreviated protocol (signal design unchanged, just describe the structural delta). Then implement.

**Signal-logic:** **full `CLAUDE.md` §2 protocol is mandatory**, plus:
- Re-answer the four prime-directive questions for the *modified* script. The edge may have shifted.
- Apply the HARD GATE — if the change weakens or muddles the edge, push back. "Add another filter for better signals" is confluence-theater bait; reject and ask what regime the new filter actually addresses.
- Explicitly list: **what existing behavior is preserved** vs **what changes**.

# Step 3 — Invariant inventory (Structural and Signal-logic only)

Before editing, list the invariants the existing script relied on that must not silently break:

- Naming conventions (`i_<camelCase>`, `f_<camelCase>`).
- ATR-based normalization for every distance/threshold.
- No-repaint guarantees (`request.security` lookahead, pivot offsets, `barstate.isconfirmed` gates).
- Strategy hygiene (commission, slippage) if strategy.
- Any explicit guarantees claimed in the note's repainting audit.

Anything you intend to change about these, state explicitly with reason.

# Step 4 — Implement

Before writing Pine for any high-risk idiom (HTF data, pivots, ATR normalization, strategy hygiene, alertconditions), invoke the `pine-v6-patterns` skill. Copy patterns; don't improvise.

Edit the target file **in place**. Do not rename.

# Step 5 — Review

Invoke the `pine-reviewer` subagent. For signal-logic changes, point it at both the change *and* the note — note/code drift is a real finding.

Address every **Blocker** and **Major** before claiming done.

# Step 6 — Decision log

Append an entry to the script's note in `notes/` (creating one from `notes/TEMPLATE.md` if it doesn't exist yet):
- Date.
- Change summary.
- Reason (why this change, what evidence drove it).
- If signal-logic: explicit before → after for the affected logic.

A change without a decision-log entry is a change that will be forgotten and re-litigated.

If the change is user-visible (inputs, defaults, signal/verdict behavior, alerts, dashboard), also update the public companion `indicators/<slug>.md` in the same pass (CLAUDE.md §6 two-tier rule). A companion that contradicts the code is a public-facing bug.

---

Use TodoWrite to track the steps that apply for the classified change. Do not collapse the classification step.
