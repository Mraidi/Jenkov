# Jenkov — strength tools (layer 1)

Implements `strength_tools.md` v1.2 against `strength_schema.sql`.
No LLM anywhere in here. That is deliberate: this layer is either correct or it
isn't, and you find out from the tests rather than by guessing at the model.

## Run

```
pip install pytest
python db.py                              # creates jenkov.db + seed catalog
python -m pytest test_strength_tools.py -q
```

## Files

| File | What it is |
|---|---|
| `db.py` | connections, init, read-only handle |
| `strength_tools.py` | the eleven verbs |
| `test_strength_tools.py` | 41 tests, one per contract rule |
| `schema/` | copies of the project `.sql` files |

Every function takes an open connection as its first argument, so tests run
against a throwaway database and nothing touches `jenkov.db` by accident.

## Two things the tests caught

**Calendar date was the wrong unit for a session.** A workout starting 23:30
was being abandoned at 00:15 as "yesterday's session" — the exact split the
04:00 rollover rule was written to prevent. Sessions now key on a *training
day*, where anything before 04:00 belongs to the previous day.

**`end_session` counted warm-ups in its total.** "Done, 6 sets" after five
working sets and one warm-up is not wrong exactly, but it is ambiguous in the
one place that has to be unambiguous. Now returns `total_sets` (working) and
`warmup_sets` separately.

Neither was visible from reading the contract.

## Not built yet

- Layer 2: tool definitions for the API, the model loop
- Layer 3: `mike_persona.md` as the system prompt
- Client: Telegram, voice notes, speech-to-text
