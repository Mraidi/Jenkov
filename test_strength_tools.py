"""Tests for strength_tools. Every test maps to a rule stated in
strength_tools.md — the contract is the spec.

Run: python -m pytest test_strength_tools.py -q
"""
from datetime import datetime, timedelta

import pytest

import db
import strength_tools as T


@pytest.fixture
def con(tmp_path):
    c = db.init(tmp_path / "t.db", seed=True)
    yield c
    c.close()


def ex_id(con, name):
    return con.execute("SELECT id FROM exercises WHERE canonical_name=?", (name,)).fetchone()["id"]


# --- sessions ---------------------------------------------------------------

def test_start_session_opens_in_warmup(con):
    r = T.start_session(con, split_label="pull")
    assert r["status"] == "ok"
    w = con.execute("SELECT * FROM workouts WHERE id=?", (r["workout_id"],)).fetchone()
    assert w["status"] == "open" and w["in_warmup"] == 1


def test_second_start_same_day_does_not_duplicate(con):
    a = T.start_session(con)
    b = T.start_session(con)
    assert b["status"] == "already_open" and b["workout_id"] == a["workout_id"]
    assert con.execute("SELECT COUNT(*) c FROM workouts").fetchone()["c"] == 1


def test_previous_day_session_is_abandoned(con):
    t0 = datetime(2026, 8, 20, 18, 0)
    a = T.start_session(con, now=t0)
    T.log_set(con, exercise="curls", reps=8, load_lb=50, now=t0)
    b = T.start_session(con, now=t0 + timedelta(days=1))
    assert b["workout_id"] != a["workout_id"]
    assert con.execute("SELECT status FROM workouts WHERE id=?", (a["workout_id"],)
                       ).fetchone()["status"] == "abandoned"


def test_six_hour_gap_is_stale(con):
    t0 = datetime(2026, 8, 20, 9, 0)
    a = T.start_session(con, now=t0)
    T.log_set(con, exercise="curls", reps=8, load_lb=50, now=t0)
    r = T.log_set(con, exercise="curls", reps=8, load_lb=50, now=t0 + timedelta(hours=7))
    assert r["status"] == "ok"
    assert con.execute("SELECT status FROM workouts WHERE id=?", (a["workout_id"],)
                       ).fetchone()["status"] == "abandoned"


def test_two_hour_gap_is_not_stale(con):
    """A long rest or a phone call must not split one workout in two."""
    t0 = datetime(2026, 8, 20, 9, 0)
    a = T.start_session(con, now=t0)
    T.log_set(con, exercise="curls", reps=8, load_lb=50, now=t0)
    T.log_set(con, exercise="curls", reps=8, now=t0 + timedelta(hours=2))
    assert con.execute("SELECT COUNT(*) c FROM workouts").fetchone()["c"] == 1


def test_late_night_session_survives_midnight(con):
    """04:00 rollover, not midnight — a late session is not split in half."""
    t0 = datetime(2026, 8, 20, 23, 30)
    T.start_session(con, now=t0)
    T.log_set(con, exercise="curls", reps=8, load_lb=50, now=t0)
    T.log_set(con, exercise="curls", reps=8, now=t0 + timedelta(minutes=45))
    assert con.execute("SELECT COUNT(*) c FROM workouts").fetchone()["c"] == 1


# --- warm-up ----------------------------------------------------------------

def test_warmup_flag_flips(con):
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=10, load_lb=20)
    T.end_warmup(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=50)
    rows = con.execute("SELECT is_warmup FROM performed_sets ORDER BY id").fetchall()
    assert [r["is_warmup"] for r in rows] == [1, 0]


def test_end_warmup_idempotent(con):
    T.start_session(con)
    T.end_warmup(con)
    assert T.end_warmup(con)["status"] == "ok"


# --- log_set ----------------------------------------------------------------

def test_implicit_session_open(con):
    r = T.log_set(con, exercise="curls", reps=8, load_lb=50)
    assert r["status"] == "ok"
    assert con.execute("SELECT COUNT(*) c FROM workouts").fetchone()["c"] == 1


def test_alias_resolves(con):
    r = T.log_set(con, exercise="Bicep Curls", reps=8, load_lb=50)
    assert r["exercise"] == "standing dumbbell curl"


def test_unresolved_writes_nothing_and_offers_candidates(con):
    T.start_session(con)
    r = T.log_set(con, exercise="curl", reps=8, load_lb=50)
    assert r["status"] == "unresolved"
    assert con.execute("SELECT COUNT(*) c FROM performed_sets").fetchone()["c"] == 0
    assert any("curl" in c for c in r["candidates"])


def test_missing_reps_writes_nothing(con):
    T.start_session(con)
    r = T.log_set(con, exercise="curls", load_lb=50)
    assert r["status"] == "need_reps"
    assert con.execute("SELECT COUNT(*) c FROM performed_sets").fetchone()["c"] == 0


