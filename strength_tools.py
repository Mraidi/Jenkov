"""Strength domain tools. Implements strength_tools.md v1.1.

These are dumb functions. No model, no prompt, no conversation state. Every
function takes plain arguments and returns a dict with `status` and `say`.
Testable without an LLM anywhere in the loop — which is the point: when
something is wrong later, this layer is either correct or it isn't, and you
find out here rather than by guessing at the model.
"""
import json
import re
import sqlite3
from datetime import datetime, timedelta

import db

AGENT = "mike"
CONTRACT_VERSION = "1.1"

STALE_HOURS = 6
ROLLOVER_HOUR = 4          # 04:00 local
UNDO_CAP = 5
AMEND_CAP = 5
ROW_CAP = 200

AMENDABLE = {
    "reps", "load_lb", "load_type", "rpe", "is_warmup",
    "to_failure", "exercise", "note",
}
LOAD_TYPES = {"external", "bodyweight", "assisted", "banded"}


# ---------------------------------------------------------------------------
# plumbing
# ---------------------------------------------------------------------------

def _now():
    return datetime.now()


def _ts(dt=None):
    return (dt or _now()).strftime("%Y-%m-%d %H:%M:%S")


def _today(dt=None):
    return (dt or _now()).strftime("%Y-%m-%d")


def _training_day(dt=None):
    """The day a session belongs to. Before 04:00 counts as the previous day,
    so a session that starts at 23:30 and runs past midnight is one session.
    Calendar date is the wrong unit here: it splits late-night workouts in half,
    which is the same failure the rollover rule was written to avoid."""
    dt = dt or _now()
    if dt.hour < ROLLOVER_HOUR:
        dt = dt - timedelta(days=1)
    return dt.strftime("%Y-%m-%d")


def _log_failure(con, tool_name, args, status, message=""):
    """Every non-ok return lands in tool_log with the args that produced it.
    Ok returns are not logged — volume without signal."""
    con.execute(
        "INSERT INTO tool_log (agent, tool_name, args_json, status, message) "
        "VALUES (?,?,?,?,?)",
        (AGENT, tool_name, json.dumps(args, default=str), status, message),
    )
    con.commit()


def _fail(con, tool, args, status, say, **extra):
    _log_failure(con, tool, args, status, say)
    return {"status": status, "say": say, **extra}


def _open_session(con):
    return con.execute(
        "SELECT * FROM workouts WHERE status='open' ORDER BY id DESC LIMIT 1"
    ).fetchone()


def _last_activity(con, workout_id):
    """Last non-voided set time, falling back to started_at."""
    r = con.execute(
        "SELECT MAX(performed_at) AS t FROM performed_sets "
        "WHERE workout_id=? AND voided=0",
        (workout_id,),
    ).fetchone()
    if r and r["t"]:
        return datetime.strptime(r["t"], "%Y-%m-%d %H:%M:%S")
    w = con.execute("SELECT started_at FROM workouts WHERE id=?", (workout_id,)).fetchone()
    if w and w["started_at"]:
        return datetime.strptime(w["started_at"], "%Y-%m-%d %H:%M:%S")
    return None


def _is_stale(con, session, now=None):
    """Stale if last activity is > STALE_HOURS old, or the session crosses
    04:00 local. Checked lazily on the next call — there is no user waiting at
    4am, and a cron job is a second thing that can fail."""
    now = now or _now()
    last = _last_activity(con, session["id"])
    if last is None:
        return False
    if now - last > timedelta(hours=STALE_HOURS):
        return True
    # rollover: has an 04:00 boundary passed between last activity and now?
    boundary = last.replace(hour=ROLLOVER_HOUR, minute=0, second=0, microsecond=0)
    if boundary <= last:
        boundary += timedelta(days=1)
    return now >= boundary


def _abandon(con, session):
    con.execute(
        "UPDATE workouts SET status='abandoned', ended_at=? WHERE id=?",
        (_ts(), session["id"]),
    )
    con.commit()


