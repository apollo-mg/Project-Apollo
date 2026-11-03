"""Recurrence matching in tools/daydream_harvest.py: a thread that comes back, reworded, in a later diary must raise the
thread's `mentions` instead of becoming a new thread (2026-11-03: all 136 open action threads had mentions == 1).
Synthetic diary snippets in tmp_path only; the real diaries are private and never in git."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import daydream_harvest as H   # noqa: E402


def diary(root, day, *bullets):
    p = root / "data" / "dev_diaries" / f"{day}_ledger.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"# {day}\n\n## Open items\n\n" + "".join(f"- {b}\n" for b in bullets))
    return p


def run(root, files, state=None, today="2026-11-03", log=None):
    state = state if state is not None else {"threads": {}}
    seen = H.ingest(state, root, files, today, log=log)
    return state, seen


def opens(state):
    return {k: t for k, t in state["threads"].items() if t["status"] == "open"}


NP4_1 = ("The np4 store grew to 1.9 GB after the overnight eviction run; worth watching whether the vector store keeps "
         "growing past the eviction threshold.")
NP4_2 = ("np4 vector store at 1.9 GB again this morning, eviction never shrank it; growing store still not root-caused.")


def test_paraphrase_with_shared_anchor_merges(tmp_path):
    a = diary(tmp_path, "2026-11-01", NP4_1)
    b = diary(tmp_path, "2026-11-02", NP4_2)
    assert H.similar(NP4_1, NP4_2) < 0.7              # not a near-duplicate: only recurrence can join them
    log = []
    state, seen = run(tmp_path, [a, b], log=log)
    assert len(opens(state)) == 1
    t = next(iter(opens(state).values()))
    assert t["mentions"] == 2
    assert [H.src_file(s) for s in t["sources"]] == ["data/dev_diaries/2026-11-01_ledger.md",
                                                     "data/dev_diaries/2026-11-02_ledger.md"]
    assert len(log) == 1 and "1.9gb" in log[0]["anchors"] and log[0]["source"].endswith("2026-11-02_ledger.md:5")


def test_last_seen_updates_and_rerun_is_stable(tmp_path):
    a = diary(tmp_path, "2026-11-01", NP4_1)
    state, _ = run(tmp_path, [a], today="2026-11-01")
    b = diary(tmp_path, "2026-11-02", NP4_2)
    run(tmp_path, [a, b], state, today="2026-11-02")
    run(tmp_path, [a, b], state, today="2026-11-03")   # next night re-harvests the same window
    assert len(state["threads"]) == 1
    t = next(iter(state["threads"].values()))
    assert (t["first_seen"], t["last_seen"], t["mentions"]) == ("2026-11-01", "2026-11-03", 2)


def test_commit_and_filename_anchors(tmp_path):
    a = diary(tmp_path, "2026-11-01", "Daily driver not switched to `1c5e564b` yet: Mark's call after the "
                                      "RESULT_SPEC_DRAFT.md acceptance numbers come in.")
    b = diary(tmp_path, "2026-11-02", "Switching the daily driver to 1c5e564 is still pending the acceptance numbers "
                                      "in RESULT_SPEC_DRAFT.md.")
    state, _ = run(tmp_path, [a, b])
    assert [t["mentions"] for t in opens(state).values()] == [2]


def test_generic_words_only_stay_separate(tmp_path):
    a = diary(tmp_path, "2026-11-01", "Re-test the model run on the P100 with the longer context window; the test "
                                      "run was cut short by the power outage.")
    b = diary(tmp_path, "2026-11-02", "Next test: run the model on the P100 again with thinking enabled, not yet run "
                                      "because the judge prompt is unfinished.")
    log = []
    state, _ = run(tmp_path, [a, b], log=log)
    assert len(opens(state)) == 2 and log == []
    assert all(t["mentions"] == 1 for t in state["threads"].values())


def test_shared_anchor_without_word_overlap_stays_separate(tmp_path):
    a = diary(tmp_path, "2026-11-01", "Qwen3.8-27B tool-call loop on long JSON schemas not yet root-caused; "
                                      "suspect the grammar sampler.")
    b = diary(tmp_path, "2026-11-02", "Qwen3.8-27B download for the abstention ladder pending the sha256 check "
                                      "from the publisher page.")
    state, _ = run(tmp_path, [a, b])
    assert len(opens(state)) == 2


def test_rementions_in_same_file_are_not_new_mentions(tmp_path):
    a = diary(tmp_path, "2026-11-01", NP4_1)
    state, _ = run(tmp_path, [a])
    a.write_text(a.read_text() + "\n## Next steps\n\n- " + NP4_2 + "\n")    # same file, new line, reworded
    run(tmp_path, [a], state)
    assert all(t["mentions"] == 1 for t in state["threads"].values())
    b = diary(tmp_path, "2026-11-02", "\n\n" + NP4_1)                          # verbatim, later file, new line no.
    run(tmp_path, [b], state)
    first = state["threads"][H.hashlib.sha1(NP4_1.encode()).hexdigest()[:10]]
    assert first["mentions"] == 2


def test_closed_thread_not_revived_by_recurrence(tmp_path):
    a = diary(tmp_path, "2026-11-01", NP4_1)
    state, _ = run(tmp_path, [a], today="2026-11-01")
    (old,) = state["threads"]
    state["threads"][old].update(status="closed", closed_on="2026-11-01")
    b = diary(tmp_path, "2026-11-02", NP4_2)
    log = []
    run(tmp_path, [b], state, today="2026-11-02", log=log)
    assert state["threads"][old]["status"] == "closed" and state["threads"][old]["mentions"] == 1
    assert log == [] and len(opens(state)) == 1         # the reworded item is a new thread, not a revival


def test_near_duplicate_still_reopens_closed_thread(tmp_path):
    """harvest's reopen rule is unchanged: a near-duplicate in a NEW file reopens a closed thread."""
    a = diary(tmp_path, "2026-11-01", NP4_1)
    state, _ = run(tmp_path, [a], today="2026-11-01")
    (old,) = state["threads"]
    state["threads"][old].update(status="closed", closed_on="2026-11-01")
    b = diary(tmp_path, "2026-11-02", NP4_1.replace("overnight", "nightly"))
    run(tmp_path, [b], state, today="2026-11-02")
    assert state["threads"][old]["status"] == "open" and state["threads"][old]["mentions"] == 2


