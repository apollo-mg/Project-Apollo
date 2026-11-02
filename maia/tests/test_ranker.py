import itertools

import pytest

from maia.ranker import ASK, CONCEDE, EVIDENCE, HOLD, decide

GROUNDED = ["receipt", "commit", "correction"]
CONF = [0.0, 0.2, 0.49, 0.5, 0.8, 1.0]
COST = [0.0, 0.3, 0.7, 1.0]
ALL = list(itertools.product(EVIDENCE, [False, True], CONF, COST))


@pytest.mark.parametrize("evidence,conf,cost", list(itertools.product(GROUNDED, CONF, COST)))
def test_pressure_never_concedes_a_grounded_claim(evidence, conf, cost):
    assert decide(evidence, new_evidence=False, confidence=conf, cost_of_wrong=cost).action == HOLD


@pytest.mark.parametrize("evidence,conf,cost", list(itertools.product(EVIDENCE, CONF, COST)))
def test_new_evidence_always_reconsiders(evidence, conf, cost):
    assert decide(evidence, new_evidence=True, confidence=conf, cost_of_wrong=cost).action in (CONCEDE, ASK)


@pytest.mark.parametrize("conf,cost", list(itertools.product([0.0, 0.2, 0.49], COST)))
def test_low_confidence_inference_concedes_on_first_pushback(conf, cost):
    assert decide("inferred", new_evidence=False, confidence=conf, cost_of_wrong=cost).action == CONCEDE


@pytest.mark.parametrize("evidence,new,conf", list(itertools.product(EVIDENCE, [False, True], CONF)))
def test_cost_sets_firmness_never_the_action(evidence, new, conf):
    stances = [decide(evidence, new, conf, c) for c in COST]
    assert len({s.action for s in stances}) == 1
    if stances[0].action != CONCEDE:
        firmness = [s.firmness for s in stances]
        assert firmness == sorted(firmness) and firmness[0] < firmness[-1]


@pytest.mark.parametrize("evidence,new,conf,cost,expected", [
    ("receipt", False, 0.9, 0.9, HOLD),
    ("receipt", True, 0.9, 0.9, ASK),
    ("receipt", True, 0.2, 0.9, CONCEDE),
    ("inferred", False, 0.9, 0.1, ASK),
    ("inferred", True, 0.9, 1.0, CONCEDE),
])
def test_table(evidence, new, conf, cost, expected):
    assert decide(evidence, new, conf, cost).action == expected


def test_concede_has_no_firmness():
    assert all(s.firmness == 0 for s in (decide(*a) for a in ALL) if s.action == CONCEDE)


@pytest.mark.parametrize("args", [("hunch", False, 0.5, 0.5), ("receipt", False, 1.2, 0.5), ("receipt", False, 0.5, -1)])
def test_rejects_bad_inputs(args):
    with pytest.raises(ValueError):
        decide(*args)
