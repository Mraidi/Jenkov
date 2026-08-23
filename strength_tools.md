# Strength domain — tool contract

**v1.2** — Documentation fixes only, no behaviour change: `end_session` return
shape gained `warmup_sets` (already returned by the code since v1.0, missing
from this doc), and the training-day rule is now stated where session identity
is decided, not only under staleness.

**v1.1** — `amend_last` gained `n`. Additive, default preserves v1.0 behaviour.

Frozen. Signatures and return shapes do not change without a version bump and a
migration note. Everything about *when* to call these, how to phrase
confirmations, and what Mike knows about my training lives in the persona
fragment and the guideline document, not here.

Eight write verbs, two resolution helpers, one read.

Every tool returns `status` plus a `say` string. `say` is the compact phrase
Mike echoes back — the tool decides what the confirmation contains, so a write
can never be confirmed with something that did not happen.

---

## start_session

```
start_session(split_label=None, location=None, energy_1_10=None)
  -> {status, workout_id, say}
```

Opens a session. `started_at` = now, `status='open'`, `in_warmup=1`.

**Training day, not calendar date.** A session's identity is `workout_date`,
computed as: anything before **04:00 local** belongs to the previous day.
"Already open today" and "open from a previous day" below both mean *training
day*, not calendar date — a session started at 23:30 and continuing past
midnight is still the same training day, so it is still the same session.
Calendar date is the wrong unit here: it splits a late-night workout into two
sessions, which is the exact failure this rule exists to prevent.

- `split_label` free text ('pull', 'push', 'legs'). Never validated against an
  enum — I change my mind mid-session and the label is post-processable.
- If a session is already open **this training day**: returns
  `status='already_open'` with the existing `workout_id`. Does not create a
  second one.
- If a session is open from a **previous training day**: auto-closes it as
  `abandoned`, opens a new one, and says so.

**Staleness rule.** Any tool that touches the open session first checks it.
A session is stale if the last non-voided set is more than **6 hours** old, or
if the session crosses **04:00 local**. Stale sessions are closed as
`abandoned` and a new one is opened, with the change stated out loud.

Six hours is well past any real gap inside one workout — a long rest, a phone
call, lunch. 04:00 rather than midnight so a late-night session is not split in
half. Checked lazily on the next call rather than by a background job: there is
no user waiting at 4am, and a cron job is a second thing that can fail.

## end_warmup

```
end_warmup() -> {status, warmup_sets, duration_min, say}
```

Sets `in_warmup=0`. Everything logged before this is `is_warmup=1`; everything
after is `0`. Idempotent — calling it twice is not an error.

If never called, the whole session is warm-up, which is wrong but recoverable:
`amend_last` and a bulk fix can correct it later.

Warm-up state lives on `workouts.in_warmup`, not in the conversation, so a
dropped context mid-session does not silently reclassify the rest of the workout.

## start_superset / end_superset

```
start_superset(include_last=0) -> {status, group, backfilled, say}
end_superset()                 -> {status, group, sets, say}
```

`start_superset` assigns the next unused group number for this session and
stores it on `workouts.active_superset_group`. Every subsequent `log_set`
inherits it. `end_superset` nulls it.

**`include_last` handles the retroactive case, which is the common one.**
I do not decide a superset in advance — I log a set, then reach for something
else while resting. `include_last=n` pulls the last `n` non-voided sets in the
session into the new group, so the pairing is recorded correctly even though
the first half was logged before I knew.

Sets already belonging to another group are skipped rather than reassigned,
and the count actually backfilled comes back in `backfilled` so the
confirmation states what happened rather than what was asked for.

Session state again, for the same reason as `in_warmup`: pairing is not
recoverable from timestamps alone. Alternating curls and skull crushers with
no rest looks identical to sloppy pacing once the moment has passed.

Both are idempotent. `end_session` clears the group regardless.

## log_set

```
log_set(exercise=None, reps=None, load_lb=None, load_type=None,
        rpe=None, to_failure=None, continues_last=False, note=None)
  -> {status, set_id, exercise, set_number, say}
```

