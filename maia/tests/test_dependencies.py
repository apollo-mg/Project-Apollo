"""Truth maintenance: retiring a memory flags what rests on it.

Shaped on the failure types in "We Taught AI to Answer Questions. Who Taught It to Change Its Mind?" (Towards Data
Science, 2026-10-31): stale (a dependent that should be revisited is not), collateral (an unrelated memory is touched),
and order dependence. Plus the cases a dependency graph adds: shared roots, several supports, cycles.
"""
import random
import sqlite3
from datetime import date

import pytest

from maia.memory import REVIEW_FACTOR, MemoryStore

D = date(2026, 11, 2)


@pytest.fixture
def store():
    return MemoryStore()


def fact(store, text, depends_on=(), importance=0.6, trust=0.8):
    return store.add(text, "fact", importance, trust, "inferred", today=D, depends_on=depends_on)


def flagged(store):
    return {m.id for m in store.needs_review()}


def test_the_weekend(store):
    """The case that motivated this: one wrong memory, four conclusions built on it."""
    wrong = fact(store, "a system update changed the outputs")
    receipt = fact(store, "receipt: outputs drifted after the update", [wrong])
    index = fact(store, "INDEX row: update-induced drift", [receipt])
    roadmap = fact(store, "ROADMAP: pin the system image", [receipt])
    rollback = fact(store, "rollback plan for the update", [wrong])
    corr = store.retire(wrong, "it was a date in the prompt", today=D)
    assert flagged(store) == {receipt, index, roadmap, rollback}
    assert corr not in flagged(store)
    (r,) = store.get(index).review_reasons
    assert r.retired_id == wrong and r.path == (wrong, receipt, index) and r.flagged == D
    # Flag, never edit or retire: text, status and trust are untouched.
    m = store.get(index)
    assert (m.text, m.status, m.trust) == ("INDEX row: update-induced drift", "active", 0.8)


def test_stale_five_levels_down(store):
    chain = [fact(store, "root")]
    for k in range(5):
        chain.append(fact(store, f"level {k + 1}", [chain[-1]]))
    store.retire(chain[0], "root was wrong", today=D)
    assert flagged(store) == set(chain[1:])
    assert store.get(chain[5]).review_reasons[0].path == tuple(chain)
    assert store.dependents(chain[0]) == chain[1:]
    assert store.dependents(chain[0], transitive=False) == [chain[1]]


def test_collateral_unrelated_branch_untouched(store):
    root = fact(store, "root")
    a = fact(store, "a", [root])
    a2 = fact(store, "a2", [a])
    other = fact(store, "other root")
    b = fact(store, "b", [other])
    b2 = fact(store, "b2", [b])
    before = {i: store.get(i) for i in (other, b, b2)}
    store.retire(root, "root was wrong", today=D)
    assert flagged(store) == {a, a2}
    assert {i: store.get(i) for i in (other, b, b2)} == before


def test_shared_dependency_flags_both_branches(store):
    root = fact(store, "root")
    left = fact(store, "left", [root])
    left2 = fact(store, "left2", [left])
    right = fact(store, "right", [root])
    right2 = fact(store, "right2", [right])
    store.retire(root, "wrong", today=D)
    assert flagged(store) == {left, left2, right, right2}


def test_multi_support_flagged_once_with_both_reasons(store):
    a, b = fact(store, "a"), fact(store, "b")
    c = fact(store, "c", [a, b])
    store.retire(a, "a was wrong", today=D)
    store.retire(b, "b was wrong", today=D)
    assert [m.id for m in store.needs_review()] == [c]
    assert [(r.retired_id, r.path) for r in store.get(c).review_reasons] == [(a, (a, c)), (b, (b, c))]


def test_diamond_one_reason_per_root(store):
    root = fact(store, "root")
    x, y = fact(store, "x", [root]), fact(store, "y", [root])
    z = fact(store, "z", [y, x])
    store.retire(root, "wrong", today=D)
    (r,) = store.get(z).review_reasons
    assert r.path == (root, x, z)  # shortest path, ties broken by id: deterministic however it was built


def random_graph(rng, n=12, p=0.2):
    """Edges (child, parent) with child > parent plus a few back edges, so some graphs carry cycles."""
    edges = [(c, q) for c in range(n) for q in range(c) if rng.random() < p]
    edges += [(q, c) for c in range(n) for q in range(c) if rng.random() < p / 4]
    return n, edges


def build(n, edges, rng):
    s = MemoryStore()
    ids = [s.add(f"m{k}", "fact", 0.5, 0.5, "inferred", today=D) for k in range(n)]
    order = edges[:]
    rng.shuffle(order)
    for c, q in order:
        s.link(ids[c], ids[q], today=D)
    return s, ids


