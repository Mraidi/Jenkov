-- jenkov_schema.sql
-- Core/shared tables. Not owned by any single domain agent.
-- Every domain schema keys on date or timestamp so these join cleanly.
-- SQLite dialect. Portable to Postgres with minor type changes.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- daily_log
-- One row per calendar day. The cross-domain join key.
-- Doc, Freud and future agents add their own tables keyed on log_date, or
-- propose columns here for things that are genuinely one-per-day.
-- Everything here is nullable: a partial day is still a valid day.
-- ---------------------------------------------------------------------------
CREATE TABLE daily_log (
    id              INTEGER PRIMARY KEY,
    log_date        TEXT    NOT NULL UNIQUE,      -- YYYY-MM-DD
    sleep_hours     REAL,
    energy_1_10     INTEGER CHECK (energy_1_10 BETWEEN 1 AND 10),
    bodyweight_lb   REAL,
    note            TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- log_unstructured
-- The overflow tool's target. Anything the model wanted to record but had no
-- column for lands here instead of being forced into the wrong field.
-- Review periodically: repeated entries with the same domain are the signal
-- that a real table or column is needed.
-- ---------------------------------------------------------------------------
CREATE TABLE log_unstructured (
    id              INTEGER PRIMARY KEY,
    logged_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    log_date        TEXT    NOT NULL,             -- YYYY-MM-DD, for joining
    domain          TEXT,                         -- 'strength', 'food', free text
    raw_text        TEXT    NOT NULL,
    reviewed        INTEGER NOT NULL DEFAULT 0    -- 0/1, set by me during review
);

CREATE INDEX idx_unstructured_date   ON log_unstructured(log_date);
CREATE INDEX idx_unstructured_review ON log_unstructured(reviewed);

-- ---------------------------------------------------------------------------
-- tool_log
-- Every non-ok tool return, with the arguments that produced it.
-- This is the only feedback loop on whether the system actually works.
-- Read it weekly. Fifteen identical failures is a fix; one is noise.
--
-- Deliberately NOT an automated repair pipeline. Volume here is a handful of
-- rows a week — small enough to fix by hand, and fixing by hand is what keeps
-- schema changes genuinely going through me rather than through a rubber stamp.
-- ---------------------------------------------------------------------------
CREATE TABLE tool_log (
    id          INTEGER PRIMARY KEY,
    called_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    agent       TEXT,                             -- 'mike', 'gordon'
    tool_name   TEXT    NOT NULL,
    args_json   TEXT,                             -- as received, before defaults
    status      TEXT    NOT NULL,                 -- 'unresolved', 'need_reps', ...
    message     TEXT,
    resolved    INTEGER NOT NULL DEFAULT 0        -- 0/1, set by me during review
);

CREATE INDEX idx_tool_log_status   ON tool_log(status);
CREATE INDEX idx_tool_log_resolved ON tool_log(resolved);
