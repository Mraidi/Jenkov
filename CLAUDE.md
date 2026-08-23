# Jenkov

Personal life-tracking system. Voice-first recording into a shared SQLite store,
with purpose-specific agent personas reading and writing through a frozen tool
layer. Jenkov is the orchestrator; Mike is the strength-training persona.

Sole user and owner: Selim. Works in product/support ops, not a full-time dev.

## Layers

1. **Data** — `schema/*.sql`. SQLite. The store, and the only source of truth.
2. **Tools** — `strength_tools.py`. Dumb functions over the schema. No LLM in
   here, ever. That is what makes this layer testable in isolation.
3. **Model** — not built. Tool definitions for the API plus the loop.
4. **Client** — not built. Telegram bot, voice notes, speech-to-text.

## Rules that do not bend

- **The tool contract is frozen.** `strength_tools.md` is the spec. Signatures
  and return shapes do not change without a version bump and a migration note.
  If the implementation and the contract disagree, one of them is a bug —
  raise it, do not silently pick a side.
- **Schema changes go through Selim.** Never alter `schema/*.sql` unprompted.
  Propose, explain the cost, wait.
- **Never write a guess.** Every tool either writes the right row, or writes
  nothing and returns a status. Partial rows with nulls are worse than refusals:
  a wrong row costs every query that touches it, forever, and looks exactly like
  a correct one.
- **Every non-ok return goes to `tool_log`** with the arguments that produced it.
  Ok returns are not logged.
- **`performed_at` is stamped by the tool**, never accepted as an argument.
  Anything the model can pass, the model can invent.
- **Store pounds only.** No unit conversion anywhere in the codebase.

## Design decisions already settled

`decisions.md` is the record. Read it before proposing anything architectural.
Some of these look wrong until you read the reasoning:

- A continuation chain is **one set**. Segments inherit the parent's
  `set_number`. `continues_last` covers drops and run-ups equally — direction is
  readable from `load_value` along the chain, so it is not a column.
- Voided sets keep their `set_number`. Gaps are expected. Renumbering would make
  an earlier spoken confirmation retroactively false.
- Sessions key on a **training day**, not a calendar date: anything before 04:00
  belongs to the previous day. Calendar date splits a 23:30 workout in half.
- Sessions go stale after 6 hours idle, checked lazily on the next tool call.
  No cron job — that is a second thing that can fail.
- Transient session state (`in_warmup`, `active_superset_group`) lives on the
  `workouts` row, not in the conversation. A dropped context mid-workout would
  otherwise silently reclassify everything after it.
- No derived fields stored. No `workout_duration`, no `number_of_sets`.
- Soft delete via `voided`. Never hard-delete a set.

## Phase 1 is pure recording

Descriptive only. No goal-setting, no inference, no programming advice. This is
a sequencing decision, not a permanent one — but until Selim says phase 2, do
not add features that evaluate, predict, or prescribe.

## Testing

```
python -m pytest test_strength_tools.py -q
```

Every test maps to a rule stated in `strength_tools.md`. If you add behaviour,
add the test that pins it. If a test fails, work out whether the code or the
contract is wrong before changing either.

## How to work with Selim

- Direction before code. He asks for direction far more often than
  implementation — do not start writing unless asked.
- Short answers. No preamble, no recap of what he just said.
- Challenge weak reasoning directly. Do not soften a conclusion to agree.
- Say which decisions are expensive to change later and which are cheap to
  defer. Prefer reversible. Only push back on deferring something genuinely
  unreconstructable: in-the-moment subjective data, timestamps, anything that
  would require the same fact to be written twice.
- Give the failure mode before the benefit.