@pytest.mark.parametrize("seed", range(25))
def test_order_invariance(seed):
    rng = random.Random(seed)
    n, edges = random_graph(rng)
    to_retire = rng.sample(range(n), 3)
    results = set()
    for trial in range(5):
        trial_rng = random.Random(seed * 100 + trial)
        s, ids = build(n, edges, trial_rng)
        order = to_retire[:]
        trial_rng.shuffle(order)
        for k in order:
            s.retire(ids[k], f"m{k} wrong", today=D)
        results.add(frozenset((ids.index(m.id), tuple(r.retired_id for r in m.review_reasons))
                              for m in s.needs_review()))
    assert len(results) == 1


def test_link_after_retirement_flags_like_before(store):
    """Linking onto something that already rests on a retired memory flags at once: order of link and retire is moot."""
    root = fact(store, "root")
    mid = fact(store, "mid", [root])
    store.retire(root, "wrong", today=D)
    late = fact(store, "late", [mid])
    assert flagged(store) == {mid, late}
    assert store.get(late).review_reasons[0].path == (root, mid, late)


def test_cycles_terminate(store):
    a, b, c = fact(store, "a"), fact(store, "b"), fact(store, "c")
    store.link(a, b), store.link(b, c), store.link(c, a)
    assert store.dependents(a) == [b, c]  # never itself
    store.retire(a, "wrong", today=D)
    assert flagged(store) == {b, c}
    with pytest.raises(ValueError):
        store.link(a, a)


def test_flagged_ranks_lower_and_never_above_equal(store):
    root = fact(store, "root", importance=0.1, trust=0.1)
    hit = fact(store, "rests on root", [root], importance=0.8, trust=0.8)
    peer = fact(store, "same score, unrelated", importance=0.8, trust=0.8)
    store.retire(root, "wrong", today=D)
    m = store.get(hit)
    assert m.score == pytest.approx(0.8 * 0.8 * REVIEW_FACTOR)
    ranked = [x.id for x in store.rank(10)]
    assert ranked.index(peer) < ranked.index(hit)


def test_flagged_loses_ties_even_at_zero(store):
    root = fact(store, "root")
    hit = store.add("zero", "fact", 0.0, 0.5, "inferred", today=D, depends_on=[root])
    peer = store.add("zero too", "fact", 0.0, 0.5, "inferred", today=D)
    store.retire(root, "wrong", today=D)
    ranked = [x.id for x in store.rank(10)]
    assert hit < peer and ranked.index(peer) < ranked.index(hit)


def test_clear_review_counts_as_confirmation(store):
    root = fact(store, "root")
    dep = fact(store, "holds on other grounds", [root])
    store.retire(root, "wrong", today=D)
    m = store.clear_review(dep, date(2026, 11, 5))
    assert not m.needs_review and m.confirmations == 1 and m.last_verified == date(2026, 11, 5)
    assert flagged(store) == set()
    with pytest.raises(ValueError):
        store.clear_review(dep, D)
    # The reason is closed, not deleted.
    row = store.db.execute("SELECT resolved, resolution FROM reviews WHERE mem_id = ?", (dep,)).fetchone()
    assert tuple(row) == ("2026-11-05", "verified")


def test_retiring_a_flagged_memory_resolves_it_and_propagates(store):
    root = fact(store, "root")
    mid = fact(store, "mid", [root])
    leaf = fact(store, "leaf", [mid])
    store.retire(root, "wrong", today=D)
    store.retire(mid, "mid wrong too", today=D)
    assert flagged(store) == {leaf}
    assert {r.retired_id for r in store.get(leaf).review_reasons} == {root, mid}
    assert store.get(mid).review_reasons == ()


def test_archived_and_retired_are_not_flagged_but_carry_the_walk(store):
    root = fact(store, "root")
    arch = fact(store, "archived", [root])
    leaf = fact(store, "leaf", [arch])
    store.archive(arch)
    store.retire(root, "wrong", today=D)
    assert flagged(store) == {leaf}


def test_nothing_deleted(store):
    a = fact(store, "a")
    b = fact(store, "b", [a])
    store.retire(a, "wrong", today=D)
    with pytest.raises(sqlite3.DatabaseError, match="never deleted"):
        store.db.execute("DELETE FROM dependencies")
    with pytest.raises(sqlite3.DatabaseError, match="never deleted"):
        store.db.execute("DELETE FROM reviews")
    assert store.supports(b) == [a]


def test_add_rejects_unknown_support_before_writing(store):
    with pytest.raises(KeyError):
        fact(store, "x", [999])
    assert store.db.execute("SELECT COUNT(*) FROM memories").fetchone()[0] == 0


def test_existing_db_gains_tables(tmp_path):
    p = str(tmp_path / "maia.db")
    con = sqlite3.connect(p)
    from maia.memory import SCHEMA
    con.executescript(SCHEMA.split("-- mem_id rests on on_id.")[0])  # a store from before dependencies existed
    con.close()
    s = MemoryStore(p)
    a = s.add("a", "fact", 0.5, 0.5, "chat", today=D)
    s.add("b", "fact", 0.5, 0.5, "chat", today=D, depends_on=[a])
    s.retire(a, "wrong", today=D)
    assert len(MemoryStore(p).needs_review()) == 1