def test_need_load_on_first_weighted_set(con):
    T.start_session(con)
    r = T.log_set(con, exercise="curls", reps=8)
    assert r["status"] == "need_load"
    assert con.execute("SELECT COUNT(*) c FROM performed_sets").fetchone()["c"] == 0


def test_bodyweight_never_waits_for_load(con):
    T.start_session(con)
    r = T.log_set(con, exercise="pullups", reps=8)
    assert r["status"] == "ok"
    row = con.execute("SELECT * FROM performed_sets").fetchone()
    assert row["load_type"] == "bodyweight" and row["load_value"] is None


def test_bodyweight_with_load_is_added_weight(con):
    T.start_session(con)
    T.log_set(con, exercise="dips", reps=5, load_lb=25)
    row = con.execute("SELECT * FROM performed_sets").fetchone()
    assert row["load_type"] == "bodyweight" and row["load_value"] == 25


def test_short_form_inherits_exercise_and_load(con):
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=50)
    r = T.log_set(con, reps=7)
    assert r["exercise"] == "standing dumbbell curl" and r["set_number"] == 2
    row = con.execute("SELECT * FROM performed_sets ORDER BY id DESC LIMIT 1").fetchone()
    assert row["load_value"] == 50


def test_need_exercise_when_nothing_to_inherit(con):
    T.start_session(con)
    assert T.log_set(con, reps=8)["status"] == "need_exercise"


def test_performed_at_is_not_an_argument(con):
    import inspect
    assert "performed_at" not in inspect.signature(T.log_set).parameters


# --- continuations ----------------------------------------------------------

def test_chain_is_one_set(con):
    T.start_session(con)
    T.end_warmup(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=60)
    T.log_set(con, reps=5, load_lb=40, continues_last=True)
    T.log_set(con, reps=4, load_lb=30, continues_last=True)
    nums = [r["set_number"] for r in con.execute(
        "SELECT set_number FROM performed_sets ORDER BY id")]
    assert nums == [1, 1, 1]
    heads = con.execute("SELECT COUNT(*) c FROM v_sets WHERE is_drop_segment=0").fetchone()["c"]
    assert heads == 1


def test_chain_ascending_also_works(con):
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=10, load_lb=30)
    for reps, load in [(8, 40), (6, 50), (4, 60)]:
        r = T.log_set(con, reps=reps, load_lb=load, continues_last=True)
        assert r["status"] == "ok"
    assert con.execute("SELECT COUNT(*) c FROM v_sets").fetchone()["c"] == 4


def test_next_clean_set_after_chain_increments(con):
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=60)
    T.log_set(con, reps=5, load_lb=40, continues_last=True)
    r = T.log_set(con, exercise="curls", reps=8, load_lb=60)
    assert r["set_number"] == 2


def test_continuation_without_parent_fails(con):
    T.start_session(con)
    r = T.log_set(con, reps=5, load_lb=40, continues_last=True)
    assert r["status"] == "no_parent"


# --- supersets --------------------------------------------------------------

def test_superset_group_inherited(con):
    T.start_session(con)
    T.start_superset(con)
    T.log_set(con, exercise="curls", reps=10, load_lb=40)
    T.log_set(con, exercise="skull crushers", reps=10, load_lb=30)
    T.end_superset(con)
    T.log_set(con, exercise="curls", reps=10, load_lb=40)
    groups = [r["superset_group"] for r in con.execute(
        "SELECT superset_group FROM performed_sets ORDER BY id")]
    assert groups == [1, 1, None]


def test_superset_backfills_retroactively(con):
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=10, load_lb=40)
    r = T.start_superset(con, include_last=1)
    assert r["backfilled"] == 1
    assert con.execute("SELECT superset_group FROM performed_sets").fetchone()[0] == r["group"]


def test_backfill_skips_already_grouped_sets(con):
    T.start_session(con)
    T.start_superset(con)
    T.log_set(con, exercise="curls", reps=10, load_lb=40)
    T.end_superset(con)
    T.log_set(con, exercise="shrugs", reps=10, load_lb=60)
    r = T.start_superset(con, include_last=2)
    assert r["backfilled"] == 1


# --- corrections ------------------------------------------------------------

def test_undo_soft_deletes(con):
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=50)
    T.undo_last(con)
    assert con.execute("SELECT voided FROM performed_sets").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) c FROM v_sets").fetchone()["c"] == 0


def test_voided_set_keeps_its_number(con):
    """Renumbering would make an earlier confirmation retroactively false."""
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=50)
    T.log_set(con, reps=8)
    T.undo_last(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=50)
    live = [r["set_number"] for r in con.execute("SELECT set_number FROM v_sets ORDER BY id")]
    assert live == [1, 3]


def test_undo_cap(con):
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=50)
    assert T.undo_last(con, n=6)["status"] == "bad_n"


