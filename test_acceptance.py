"""Tests that the acceptance rule turns luck away and lets a real edge through. Run:

    python test_acceptance.py

They use made-up returns, so no download is needed.
"""

import numpy as np
import pandas as pd

from acceptance import compare, judge, required_ratio, sharpe_of
from backtest import run_backtest, summarize
from test_backtest import random_prices

FAST = dict(resamples=400)        # fewer reshuffles keeps the tests quick


def noise_returns(seed, days=2000, daily_mean=0.001):
    index = pd.date_range("2018-01-01", periods=days, freq="D")
    returns = np.random.default_rng(seed).normal(daily_mean, 0.03, days)
    return pd.Series(returns, index=index)


def test_the_bar_rises_with_the_number_of_experiments():
    assert np.isclose(required_ratio(1), 1.645, atol=0.001)
    assert required_ratio(1) < required_ratio(5) < required_ratio(100) < required_ratio(10000)
    assert np.isclose(required_ratio(100), 3.29, atol=0.01)


def test_sharpe_matches_the_backtester():
    prices = random_prices()
    result = run_backtest(prices, pd.Series(1.0, index=prices.index))
    assert np.isclose(sharpe_of(result["return"].to_numpy())[0], summarize(result)["sharpe"])


def test_a_copy_of_the_baseline_is_rejected():
    baseline = noise_returns(1)
    verdict = judge(baseline.copy(), {"baseline": baseline}, trials=1, **FAST)
    assert verdict["accepted"] is False
    assert verdict["comparisons"]["baseline"]["lead"] == 0.0


def test_luck_alone_rarely_gets_accepted():
    # 200 pairs of strategies with exactly the same true quality. Any lead
    # one has over the other is luck. At most about 5% should be accepted.
    accepted = 0
    for seed in range(200):
        candidate = noise_returns(1000 + seed, days=1000)
        baseline = noise_returns(5000 + seed, days=1000)
        accepted += judge(candidate, {"baseline": baseline}, trials=1,
                          resamples=200, seed=seed)["accepted"]
    assert accepted <= 20, f"{accepted} of 200 lucky strategies were accepted"


def test_luck_gets_through_even_less_often_after_many_experiments():
    accepted = 0
    for seed in range(200):
        candidate = noise_returns(1000 + seed, days=1000)
        baseline = noise_returns(5000 + seed, days=1000)
        accepted += judge(candidate, {"baseline": baseline}, trials=50,
                          resamples=200, seed=seed)["accepted"]
    assert accepted <= 2, f"{accepted} of 200 lucky strategies were accepted"


def test_a_large_real_edge_is_accepted_even_after_many_experiments():
    baseline = noise_returns(2)
    candidate = baseline + 0.004          # the same days, plus a steady 0.4% a day
    assert judge(candidate, {"baseline": baseline}, trials=1, **FAST)["accepted"] is True
    assert judge(candidate, {"baseline": baseline}, trials=1000, **FAST)["accepted"] is True


def test_a_result_that_passes_early_fails_once_enough_ideas_have_been_tried():
    baseline = noise_returns(3)
    candidate = noise_returns(4, daily_mean=0.0033)       # truly better, but only somewhat
    early = judge(candidate, {"baseline": baseline}, trials=1, **FAST)
    late = judge(candidate, {"baseline": baseline}, trials=1000, **FAST)
    ratio = early["comparisons"]["baseline"]["ratio"]
    assert early["required"] < ratio < late["required"]
    assert early["accepted"] is True
    assert late["accepted"] is False


def test_the_candidate_must_beat_every_baseline():
    weak = noise_returns(5)
    strong = weak + 0.004
    candidate = weak + 0.002              # clearly better than weak, clearly worse than strong
    assert judge(candidate, {"weak": weak}, trials=1, **FAST)["accepted"] is True
    verdict = judge(candidate, {"weak": weak, "strong": strong}, trials=1, **FAST)
    assert verdict["accepted"] is False
    assert verdict["comparisons"]["strong"]["lead"] < 0


def test_less_history_means_more_noise():
    candidate, baseline = noise_returns(6), noise_returns(7)
    long_history = compare(candidate, baseline, **FAST)["noise"]
    short_history = compare(candidate.iloc[:300], baseline.iloc[:300], **FAST)["noise"]
    assert short_history > 1.5 * long_history


def test_the_same_inputs_always_give_the_same_verdict():
    candidate, baseline = noise_returns(8), noise_returns(9)
    assert compare(candidate, baseline, **FAST) == compare(candidate, baseline, **FAST)


def test_different_days_are_an_error():
    candidate, baseline = noise_returns(10), noise_returns(11)
    try:
        compare(candidate.iloc[1:], baseline.iloc[:-1], **FAST)
    except ValueError:
        return
    raise AssertionError("returns over different days were compared")


def test_a_strategy_that_never_trades_is_rejected_not_a_crash():
    baseline = noise_returns(12)
    in_cash = pd.Series(0.0, index=baseline.index)
    verdict = judge(in_cash, {"baseline": baseline}, trials=1, **FAST)
    assert verdict["accepted"] is False


if __name__ == "__main__":
    tests = [(name, item) for name, item in sorted(globals().items())
             if name.startswith("test_") and callable(item)]
    for name, test in tests:
        test()
        print(f"ok  {name}")
    print(f"\nAll {len(tests)} tests passed.")
