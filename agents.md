# Jenkov — agent roster

Jenkov is the orchestrator. Everything below is a persona beneath it:
a system-prompt fragment plus a subset of tools, not a separate service.

This list is not the scope of the project. More agents exist in the original
design and will be added.

| Agent | Domain | Schema file | Status |
|---|---|---|---|
| Jenkov | orchestration, activities, to-dos, day planning | `jenkov_schema.sql` | core tables drafted (`daily_log`, `log_unstructured`); activities and to-dos deferred |
| Mike | strength training | `strength_schema.sql` | schema drafted |
| Gordon | food, meals, groceries | `food_schema.sql` | designed on Miro, not yet drafted |
| Doc | physical health | `health_schema.sql` | named only |
| Freud | mental health | `mental_health_schema.sql` | designed on Miro, not yet drafted |

## Permanent restrictions

- **Doc and Freud record and describe only.** No diagnostic or treatment advice,
  no interpretation of symptoms. This does not lift at phase 2.

## Checklist for introducing a new agent

Work through these in order. The first is the only irreversible one.

1. **What is unreconstructable if not captured on day one?** In-the-moment
   subjective ratings, timestamps, anything that requires the same fact to be
   written twice. Everything else can be added later without loss.
2. **What is the join key to the rest of the system?** Date or timestamp.
   No agent gets an isolated store.
3. **Does any existing table already own these facts?** One writer per fact.
   If two could hold the same event, name the owner and make the other derive.
4. **What are the write tools?** One verb each, dumb, independently testable
   outside the model.
5. **What does correction look like?** Undo and amend before anything else.
6. **What is the guideline document?** The knowledge artifact this agent may
   propose edits to. Schema and signatures stay frozen.