The only verb that writes a set. Called once per set.

**Session resolution.** Finds the open session itself. If none is open, opens
one implicitly and says so — a set is never lost because I forgot to say "start
workout".

**Exercise resolution.** Exact match on `canonical_name`, then on
`exercise_aliases`. Both lowercased and trimmed. No fuzzy matching.

- Resolved → writes.
- Not resolved → **writes nothing**. Returns `status='unresolved'` with up to
  three candidates from a substring match, for Mike to ask about.
- `exercise` omitted → inherits from the last non-voided set in this session,
  along with `load_lb` and `load_type` if those are also omitted. This is the
  short form: saying "eight more" logs another set of the same thing.
- No previous set and no exercise → `status='need_exercise'`.

**Load.**

- Exercise has `is_bodyweight_base=1` and no `load_lb` → `load_type='bodyweight'`,
  `load_value` null. Never blocks waiting for a weight.
- `is_bodyweight_base=1` with `load_lb` → `load_type='bodyweight'`,
  `load_value` = the added weight.
- `is_bodyweight_base=0` and no `load_lb` → inherits from the last set of the
  same exercise in this session. If there is none, `status='need_load'` and
  nothing is written.
- `load_lb` is **always pounds**. The tool does not convert. If I say kilos,
  that is a resolution problem for Mike to raise, not a silent multiply.
- `load_type='assisted'` → `load_value` is the assistance, stored positive.

**Reps.** Required. `reps=None` → `status='need_reps'`, nothing written.

**Drop sets and run-ups.** `continues_last=True` writes this set as a
continuation of the previous one: `parent_set_id` points at the last non-voided
set, and `exercise` is inherited from it and cannot be overridden.

Direction is not a parameter. Load going down (a drop set) and load going up
(ascending / run-up) are the same structure, and which one it was is already
readable by comparing `load_value` along the chain. Naming the argument
`continues_last` rather than `drop_from_last` keeps that honest — the column
never had a direction constraint and the argument name should not imply one.

Chains are unbounded. Each segment points at the segment before it, so a
ten-drop chain is the same shape as a two-drop one. `v_sets.is_drop_segment`
marks every row with a parent, so a set count is `COUNT(*) WHERE
is_drop_segment = 0` and volume is summed across every row.

Fails with `status='no_parent'` if there is no previous set in the session.

**Supersets.** If `workouts.active_superset_group` is set, every logged set
inherits it. Nothing is passed to `log_set` — see `start_superset` below.

**RPE.** Mike asks for it on every set. It is not required by the tool: a set
with `rpe=None` still writes. The asking is a prompt behaviour, not a contract
rule, so it can be relaxed later without a migration if it turns out to be too
much friction mid-workout.

Inside a superset Mike stays quiet and collects both afterwards via
`amend_last(..., n=)`. See `amend_last`.

**set_number.** Computed as max+1 for that exercise within that session —
**except for continuation segments, which inherit the parent's `set_number`.**

A chain is one set. Switching weight mid-set does not advance the count: if I
am on set 2 and drop the load, I am still on set 2. `set_number` therefore
counts efforts, not rows, which is what I actually experienced and what "three
sets of curls" means when I say it out loud.

Voided sets keep their numbers; gaps are allowed and expected. Renumbering
after a correction would make earlier confirmations retroactively false.

**performed_at.** Stamped by the tool at call time. Never accepted as an
argument — a timestamp I could pass is a timestamp the model can invent.

## end_session

```
end_session(enjoyment_1_10=None, energy_1_10=None, note=None)
  -> {status, duration_min, total_sets, warmup_sets, exercises, say}
```

Sets `ended_at`, `status='closed'`. Returns a session summary.

`total_sets` counts working sets only; `warmup_sets` is separate. A chain
counts once (`total_sets` is the working-set version of the `set_number`
rule above — segments are not counted individually). Kept apart deliberately:
"done, 6 sets" after five working sets and one warm-up is ambiguous in the one
place that has to be unambiguous.

The subjective fields are the reason this verb exists — they are the only
values in the whole domain that cannot be reconstructed later. If they come
back null, that is a real loss, not a cosmetic one.

