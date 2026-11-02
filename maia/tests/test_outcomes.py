import pytest

from maia.outcomes import OutcomeLog, beta_cdf, beta_ppf


def feed(log, pattern, useful, useless):
    for _ in range(useful):
        log.log(pattern, True, "acts on it", "acts on it", useful=True)
    for _ in range(useless):
        log.log(pattern, True, "acts on it", "ignores it", useful=False)


@pytest.mark.parametrize("x,a,b,expected", [(0.5, 1, 1, 0.5), (0.3, 1, 1, 0.3), (0.5, 2, 2, 0.5), (0.5, 1, 2, 0.75),
                                            (0.2, 2, 5, 0.34464)])
def test_beta_cdf_known_values(x, a, b, expected):
    assert beta_cdf(x, a, b) == pytest.approx(expected, abs=1e-5)


@pytest.mark.parametrize("a,b", [(1, 1), (3, 7), (40, 2), (0.5, 0.5)])
def test_beta_ppf_inverts_cdf(a, b):
    for q in (0.05, 0.5, 0.95):
        assert beta_cdf(beta_ppf(q, a, b), a, b) == pytest.approx(q, abs=1e-6)


def test_log_and_surprises():
    log = OutcomeLog()
    log.log("stale-intention", True, "answers", "answers", useful=True)
    log.log("stale-intention", False, "would ignore", "asked why she said nothing", useful=True)
    log.log("prior-art", True, "reads the receipt", "reads the receipt", useful=True)
    [s] = log.surprises("stale-intention")
    assert s["interrupted"] == 0 and s["observed"] == "asked why she said nothing"
    assert len(log.surprises()) == 1


def test_unknown_usefulness_does_not_move_the_posterior():
    log = OutcomeLog()
    log.log("p", True, "a", "no reply yet")
    assert log.posterior("p") == (1.0, 1.0)


def test_starts_conservative_with_a_wide_interval():
    d = OutcomeLog(explore=0.0).should_interrupt("new-pattern")
    assert d.interrupt is False and d.reason == "hold" and d.n == 0 and d.high - d.low > 0.8


def test_interrupts_only_when_lower_bound_clears():
    log = OutcomeLog(threshold=0.6, explore=0.0)
    feed(log, "p", 3, 0)  # mean 0.8 but too few to be sure
    d = log.should_interrupt("p")
    assert d.mean > 0.6 and d.low < 0.6 and not d.interrupt
    feed(log, "p", 27, 1)
    d = log.should_interrupt("p")
    assert d.interrupt and d.reason == "confident" and d.low >= 0.6


def test_useless_pattern_never_interrupts_once_narrow():
    log = OutcomeLog(explore=1.0)  # would always explore if the interval were wide
    feed(log, "noise", 2, 60)
    d = log.should_interrupt("noise")
    assert d.high - d.low < log.wide and not d.interrupt


def test_explores_a_little_while_wide_and_is_seedable():
    def run(seed):
        log = OutcomeLog(explore=0.1, seed=seed)
        return [log.should_interrupt("new").reason for _ in range(1000)]
    a = run(7)
    assert a == run(7)
    rate = a.count("explore") / len(a)
    assert 0.07 < rate < 0.13 and set(a) == {"explore", "hold"}