def test_amend_last_default(con):
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=50)
    r = T.amend_last(con, "load_lb", 55)
    assert r["status"] == "ok" and r["after"] == 55
    assert con.execute("SELECT load_value FROM performed_sets").fetchone()[0] == 55


def test_amend_reaches_back_for_superset_rpe(con):
    """The reason n exists: two sets logged with no gap, RPE collected after."""
    T.start_session(con)
    T.start_superset(con)
    T.log_set(con, exercise="curls", reps=10, load_lb=40)
    T.log_set(con, exercise="skull crushers", reps=10, load_lb=30)
    T.amend_last(con, "rpe", 9, n=1)
    T.amend_last(con, "rpe", 8, n=2)
    rows = con.execute("SELECT rpe FROM performed_sets ORDER BY id").fetchall()
    assert [r["rpe"] for r in rows] == [8, 9]


def test_amend_out_of_range(con):
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=50)
    r = T.amend_last(con, "rpe", 8, n=3)
    assert r["status"] == "no_such_set"


def test_amend_rejects_frozen_fields(con):
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=50)
    for f in ["performed_at", "set_number", "workout_id"]:
        assert T.amend_last(con, f, 1)["status"] == "bad_field"


def test_amend_exercise_resolves(con):
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=50)
    r = T.amend_last(con, "exercise", "incline curls")
    assert r["after"] == "incline dumbbell curl"


# --- resolution helpers -----------------------------------------------------

def test_alias_then_resolves(con):
    T.start_session(con)
    r = T.log_set(con, exercise="hammer curls", reps=8, load_lb=40)
    assert r["status"] == "unresolved"
    T.add_exercise_alias(con, ex_id(con, "standing dumbbell curl"), "hammer curls")
    r = T.log_set(con, exercise="hammer curls", reps=8, load_lb=40)
    assert r["status"] == "ok"


def test_duplicate_alias_rejected(con):
    assert T.add_exercise_alias(con, ex_id(con, "pull-up"), "curls")["status"] == "duplicate_alias"


def test_create_exercise_with_alias(con):
    r = T.create_exercise(con, "zercher squat", alias="zerchers")
    assert r["status"] == "ok"
    T.start_session(con)
    assert T.log_set(con, exercise="zerchers", reps=5, load_lb=100)["status"] == "ok"


# --- read -------------------------------------------------------------------

def test_run_query_rejects_writes(tmp_path):
    c = db.init(tmp_path / "q.db", seed=True)
    c.close()
    ro = db.connect_ro(tmp_path / "q.db")
    for bad in ["DELETE FROM performed_sets",
                "SELECT 1; DROP TABLE exercises",
                "UPDATE exercises SET canonical_name='x'"]:
        assert "error" in T.run_query(ro, bad)
    assert T.run_query(ro, "SELECT COUNT(*) c FROM exercises")["rows"][0]["c"] == 39


def test_read_only_handle_actually_blocks(tmp_path):
    c = db.init(tmp_path / "r.db", seed=True)
    c.close()
    ro = db.connect_ro(tmp_path / "r.db")
    with pytest.raises(Exception):
        ro.execute("DELETE FROM exercises")


# --- error logging ----------------------------------------------------------

def test_failures_are_logged_with_args(con):
    T.start_session(con)
    T.log_set(con, exercise="hammer curls", reps=8, load_lb=40)
    row = con.execute("SELECT * FROM tool_log ORDER BY id DESC LIMIT 1").fetchone()
    assert row["status"] == "unresolved" and "hammer curls" in row["args_json"]


def test_ok_returns_are_not_logged(con):
    T.start_session(con)
    T.log_set(con, exercise="curls", reps=8, load_lb=50)
    assert con.execute("SELECT COUNT(*) c FROM tool_log").fetchone()["c"] == 0


# --- end to end -------------------------------------------------------------

def test_full_session(con):
    T.start_session(con, split_label="pull")
    T.log_set(con, exercise="pullups", reps=5)
    T.end_warmup(con)
    T.log_set(con, exercise="pullups", reps=8, rpe=8)
    T.log_set(con, reps=7, rpe=9)
    T.log_set(con, exercise="one arm row", reps=10, load_lb=70, rpe=8)
    T.start_superset(con, include_last=1)
    T.log_set(con, exercise="lat raises", reps=15, load_lb=15)
    T.end_superset(con)
    T.log_set(con, exercise="curls", reps=10, load_lb=45)
    T.log_set(con, reps=6, load_lb=30, continues_last=True)
    r = T.end_session(con, enjoyment_1_10=8, energy_1_10=7)

    assert r["status"] == "ok"
    assert r["total_sets"] == 5          # working sets, chain counted once
    w = con.execute("SELECT * FROM workouts").fetchone()
    assert w["status"] == "closed" and w["enjoyment_1_10"] == 8
    assert con.execute("SELECT COUNT(*) c FROM v_sets WHERE is_warmup=1").fetchone()["c"] == 1