## undo_last

```
undo_last(n=1) -> {status, voided, say}
```

Sets `voided=1` on the last `n` non-voided sets in the open session, most
recent first. Returns what was voided so Mike can state it plainly.

- Never hard-deletes.
- `n` capped at 5. Beyond that, use the correction path deliberately.
- No open session → `status='no_session'`.

## amend_last

```
amend_last(field, value, n=1) -> {status, before, after, set_number, say}
```

Updates one field on the `n`-th most recent non-voided set in the open session.
`n=1` is the last set, `n=2` the one before it. Default `n=1`.

`n` capped at 5, same as `undo_last`. Out of range → `status='no_such_set'`,
nothing written. The return includes `set_number` so the confirmation states
which set was actually changed rather than assuming.

**Why `n` exists.** Supersets log two sets back to back with no rest between
them, so RPE cannot be asked between them — there is no moment to answer in.
Mike logs the pair silently and asks once afterwards, which means writing RPE
to a set that is no longer the most recent. It generalises past supersets:
correcting a set two back otherwise has no path except manual SQL.

Allowed fields: `reps`, `load_lb`, `load_type`, `rpe`, `is_warmup`,
`to_failure`, `exercise`, `note`.

Not amendable: `performed_at`, `set_number`, `workout_id`. Changing those
rewrites history rather than correcting it.

Amending `exercise` runs the same resolution as `log_set` and fails the same
way if it does not resolve.

---

## Resolution helpers

Called only after I have answered Mike's question. Neither is ever called
speculatively.

```
add_exercise_alias(exercise_id, alias) -> {status, say}
```
Stores what I said so it never asks again. This is the common case.

```
create_exercise(canonical_name, movement_pattern=None, primary_muscle=None,
                equipment=None, is_bodyweight_base=0, alias=None)
  -> {status, exercise_id, say}
```
Only after I confirm it is genuinely new. Creates the row and, if `alias`
differs from `canonical_name`, the alias too.

---

## Overflow

```
log_unstructured(domain, raw_text) -> {status, say}
```

Anything Mike wanted to record with no column for it. Domain is `'strength'`
here. This is the pressure valve that stops improvisation into the wrong field.

---

## Read

```
run_query(sql) -> {rows, count} | {error}
```

Single `SELECT` against a read-only connection. Rejects multiple statements and
anything matching write keywords. Row cap 200.

Prefer the `v_sets` view — it filters voided rows and resolves exercise names.
Querying `performed_sets` directly will count corrections as real sets.

---

## Error logging

Every non-ok return is appended to `tool_log` with the arguments that produced
it, before the status goes back to Mike. Ok returns are not logged — volume
without signal.

This is the only feedback loop on whether the system works. Read it weekly.
Fifteen identical `unresolved` rows for the same spoken name is a missing
alias; one is noise.

Deliberately not an automated repair pipeline. At a handful of rows a week,
reviewing by hand costs less than building the pipeline, and it keeps schema
changes genuinely going through me rather than through a rubber stamp I stop
reading by the twentieth patch.

---

## Settled

- **RPE** — Mike asks every set. Prompt behaviour, not a contract rule.
- **Pausing** — no verb. Sets carry their own timestamps, so a long gap is
  already visible and derivable. A `paused` state can be entered and never
  exited, which is a new failure mode for no new information.
- **Never write a guess.** Ambiguous but recoverable → ask, one line.
  Unmodeled but recordable → `log_unstructured`. Genuinely stuck → say so and
  write nothing. A refusal costs one utterance; a wrong row costs every query
  that touches it, forever, and looks exactly like a correct one.

## Open in this contract

- **`log_set` implicit session open** contradicts nothing, but it means
  `started_at` is really "time of first set" whenever I forget the start verb.
  Acceptable, worth knowing.
- **Reps within a chain are per segment, not cumulative.** 8 at 60 then 5 at
  40 stores `reps=8` and `reps=5`, not 8 and 13. Total reps for the set is a
  sum along the chain. Mike's confirmation says the segment, since that is what
  just happened.