def _live_session(con, now=None):
    """Returns (session_row_or_None, note_string). Closes stale sessions."""
    s = _open_session(con)
    if s is None:
        return None, ""
    now = now or _now()
    if s["workout_date"] != _training_day(now):
        _abandon(con, s)
        return None, f"Closed {s['workout_date']} session, it was left open."
    if _is_stale(con, s, now):
        _abandon(con, s)
        return None, "Previous session went stale, closed it."
    return s, ""


def _resolve_exercise(con, spoken):
    """Exact match on canonical_name, then aliases. Lowercased and trimmed.
    No fuzzy matching — that is where silent wrong-row writes come from."""
    if not spoken:
        return None, []
    key = spoken.strip().lower()
    r = con.execute(
        "SELECT * FROM exercises WHERE lower(canonical_name)=? AND is_active=1", (key,)
    ).fetchone()
    if r:
        return r, []
    r = con.execute(
        "SELECT e.* FROM exercise_aliases a JOIN exercises e ON e.id=a.exercise_id "
        "WHERE lower(a.alias)=? AND e.is_active=1",
        (key,),
    ).fetchone()
    if r:
        return r, []
    cands = con.execute(
        "SELECT DISTINCT canonical_name FROM exercises "
        "WHERE is_active=1 AND canonical_name LIKE ? LIMIT 3",
        (f"%{key}%",),
    ).fetchall()
    return None, [c["canonical_name"] for c in cands]


def _last_set(con, workout_id, exercise_id=None):
    q = ("SELECT * FROM performed_sets WHERE workout_id=? AND voided=0 "
         + ("AND exercise_id=? " if exercise_id else "")
         + "ORDER BY id DESC LIMIT 1")
    args = (workout_id, exercise_id) if exercise_id else (workout_id,)
    return con.execute(q, args).fetchone()


def _fmt_load(row_load, load_type):
    if load_type == "bodyweight":
        return "bodyweight" if row_load is None else f"bodyweight +{row_load:g}"
    if load_type == "assisted":
        return f"-{row_load:g} assist"
    return f"{row_load:g} lb" if row_load is not None else "no load"


# ---------------------------------------------------------------------------
# session verbs
# ---------------------------------------------------------------------------

def start_session(con, split_label=None, location=None, energy_1_10=None, now=None):
    now = now or _now()
    args = {"split_label": split_label, "location": location, "energy_1_10": energy_1_10}

    s = _open_session(con)
    prefix = ""
    if s is not None:
        if s["workout_date"] == _training_day(now) and not _is_stale(con, s, now):
            return {"status": "already_open", "workout_id": s["id"],
                    "say": f"Already open. Session {s['id']}."}
        _abandon(con, s)
        prefix = (f"Closed {s['workout_date']} session first. "
                  if s["workout_date"] != _training_day(now)
                  else "Previous session was stale, closed it. ")

    cur = con.execute(
        "INSERT INTO workouts (workout_date, started_at, status, in_warmup, "
        "location, energy_1_10) VALUES (?,?, 'open', 1, ?, ?)",
        (_training_day(now), _ts(now), location, energy_1_10),
    )
    con.commit()
    wid = cur.lastrowid
    label = f"{split_label}. " if split_label else ""
    return {"status": "ok", "workout_id": wid, "say": f"{prefix}{label}Warm-up."}


