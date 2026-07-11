---
description: Retire an indicator or strategy — close and archive its notes, delete the script + companion, and purge every repo reference.
argument-hint: <script-name-or-keyword> [reason]
---

You are retiring a Pine script. Retirement without cleanup leaves the repo lying about itself — stale style anchors, "live" notes for dead code, layout docs listing deleted files. Do all steps; the grep step is the point.

The user's request:
$ARGUMENTS

# Step 0 — Confirm the target

Identify the script in `indicators/`. State what will be deleted (`indicators/<slug>.pine` + companion `indicators/<slug>.md`) and what will be archived (its notes). If the reason for retirement isn't stated or obvious, ask one question. Deletion is destructive — get explicit confirmation before Step 2 unless the user already gave it.

# Step 1 — Close the note (memory first)

In `notes/<slug>.md`:
- Set `Status:` to `killed (<date> — <one-line reason>)` or `shelved (...)`.
- Append a final Decision Log entry: date, "retired", the reason, and what (if anything) replaces it.
- If a successor exists, link the successor's note. The failure record is the successor's justification — **never delete it**; killed systems need memory most, to prevent re-litigating the same design later.

Then move the script's notes (including any old `<slug>-analysis-*.md`) to `notes/archive/`.

# Step 2 — Delete the artifacts

Delete `indicators/<slug>.pine` and `indicators/<slug>.md`.

# Step 3 — Purge references (the step everyone skips)

Grep the whole repo for the slug, excluding `notes/archive/` and `.git`. Fix every hit:
- `CLAUDE.md` repo-layout tree.
- `README.md`.
- `.claude/` agents / commands / skills — style anchors and examples must point at current scripts. Prefer generic phrasing ("the current scripts in `indicators/`") so the reference cannot go stale again.
- Other scripts' notes that cite the retired one: keep the citation but mark it retired.

# Step 4 — Verify

Re-run the grep. The only remaining hits must be inside `notes/archive/` and historical citations in successor notes. Report the list of files changed.
