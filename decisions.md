# Jenkov — decisions log

One line per settled question. Anything here is closed unless I reopen it.
Format: decision — reasoning — date.

## Architecture

- **Schema and tools first, LLM on top** — the model is an interface, never the store. — 2026-08-22
- **One agent to start** — personas are system-prompt fragments plus tool subsets, not separate services. Split only when one prompt stops being coherent. — 2026-08-22
- **Cross-domain analysis via SQL joins, not agent-to-agent messaging** — agents partition tools and context, not data. Every domain keys on date or timestamp. — 2026-08-22
- **Tools frozen, knowledge fluid** — an agent may propose edits to its guideline document; never to schema or function signatures. Modelled on how Siwar's glossary and style guide evolve while the publishing API stays fixed. — 2026-08-22
- **Read path is one open-ended read-only SQL tool** — not one function per question. Promote specific reads to real functions only when SQL demonstrably fails at them. — 2026-08-22
- **Explicit overflow tool (`log_unstructured`)** — gaps land in one visible place instead of being improvised into the wrong column. — 2026-08-22
- **One writer per fact** — if two tables could hold the same event, one owns it and the other derives. — 2026-08-22
- **Schema files named per domain, not per agent** — `strength_schema.sql`, not `mike_schema.sql`. Agents get renamed and merged; domains don't. — 2026-08-22
- **Rented client before native app** — Telegram or similar gives voice notes, push, history and sync for free. Backend is identical either way. — 2026-08-22
- **Phase 1 is pure recording** — descriptive only, no goal-setting or inference. Sequencing decision, not permanent. — 2026-08-22

## Strength domain

- **`load_value` + `load_type` replaces a single weight column** — bodyweight, assisted and banded work are not expressible as one number. — 2026-08-22
- **Store pounds only** — lb is what I speak and what my equipment is marked in, so storing it avoids a conversion step that can silently drift. One canonical unit matters; which one does not. Superseded the earlier kg decision. — 2026-08-22
- **Timestamp per set, not per session** — unreconstructable if missed. Gives rest intervals, intra-session fatigue and time-of-day for free. — 2026-08-22
- **Exercise aliases table** — voice produces many names for one movement. Without resolution, early data won't aggregate. — 2026-08-22
- **Warm-ups are sets with `is_warmup`, not a parallel structure** — one model instead of two, still separately queryable. — 2026-08-22
- **Derived fields not stored** — no `workout_duration`, no `number_of_sets`. They can disagree with reality after a correction. — 2026-08-22
- **Plans and performances are separate tables** — `workouts.plan_id` nullable so off-program sessions are still valid. Makes adherence measurable. — 2026-08-22
- **Set continuations are child rows via `parent_set_id`** — each segment points at the one before. Covers drops and run-ups equally; direction is readable from `load_value` along the chain, so it is not a column. Chains unbounded. — 2026-08-22
- **A continuation chain is one set** — segments inherit the parent's `set_number`. Changing load mid-set does not advance the count. `set_number` counts efforts, not rows, which is what "three sets" means when I say it. — 2026-08-22
- **Supersets via `superset_group`, declarable retroactively** — pairing is not recoverable from timestamps, and I decide mid-rest rather than in advance. `start_superset(include_last=n)` backfills. — 2026-08-22
- **Transient session state lives on `workouts`, not in the conversation** — `in_warmup`, `active_superset_group`. A dropped context mid-workout would otherwise silently reclassify everything after it. — 2026-08-22
- **`amend_last` takes `n`, reaching back up to 5 sets** — contract v1.1. Supersets log two sets with no gap, so RPE is collected after the pair, which means writing to a set that is no longer the most recent. Generalises: correcting two sets back otherwise needs manual SQL. — 2026-08-22
- **RPE asked on every set** — prompt behaviour, not a contract rule, so it can be relaxed without a migration if the friction proves too high. — 2026-08-22
- **No pause verb** — sets carry their own timestamps so long gaps are already derivable. A `paused` state can be entered and never exited: new failure mode, no new information. — 2026-08-22
- **Personality in the wrapper, never in the numbers** — every confirmation is built from the tool's `say` string, not phrased freely by the agent. A confident, terse persona is more convincing when it is wrong, so the persona owns tone and the tool owns facts. — 2026-08-22
- **Never write a guess** — ask, overflow, or refuse. A refusal costs one utterance; a wrong row costs every query that touches it and looks exactly like a correct one. — 2026-08-22
- **`tool_log` for every non-ok tool return** — the only feedback loop on whether the system works. Reviewed by hand weekly, deliberately not an automated repair pipeline: at this volume the pipeline costs more than it saves and turns approval into a rubber stamp. — 2026-08-22
- **Soft delete via `voided`** — corrections are frequent and first-class; hard deletes lose the fact that a correction happened. — 2026-08-22

- **Session auto-close at 6 hours idle or 04:00 local** — checked lazily on the next tool call, not by a cron job. Long enough to survive a real break, short enough that yesterday's session never takes today's sets. — 2026-08-22

## Deferred deliberately

- **Whether workouts also populate a general `activities` table** — cheap to backfill with `INSERT ... SELECT` once Jenkov's own schema exists. Only genuinely lost field would be in-the-moment subjective scores, which is why `enjoyment_1_10` is on `workouts` now. — 2026-08-22
- **Whether Jenkov's `to_dos` and `plan_day` are exempt from the descriptive-only rule** — forward-looking by nature. Revisit at phase 2. — 2026-08-22
- **Bulk warm-up fix** — if `end_warmup` never fires the whole session flags as warm-up and `amend_last` reaches only one set. Accepted as a manual SQL cleanup for now; `tool_log` will show whether it actually happens. — 2026-08-22
- **SQLite vs Postgres** — SQLite is correct for a single user. Migration is mechanical if it ever matters. — 2026-08-22
- **MCP vs direct function calling** — transport decision, identical contract. MCP only earns its place with a second client. — 2026-08-22