def end_warmup(con, now=None):
    now = now or _now()
    s, note = _live_session(con, now)
    if s is None:
        return _fail(con, "end_warmup", {}, "no_session", "No session open.")
    if not s["in_warmup"]:
        n = con.execute("SELECT COUNT(*) c FROM performed_sets WHERE workout_id=? "
                        "AND is_warmup=1 AND voided=0", (s["id"],)).fetchone()["c"]
        return {"status": "ok", "warmup_sets": n, "duration_min": None,
                "say": "Warm-up already done."}

    con.execute("UPDATE workouts SET in_warmup=0 WHERE id=?", (s["id"],))
    con.commit()
    n = con.execute("SELECT COUNT(*) c FROM performed_sets WHERE workout_id=? "
                    "AND is_warmup=1 AND voided=0", (s["id"],)).fetchone()["c"]
    start = datetime.strptime(s["started_at"], "%Y-%m-%d %H:%M:%S") if s["started_at"] else None
    mins = int((now - start).total_seconds() // 60) if start else None
    tail = f" {mins} min." if mins is not None else ""
    return {"status": "ok", "warmup_sets": n, "duration_min": mins,
            "say": f"Warm-up done, {n} sets.{tail}"}


def start_superset(con, include_last=0, now=None):
    now = now or _now()
    args = {"include_last": include_last}
    s, note = _live_session(con, now)
    if s is None:
        return _fail(con, "start_superset", args, "no_session", "No session open.")

    if s["active_superset_group"] is not None:
        return {"status": "already_open", "group": s["active_superset_group"],
                "backfilled": 0, "say": f"Superset {s['active_superset_group']} already running."}

    r = con.execute("SELECT COALESCE(MAX(superset_group),0)+1 g FROM performed_sets "
                    "WHERE workout_id=?", (s["id"],)).fetchone()
    group = r["g"]

    backfilled = 0
    if include_last and include_last > 0:
        rows = con.execute(
            "SELECT id, superset_group FROM performed_sets WHERE workout_id=? AND voided=0 "
            "ORDER BY id DESC LIMIT ?", (s["id"], include_last)).fetchall()
        # already grouped sets are skipped, never reassigned
        ids = [r["id"] for r in rows if r["superset_group"] is None]
        for i in ids:
            con.execute("UPDATE performed_sets SET superset_group=? WHERE id=?", (group, i))
        backfilled = len(ids)

    con.execute("UPDATE workouts SET active_superset_group=? WHERE id=?", (group, s["id"]))
    con.commit()
    tail = f" Pulled in {backfilled}." if backfilled else ""
    return {"status": "ok", "group": group, "backfilled": backfilled,
            "say": f"Superset {group}.{tail}"}


def end_superset(con, now=None):
    now = now or _now()
    s, note = _live_session(con, now)
    if s is None:
        return _fail(con, "end_superset", {}, "no_session", "No session open.")
    group = s["active_superset_group"]
    if group is None:
        return {"status": "ok", "group": None, "sets": 0, "say": "No superset running."}
    n = con.execute("SELECT COUNT(*) c FROM performed_sets WHERE workout_id=? "
                    "AND superset_group=? AND voided=0", (s["id"], group)).fetchone()["c"]
    con.execute("UPDATE workouts SET active_superset_group=NULL WHERE id=?", (s["id"],))
    con.commit()
    return {"status": "ok", "group": group, "sets": n,
            "say": f"Superset done, {n} sets."}


def end_session(con, enjoyment_1_10=None, energy_1_10=None, note=None, now=None):
    now = now or _now()
    args = {"enjoyment_1_10": enjoyment_1_10, "energy_1_10": energy_1_10, "note": note}
    s = _open_session(con)
    if s is None:
        return _fail(con, "end_session", args, "no_session", "No session open.")

    con.execute(
        "UPDATE workouts SET ended_at=?, status='closed', active_superset_group=NULL, "
        "enjoyment_1_10=COALESCE(?, enjoyment_1_10), "
        "energy_1_10=COALESCE(?, energy_1_10), "
        "session_note=COALESCE(?, session_note) WHERE id=?",
        (_ts(now), enjoyment_1_10, energy_1_10, note, s["id"]),
    )
    con.commit()

    total = con.execute(
        "SELECT COUNT(*) c FROM performed_sets WHERE workout_id=? AND voided=0 "
        "AND parent_set_id IS NULL AND is_warmup=0", (s["id"],)).fetchone()["c"]
    warm = con.execute(
        "SELECT COUNT(*) c FROM performed_sets WHERE workout_id=? AND voided=0 "
        "AND parent_set_id IS NULL AND is_warmup=1", (s["id"],)).fetchone()["c"]
    exs = [r["canonical_name"] for r in con.execute(
        "SELECT DISTINCT e.canonical_name FROM performed_sets p "
        "JOIN exercises e ON e.id=p.exercise_id "
        "WHERE p.workout_id=? AND p.voided=0", (s["id"],))]
    start = datetime.strptime(s["started_at"], "%Y-%m-%d %H:%M:%S") if s["started_at"] else None
    mins = int((now - start).total_seconds() // 60) if start else None
    return {"status": "ok", "duration_min": mins, "total_sets": total,
            "warmup_sets": warm, "exercises": exs,
            "say": f"Done. {total} working sets, {len(exs)} exercises"
                   + (f", {mins} min." if mins is not None else ".")}


# ---------------------------------------------------------------------------
# log_set
# ---------------------------------------------------------------------------

def log_set(con, exercise=None, reps=None, load_lb=None, load_type=None,
            rpe=None, to_failure=None, continues_last=False, note=None, now=None):
    now = now or _now()
    args = {"exercise": exercise, "reps": reps, "load_lb": load_lb,
            "load_type": load_type, "rpe": rpe, "to_failure": to_failure,
            "continues_last": continues_last, "note": note}

    # --- session: find it, or open one. A set is never lost because I forgot
    # to say "start workout".
    s, note_prefix = _live_session(con, now)
    if s is None:
        opened = start_session(con, now=now)
        s = con.execute("SELECT * FROM workouts WHERE id=?", (opened["workout_id"],)).fetchone()
        note_prefix = (note_prefix + " Started a session. ").strip() + " "

    prev = _last_set(con, s["id"])

    # --- continuation
    parent = None
    if continues_last:
        if prev is None:
            return _fail(con, "log_set", args, "no_parent",
                         "Nothing to continue from.")
        parent = prev
        ex = con.execute("SELECT * FROM exercises WHERE id=?", (parent["exercise_id"],)).fetchone()
    else:
        # --- exercise resolution
        if exercise:
            ex, cands = _resolve_exercise(con, exercise)
            if ex is None:
                return _fail(con, "log_set", args, "unresolved",
                             f"Don't know '{exercise}'.", candidates=cands)
        elif prev is not None:
            ex = con.execute("SELECT * FROM exercises WHERE id=?", (prev["exercise_id"],)).fetchone()
        else:
            return _fail(con, "log_set", args, "need_exercise", "Which exercise?")

    # --- reps
    if reps is None:
        return _fail(con, "log_set", args, "need_reps", "How many reps?")

    # --- load
    if parent is not None:
        # continuation: exercise inherited, load must be given or inherited
        lt = load_type or parent["load_type"]
        lv = load_lb if load_lb is not None else parent["load_value"]
    elif ex["is_bodyweight_base"]:
        lt = load_type or "bodyweight"
        lv = load_lb  # None means plain bodyweight; a number means added weight
    else:
        lt = load_type or "external"
        if load_lb is not None:
            lv = load_lb
        else:
            same = _last_set(con, s["id"], ex["id"])
            if same is not None and same["load_value"] is not None:
                lv = same["load_value"]
                lt = load_type or same["load_type"]
            else:
                return _fail(con, "log_set", args, "need_load", "What weight?")

    if lt not in LOAD_TYPES:
        return _fail(con, "log_set", args, "bad_load_type", f"Unknown load type '{lt}'.")

    # --- set_number: a continuation chain is one set
    if parent is not None:
        set_number = parent["set_number"]
    else:
        r = con.execute(
            "SELECT COALESCE(MAX(set_number),0)+1 n FROM performed_sets "
            "WHERE workout_id=? AND exercise_id=? AND parent_set_id IS NULL",
            (s["id"], ex["id"])).fetchone()
        set_number = r["n"]

    cur = con.execute(
        "INSERT INTO performed_sets (workout_id, exercise_id, set_number, reps, "
        "load_value, load_type, rpe, is_warmup, to_failure, parent_set_id, "
        "superset_group, performed_at, note) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (s["id"], ex["id"], set_number, reps, lv, lt, rpe,
         1 if s["in_warmup"] else 0, 1 if to_failure else 0,
         parent["id"] if parent else None,
         s["active_superset_group"], _ts(now), note),
    )
    con.commit()

    load_str = _fmt_load(lv, lt)
    if parent is not None:
        say = f"{note_prefix}Still set {set_number}. {reps} at {load_str}."
    else:
        say = f"{note_prefix}{ex['canonical_name']}, set {set_number}. {reps} at {load_str}."
    return {"status": "ok", "set_id": cur.lastrowid, "exercise": ex["canonical_name"],
            "set_number": set_number, "say": say.strip()}


# ---------------------------------------------------------------------------
# corrections
# ---------------------------------------------------------------------------

def undo_last(con, n=1, now=None):
    now = now or _now()
    args = {"n": n}
    s, _ = _live_session(con, now)
    if s is None:
        return _fail(con, "undo_last", args, "no_session", "No session open.")
    if n < 1 or n > UNDO_CAP:
        return _fail(con, "undo_last", args, "bad_n", f"Undo reaches {UNDO_CAP} sets.")

    rows = con.execute(
        "SELECT p.id, p.reps, p.load_value, p.load_type, p.set_number, e.canonical_name "
        "FROM performed_sets p JOIN exercises e ON e.id=p.exercise_id "
        "WHERE p.workout_id=? AND p.voided=0 ORDER BY p.id DESC LIMIT ?",
        (s["id"], n)).fetchall()
    if not rows:
        return _fail(con, "undo_last", args, "nothing_to_undo", "Nothing logged yet.")

    for r in rows:
        con.execute("UPDATE performed_sets SET voided=1 WHERE id=?", (r["id"],))
    con.commit()

    voided = [{"set_id": r["id"], "exercise": r["canonical_name"],
               "set_number": r["set_number"], "reps": r["reps"]} for r in rows]
    if len(rows) == 1:
        r = rows[0]
        say = f"Scratched {r['canonical_name']} set {r['set_number']}, {r['reps']} reps."
    else:
        say = f"Scratched last {len(rows)} sets."
    return {"status": "ok", "voided": voided, "say": say}


def amend_last(con, field, value, n=1, now=None):
    """n=1 is the last set, n=2 the one before it. Exists because supersets log
    two sets with no gap, so RPE is collected after the pair."""
    now = now or _now()
    args = {"field": field, "value": value, "n": n}
    s, _ = _live_session(con, now)
    if s is None:
        return _fail(con, "amend_last", args, "no_session", "No session open.")
    if field not in AMENDABLE:
        return _fail(con, "amend_last", args, "bad_field", f"Can't change {field}.")
    if n < 1 or n > AMEND_CAP:
        return _fail(con, "amend_last", args, "no_such_set", f"Reaches {AMEND_CAP} sets back.")

    rows = con.execute(
        "SELECT * FROM performed_sets WHERE workout_id=? AND voided=0 "
        "ORDER BY id DESC LIMIT ?", (s["id"], n)).fetchall()
    if len(rows) < n:
        return _fail(con, "amend_last", args, "no_such_set", "Not that many sets.")
    row = rows[n - 1]

    col = {"load_lb": "load_value"}.get(field, field)

    if field == "exercise":
        ex, cands = _resolve_exercise(con, value)
        if ex is None:
            return _fail(con, "amend_last", args, "unresolved",
                         f"Don't know '{value}'.", candidates=cands)
        before = con.execute("SELECT canonical_name FROM exercises WHERE id=?",
                             (row["exercise_id"],)).fetchone()["canonical_name"]
        con.execute("UPDATE performed_sets SET exercise_id=? WHERE id=?", (ex["id"], row["id"]))
        after = ex["canonical_name"]
    else:
        if field == "load_type" and value not in LOAD_TYPES:
            return _fail(con, "amend_last", args, "bad_load_type", f"Unknown load type '{value}'.")
        before = row[col]
        con.execute(f"UPDATE performed_sets SET {col}=? WHERE id=?", (value, row["id"]))
        after = value
    con.commit()

    return {"status": "ok", "before": before, "after": after,
            "set_number": row["set_number"],
            "say": f"Set {row['set_number']}: {field} {before} to {after}."}


# ---------------------------------------------------------------------------
# resolution helpers
# ---------------------------------------------------------------------------

def add_exercise_alias(con, exercise_id, alias):
    args = {"exercise_id": exercise_id, "alias": alias}
    key = (alias or "").strip().lower()
    if not key:
        return _fail(con, "add_exercise_alias", args, "bad_alias", "Empty alias.")
    ex = con.execute("SELECT * FROM exercises WHERE id=?", (exercise_id,)).fetchone()
    if ex is None:
        return _fail(con, "add_exercise_alias", args, "no_exercise", "No such exercise.")
    try:
        con.execute("INSERT INTO exercise_aliases (exercise_id, alias) VALUES (?,?)",
                    (exercise_id, key))
        con.commit()
    except sqlite3.IntegrityError:
        return _fail(con, "add_exercise_alias", args, "duplicate_alias",
                     f"'{key}' already taken.")
    return {"status": "ok", "say": f"Got it, '{key}' is {ex['canonical_name']}."}


def create_exercise(con, canonical_name, movement_pattern=None, primary_muscle=None,
                    equipment=None, is_bodyweight_base=0, alias=None):
    args = {"canonical_name": canonical_name, "alias": alias}
    key = (canonical_name or "").strip().lower()
    if not key:
        return _fail(con, "create_exercise", args, "bad_name", "Empty name.")
    try:
        cur = con.execute(
            "INSERT INTO exercises (canonical_name, movement_pattern, primary_muscle, "
            "equipment, is_bodyweight_base) VALUES (?,?,?,?,?)",
            (key, movement_pattern, primary_muscle, equipment, 1 if is_bodyweight_base else 0))
        con.commit()
    except sqlite3.IntegrityError:
        return _fail(con, "create_exercise", args, "duplicate", f"'{key}' already exists.")
    eid = cur.lastrowid
    if alias and alias.strip().lower() != key:
        add_exercise_alias(con, eid, alias)
    return {"status": "ok", "exercise_id": eid, "say": f"Added {key}."}


# ---------------------------------------------------------------------------
# overflow and read
# ---------------------------------------------------------------------------

def log_unstructured(con, domain, raw_text, now=None):
    now = now or _now()
    if not raw_text or not raw_text.strip():
        return _fail(con, "log_unstructured", {"domain": domain}, "empty", "Nothing to log.")
    con.execute("INSERT INTO log_unstructured (log_date, domain, raw_text) VALUES (?,?,?)",
                (_today(now), domain, raw_text.strip()))
    con.commit()
    return {"status": "ok", "say": "Parked it."}


_WRITE_WORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex)\b",
    re.I)


def run_query(con_ro, sql):
    """Single SELECT against a read-only connection. The read-only handle is the
    real guard; the keyword check just returns a clearer error."""
    s = (sql or "").strip().rstrip(";")
    if not s:
        return {"error": "empty query"}
    if ";" in s:
        return {"error": "one statement only"}
    if not re.match(r"^\s*(select|with)\b", s, re.I):
        return {"error": "SELECT only"}
    if _WRITE_WORDS.search(s):
        return {"error": "read-only"}
    try:
        rows = con_ro.execute(s).fetchmany(ROW_CAP)
        return {"rows": [dict(r) for r in rows], "count": len(rows)}
    except Exception as e:
        return {"error": str(e)}