def test_near_duplicate_merge_unchanged(tmp_path):
    a = diary(tmp_path, "2026-11-01", NP4_1)
    b = diary(tmp_path, "2026-11-02", NP4_1 + " Still.")
    state, _ = run(tmp_path, [a, b], log=(log := []))
    assert len(state["threads"]) == 1 and log == []     # matched as a near-duplicate, before recurrence is tried


def test_anchor_carried_by_many_open_threads_is_ignored(tmp_path):
    topics = ["temperature scaling", "refusal threshold", "abstention ladder", "judge agreement", "token budget",
              "context sweep"]
    state = {"threads": {f"t{i}": {"text": f"RESULT_CALIB.md: the {w} for the quantised readout is unverified on "
                                           f"held-out items.", "first_seen": "2026-10-01", "last_seen": "2026-10-01",
                                   "mentions": 1, "sources": [f"data/receipts/c/R{i}.md:1"], "why": "",
                                   "status": "open", "kind": "action"}
                         for i, w in enumerate(topics[:H.ANCHOR_MAX_THREADS + 1])}}
    new = "Per RESULT_CALIB.md the temperature scaling readout still drifts on held-out items; not verified."
    assert H.recurrence(state, new, "data/dev_diaries/2026-11-02_ledger.md") is None
    del state["threads"]["t4"]                          # one fewer carrier: the anchor counts again
    r = H.recurrence(state, new, "data/dev_diaries/2026-11-02_ledger.md")
    assert r and r["thread"] == "t0" and r["anchors"] == {"result_calib.md": "file"}


def test_anchors():
    A = H.anchors("np4 at 1.9 GB, commit 1c5e564b, Qwen3.8-27B Q4_K_M, see data/receipts/x/RESULT_X.md and "
                  "`cache_prompt:false`; 16 GB card, 4x P100, 2026-09-28, README.md, Q8_0")
    assert A == {"1.9gb": "number", "1c5e564": "commit", "qwen3.8-27b": "name", "q4_k_m": "name",
                 "result_x.md": "file", "cache_prompt:false": "ident"}


SCOPE_NP4 = "The np4 store measured 1.9 GB after the overnight eviction run, with the vector store growing past the threshold."
SCOPE_NP4_2 = "np4 vector store at 1.9 GB again this morning; eviction never shrank the growing store."


def test_action_item_does_not_join_a_scope_thread(tmp_path):
    """2026-11-02: the nightly question reads action threads only, so an action item absorbed by a scope thread would
    be hidden from it. It stays its own (action) thread."""
    assert not H.ACTION.search(SCOPE_NP4) and H.ACTION.search(NP4_2) and H.similar(SCOPE_NP4, NP4_2) < 0.7
    a = diary(tmp_path, "2026-11-01", SCOPE_NP4)
    b = diary(tmp_path, "2026-11-02", NP4_2)
    state, _ = run(tmp_path, [a, b], log=(log := []))
    assert log == [] and sorted(t["kind"] for t in opens(state).values()) == ["action", "scope"]


def test_scope_item_does_not_raise_an_action_threads_mentions(tmp_path):
    assert H.ACTION.search(NP4_1) and not H.ACTION.search(SCOPE_NP4_2) and H.similar(NP4_1, SCOPE_NP4_2) < 0.7
    a = diary(tmp_path, "2026-11-01", NP4_1)
    b = diary(tmp_path, "2026-11-02", SCOPE_NP4_2)
    state, _ = run(tmp_path, [a, b], log=(log := []))
    assert log == [] and all(t["mentions"] == 1 for t in state["threads"].values())


def test_project_names_are_not_file_anchors():
    assert "llama.cpp" not in H.anchors("Not yet checked against upstream llama.cpp or `whisper.cpp`; see RESULT_X.md")
