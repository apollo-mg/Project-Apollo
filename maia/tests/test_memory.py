import sqlite3
from datetime import date

import pytest

from maia.memory import MemoryStore

D = date(2026, 11, 2)


@pytest.fixture
def store():
    return MemoryStore()


def test_add_get_roundtrip(store):
    i = store.add("prefers questions to summaries", "preference", 0.8, 0.9, "chat", "irc 2026-11-02", today=D)
    m = store.get(i)
    assert (m.text, m.kind, m.provenance, m.ref, m.status) == (
        "prefers questions to summaries", "preference", "chat", "irc 2026-11-02", "active")
    assert m.created == D and m.check_by > D and m.last_verified is None and m.corrected_by is None


@pytest.mark.parametrize("kw", [dict(kind="rumour"), dict(provenance="vibes"), dict(importance=1.5), dict(trust=-0.1)])
def test_add_rejects_bad_fields(store, kw):
    args = dict(text="x", kind="fact", importance=0.5, trust=0.5, provenance="chat") | kw
    with pytest.raises(ValueError):
        store.add(**args)


def test_rank_uses_both_axes(store):
    important_wrong = store.add("important but untrusted", "fact", 1.0, 0.2, "inferred", today=D)
    solid = store.add("moderately important, trusted", "fact", 0.6, 0.9, "receipt", today=D)
    assert [m.id for m in store.rank(2)] == [solid, important_wrong]


def test_corrections_and_confirmations_rank_high(store):
    plain = store.add("plain", "fact", 0.7, 0.8, "receipt", today=D)
    confirmed = store.add("confirmed", "fact", 0.7, 0.8, "receipt", today=D)
    for _ in range(3):
        store.verify(confirmed, D)
    wrong = store.add("the update broke it", "fact", 0.7, 0.8, "inferred", today=D)
    corr = store.retire(wrong, "it was the date, not the update; compare prompts, not token counts", today=D)
    ranked = [m.id for m in store.rank(10)]
    assert ranked.index(corr) < ranked.index(plain)
    assert ranked.index(confirmed) < ranked.index(plain)
    assert wrong not in ranked


def test_rank_limit_keeps_working_memory_lean(store):
    for k in range(20):
        store.add(f"m{k}", "fact", 0.5, 0.5, "chat", today=D)
    assert len(store.rank(5)) == 5


def test_due_for_check_and_verify(store):
    i = store.add("a", "fact", 0.5, 0.5, "chat", today=D, check_by=date(2026, 11, 10))
    assert store.due_for_check(date(2026, 11, 9)) == []
    assert [m.id for m in store.due_for_check(date(2026, 11, 10))] == [i]
    m = store.verify(i, date(2026, 11, 10), days=7)
    assert (m.last_verified, m.check_by, m.confirmations) == (date(2026, 11, 10), date(2026, 11, 17), 1)
    assert store.due_for_check(date(2026, 11, 10)) == []


def test_retire_keeps_the_scar(store):
    old = store.add("the update broke it", "fact", 0.6, 0.7, "inferred", today=D)
    new = store.retire(old, "it was the date, not the update", today=D)
    o, n = store.get(old), store.get(new)
    assert o.status == "retired" and o.corrected_by == new and o.text == "the update broke it"
    assert n.status == "active" and n.kind == "correction" and n.provenance == "correction"
    assert n.importance >= o.importance
    with pytest.raises(ValueError):
        store.retire(old, "again")


def test_archive_hides_but_keeps(store):
    i = store.add("old intention", "intention", 0.5, 0.5, "chat", today=D, check_by=D)
    store.archive(i)
    assert store.get(i).status == "archived"
    assert store.rank() == [] and store.due_for_check(D) == []


def test_database_refuses_delete(store):
    i = store.add("x", "fact", 0.5, 0.5, "chat", today=D)
    with pytest.raises(sqlite3.DatabaseError, match="never deleted"):
        store.db.execute("DELETE FROM memories WHERE id = ?", (i,))
    assert store.get(i).text == "x"
    assert not hasattr(store, "delete")


def test_persists_to_file(tmp_path):
    p = str(tmp_path / "maia.db")
    i = MemoryStore(p).add("kept", "fact", 0.5, 0.5, "commit", "abc123", today=D)
    assert MemoryStore(p).get(i).ref == "abc123"
