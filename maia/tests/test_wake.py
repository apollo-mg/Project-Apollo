from datetime import date, datetime, timedelta

import pytest

from maia.wake import InterruptionBudget, WakeCondition, WakeStore

NOW = datetime(2026, 11, 2, 22, 0)
LATER = NOW + timedelta(days=7)


@pytest.fixture
def store():
    return WakeStore()


def test_each_trigger_fires_on_its_observation(store):
    ids = {
        "time": store.add(WakeCondition("time", "2026-11-03T08:00", "he reads the brief before work", LATER)),
        "file": store.add(WakeCondition("file", "data/receipts/*/RESULT_*.md", "the run lands a result", LATER)),
        "commit": store.add(WakeCondition("commit", "abstend:", "the v3 rerun is committed", LATER)),
        "event": store.add(WakeCondition("event", "irc:mention", "he answers the question", LATER)),
    }
    assert store.due(NOW, {}) == []
    fired = store.due(datetime(2026, 11, 3, 9, 0), {
        "file": ["data/receipts/abench/RESULT_V3.md"],
        "commit": ["1c9cda9 abstend: instrument v3"],
        "event": ["irc:mention"],
    })
    assert {f.condition.id for f in fired} == set(ids.values())
    assert {f.reason for f in fired} == {"matched"}


def test_non_matching_observations_do_not_fire(store):
    store.add(WakeCondition("file", "*.md", "h", LATER))
    store.add(WakeCondition("commit", "maia:", "h", LATER))
    store.add(WakeCondition("event", "irc:mention", "h", LATER))
    assert store.due(NOW, {"file": ["a.py"], "commit": ["abc docs"], "event": ["irc:join"]}) == []


def test_fires_once(store):
    store.add(WakeCondition("event", "e", "h", LATER))
    assert len(store.due(NOW, {"event": ["e"]})) == 1
    assert store.due(NOW, {"event": ["e"]}) == [] and store.pending() == []


def test_timeout_fires_with_hypothesis_unmet(store):
    store.add(WakeCondition("commit", "maia:", "the library gets merged this week", LATER))
    [f] = store.due(LATER, {})
    assert f.reason == "timeout" and f.condition.hypothesis == "the library gets merged this week"


@pytest.mark.parametrize("cond", [
    WakeCondition("cron", "* * * * *", "h", LATER),
    WakeCondition("event", "e", "  ", LATER),
    WakeCondition("time", "tomorrow-ish", "h", LATER),
])
def test_rejects_bad_conditions(store, cond):
    with pytest.raises(ValueError):
        store.add(cond)


def test_budget_defaults_to_one_and_resets_daily():
    b, d1, d2 = InterruptionBudget(), date(2026, 11, 2), date(2026, 11, 3)
    assert b.remaining(d1) == 1
    assert b.spend(d1) is True
    assert b.spend(d1) is False and b.remaining(d1) == 0
    assert b.remaining(d2) == 1 and b.spend(d2) is True


def test_budget_per_day_configurable():
    b, d = InterruptionBudget(per_day=3), date(2026, 11, 2)
    assert [b.spend(d) for _ in range(4)] == [True, True, True, False]
