# Jenkov — future features

Parking lot. Nothing here is committed. The point is that a good idea can be
written down and then left alone, instead of turning into scope creep.

Ordered by phase, not priority. An item moves to `decisions.md` when it is
settled, or gets deleted when it is rejected — with the reasoning kept in the
rejected section below, so it does not come back as a fresh idea in six weeks.

---

## Near-term (does not need phase 2, just not built yet)

- **Previous-set recall on log.** When a set is logged, echo the same
  exercise's last performance. Zero analysis, immediately useful, and it
  double-checks the data by putting it in front of me.
- **Weekly digest.** What I did this week, what I did last week. Descriptive
  only. This is what keeps a pure-recording phase from feeling like a chore
  with no return.
- **Proactive scheduler.** Cron job, unprompted messages. Turns a chatbot into
  something that feels like an agent. Cheap on a bot platform, expensive on a
  native app.
- **Catalog reads mid-session.** "What can I do for triceps" is a query against
  `exercises`, descriptive, allowed now. Distinct from "what should I do next",
  which is programming.
- **Bulk warm-up fix.** If `end_warmup` is never called the whole session is
  flagged warm-up. Needs a correction path beyond `amend_last`.

## Phase 2 (planning and inference)

- **Programming.** Mike proposes the next session, progressive overload,
  deload timing. Requires enough data to say anything non-noisy.
- **Seed `workout_plans`.** Once the split holds for a few weeks. Makes
  adherence measurable — planned versus performed.
- **Goals, manifesto, day planning.** Jenkov's own layer. Exists on the
  thinking board already. Explicitly out of scope until phase 2 is declared.
- **Equipment-exhaustive exercise catalog.** The full list of what my equipment
  permits, versus the observed list I actually train. The gap between them is
  the interesting part: movements available to me that I never touch.
- **`activities` table.** General-purpose activity log under Jenkov. Workouts
  backfill into it with `INSERT ... SELECT`. Only field that cannot be
  reconstructed is in-the-moment subjective score, which is why
  `enjoyment_1_10` is already on `workouts`.
- **`to_dos` and `plan_day`.** Forward-looking by nature, so they need an
  explicit exemption from the descriptive-only rule.

## New domains

- **Cardio, walks, runs.** Not Mike's. Different shape entirely — distance,
  pace, duration, heart rate, no sets or reps. Its own domain schema, keyed on
  date like everything else.
- **Gordon** — food, meals, groceries. Designed on Miro, not drafted.
- **Doc** — physical health. Named only. Recording and description only,
  permanently.
- **Freud** — mental health. Designed on Miro, not drafted. Same permanent
  restriction as Doc.
- **More agents.** The original design has others. This list is not the scope.

## Interface

- **Distinct TTS voice per agent.** Cheapest way to make personas feel
  genuinely separate. Providers support this today.
- **Native app.** Only after the rented client hits something it genuinely
  cannot do. Backend is identical either way.
- **Apple Health / Apple Fitness import.** Heart rate, calories, steps, sleep.
  Its own time-series table joined on timestamp, not columns on `workouts`.
- **Photo and receipt capture.** Meal photos for Gordon, grocery receipt
  emails. Receipts are genuinely automatable; meal macros from photos are not
  yet reliable enough for analysis.
- **MCP transport.** Same tool contract reachable from the bot and from a
  desktop client. Earns its place when there is a second client, not before.

## Data and correctness

- **Time under tension.** Needs a set-start utterance as well as a set-end one.
  Two extra things to say per set, roughly 20 sets a session. Probably not
  worth it for strength work; revisit if the logging flow turns out to be
  cheaper than expected.
- **Cross-domain analysis.** Sleep against volume, food against energy. Needs
  two domains with real data first. SQL joins, not agent-to-agent messaging.
- **Fuzzy exercise matching.** Deliberately absent. Revisit only if the
  ask-once-then-alias flow proves too slow in practice — `tool_log` will show
  it.

---

## Rejected, with reasoning

Kept so these do not return as fresh ideas.

- **Pause verb.** Sets carry their own timestamps, so a long gap is already
  derivable. A `paused` state can be entered and never exited: a new failure
  mode for no new information.
- **Automated error repair pipeline.** LLM proposes a fix, I approve. Sounds
  safe, degrades predictably: by the twentieth correct-looking patch, approval
  is a formality and the rule that schema changes go through me stops binding.
  At a handful of rows a week, reviewing by hand costs less than the pipeline.
- **Multi-agent as the starting architecture.** Agents partition tools and
  context, not data. Cross-domain questions are joins. Splitting early buys
  coordination overhead and buys nothing back.
- **Storing derived fields.** No `workout_duration`, no `number_of_sets`. They
  can disagree with reality after a correction.
- **15-minute session auto-close.** Splits one workout into two rows after a
  long rest or a phone call. Auto-close is measured in hours.
