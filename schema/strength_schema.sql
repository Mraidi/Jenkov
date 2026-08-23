-- strength_schema.sql
-- Domain: strength training. Current agent persona: Mike.
-- Depends on jenkov_schema.sql (joins to daily_log on date).
-- SQLite dialect. Portable to Postgres with minor type changes.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- exercises
-- Reference table. One row per distinct movement.
-- The agent must resolve to an existing row or ask before creating a new one.
-- ---------------------------------------------------------------------------
CREATE TABLE exercises (
    id                  INTEGER PRIMARY KEY,
    canonical_name      TEXT    NOT NULL UNIQUE,  -- 'barbell bench press'
    movement_pattern    TEXT,                     -- 'horizontal push', 'hinge'
    primary_muscle      TEXT,
    equipment           TEXT,                     -- 'barbell', 'dumbbell', 'cable'
    is_bodyweight_base  INTEGER NOT NULL DEFAULT 0,  -- 0/1
    is_active           INTEGER NOT NULL DEFAULT 1,  -- retire without deleting
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- exercise_aliases
-- Voice logging produces many names for one movement: 'bench', 'flat bench',
-- 'barbell bench'. Without this, six months of data will not aggregate.
-- ---------------------------------------------------------------------------
CREATE TABLE exercise_aliases (
    id          INTEGER PRIMARY KEY,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id),
    alias       TEXT    NOT NULL UNIQUE           -- stored lowercase
);

CREATE INDEX idx_alias_exercise ON exercise_aliases(exercise_id);

-- ---------------------------------------------------------------------------
-- workout_plans / plan_items
-- What I am supposed to do. Distinct from what I did.
-- Kept separate so deviation is measurable rather than destructive.
-- ---------------------------------------------------------------------------
CREATE TABLE workout_plans (
    id          INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL,
    split_label TEXT,                             -- 'push', 'pull', 'legs'
    active_from TEXT,                             -- YYYY-MM-DD
    active_to   TEXT,                             -- null = current
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE plan_items (
    id                INTEGER PRIMARY KEY,
    plan_id           INTEGER NOT NULL REFERENCES workout_plans(id),
    exercise_id       INTEGER NOT NULL REFERENCES exercises(id),
    order_index       INTEGER NOT NULL,
    target_sets       INTEGER,
    target_reps_low   INTEGER,
    target_reps_high  INTEGER,
    target_load_lb    REAL,
    target_rpe        REAL,
    notes             TEXT
);

CREATE INDEX idx_plan_items_plan ON plan_items(plan_id);

-- ---------------------------------------------------------------------------
-- workouts
-- One row per session. status='open' is what makes mid-workout voice logging
-- work: log_set finds the open session itself rather than relying on the
-- conversation to remember which session is current.
-- ---------------------------------------------------------------------------
CREATE TABLE workouts (
    id            INTEGER PRIMARY KEY,
    plan_id       INTEGER REFERENCES workout_plans(id),  -- null = off-program
    workout_date  TEXT    NOT NULL,               -- YYYY-MM-DD, joins daily_log
    started_at    TEXT,                           -- ISO timestamp
    ended_at      TEXT,
    status        TEXT    NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open', 'closed', 'abandoned')),
    -- Transient session state. Lives here rather than in the conversation so a
    -- dropped context mid-workout does not lose it.
    in_warmup     INTEGER NOT NULL DEFAULT 1,     -- 0/1, cleared by end_warmup
    active_superset_group INTEGER,                -- null = not in a superset
    location      TEXT,
    session_note  TEXT,
    energy_1_10   INTEGER CHECK (energy_1_10 BETWEEN 1 AND 10),
    enjoyment_1_10 INTEGER CHECK (enjoyment_1_10 BETWEEN 1 AND 10),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_workouts_date   ON workouts(workout_date);
CREATE INDEX idx_workouts_status ON workouts(status);

-- ---------------------------------------------------------------------------
-- performed_sets
-- One row per set. Duration and set counts are NOT stored — they are derived,
-- and storing them means they can disagree with reality after a correction.
--
-- load_value + load_type replaces a single ambiguous weight column:
--   external   -> load_value is the weight on the bar/stack
--   bodyweight -> load_value is null or added weight (weighted dips)
--   assisted   -> load_value is the assistance, i.e. negative load
--   banded     -> load_value is nominal; band tension is not linear
-- Store POUNDS only. load_value is always lb. The unit lives in the column
-- name where it can be seen (target_load_lb, bodyweight_lb); load_value is
-- documented here. Never mix units in one column.
-- ---------------------------------------------------------------------------
CREATE TABLE performed_sets (
    id            INTEGER PRIMARY KEY,
    workout_id    INTEGER NOT NULL REFERENCES workouts(id),
    exercise_id   INTEGER NOT NULL REFERENCES exercises(id),
    set_number    INTEGER NOT NULL,
    reps          INTEGER,
    load_value    REAL,
    load_type     TEXT    NOT NULL DEFAULT 'external'
                  CHECK (load_type IN ('external','bodyweight','assisted','banded')),
    rpe           REAL    CHECK (rpe BETWEEN 1 AND 10),
    is_warmup     INTEGER NOT NULL DEFAULT 0,
    to_failure    INTEGER NOT NULL DEFAULT 0,
    -- Drop set: each segment is its own row, pointing at the segment before it.
    -- Without this, 8@60 then 6@40 twenty seconds apart is indistinguishable
    -- from two rushed sets, and neither set counts nor rest intervals are honest.
    parent_set_id INTEGER REFERENCES performed_sets(id),
    -- Supersets: sets sharing a group within one session were paired.
    -- Changes what the gap between timestamps means.
    superset_group INTEGER,
    performed_at  TEXT    NOT NULL DEFAULT (datetime('now')),  -- per-set, not per-session
    note          TEXT,
    voided        INTEGER NOT NULL DEFAULT 0     -- soft delete, for undo/correction
);

CREATE INDEX idx_sets_workout  ON performed_sets(workout_id);
CREATE INDEX idx_sets_exercise ON performed_sets(exercise_id);
CREATE INDEX idx_sets_voided   ON performed_sets(voided);

-- ---------------------------------------------------------------------------
-- Convenience view: live sets only, with names resolved.
-- The read tool should prefer this over the raw table.
-- ---------------------------------------------------------------------------
CREATE VIEW v_sets AS
SELECT
    ps.id,
    w.workout_date,
    w.id                AS workout_id,
    e.canonical_name    AS exercise,
    e.primary_muscle,
    ps.set_number,
    ps.reps,
    ps.load_value,
    ps.load_type,
    ps.rpe,
    ps.is_warmup,
    ps.to_failure,
    ps.parent_set_id,
    CASE WHEN ps.parent_set_id IS NOT NULL THEN 1 ELSE 0 END AS is_drop_segment,
    ps.superset_group,
    ps.performed_at
FROM performed_sets ps
JOIN workouts  w ON w.id = ps.workout_id
JOIN exercises e ON e.id = ps.exercise_id
WHERE ps.voided = 0;
