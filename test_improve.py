"""Tests for the improvement loop and the strategies it has tried. Run:

    python test_improve.py

They use made-up prices and a throwaway log, so nothing real is touched.
"""

import os
import tempfile

import numpy as np
import pandas as pd

import backtest
from improve import check_proposals, find_peeking, run_loop
from proposals import PROPOSALS
from strategies import trend_blend, trend_buffer, trend_filter, vol_target
from test_backtest import make_prices, random_prices

REASON = "A long enough made-up reason, because every proposal must have one."


def proposal(name, strategy, grid=None, hypothesis=REASON):
    return {"name": name, "hypothesis": hypothesis, "strategy": strategy,
            "grid": grid or [{}], "warmup": 0}


def swinging_prices(days=2500, seed=5):
    """Prices that rise steadily for 100 days, then fall for 100, over and over."""
    rng = np.random.default_rng(seed)
    drift = np.where((np.arange(days) // 100) % 2 == 0, 0.008, -0.008)
    return make_prices(100 * np.exp(np.cumsum(drift + rng.normal(0, 0.01, days))), start="2015-01-01")


def follow_recent_move(prices, lookback=10):
    """Honest: hold if the price is higher than it was `lookback` days ago."""
    return (prices["close"] > prices["close"].shift(lookback)).astype(float)


def knows_tomorrow(prices):
    """Cheat: hold today if tomorrow's price is higher."""
    return (prices["close"].shift(-1) > prices["close"]).astype(float)


def knows_the_whole_history(prices):
    """Cheat: hold when the price is below its average over ALL days, future included."""
    return (prices["close"] < prices["close"].mean()).astype(float)


def smooths_across_today(prices):
    """Cheat: an average centred on today uses the days after it."""
    return (prices["close"] > prices["close"].rolling(21, center=True).mean()).astype(float)


def temporary_log():
    folder = tempfile.TemporaryDirectory()
    return folder, os.path.join(folder.name, "log.jsonl")


# --- The cheating check -----------------------------------------------------

def test_every_real_proposal_passes_the_cheating_check():
    prices = random_prices(days=900)
    for item in PROPOSALS:
        assert find_peeking(item["strategy"], item["grid"], prices) is None, item["name"]


def test_three_kinds_of_cheating_are_caught():
    prices = random_prices(days=900)
    for cheat in (knows_tomorrow, knows_the_whole_history, smooths_across_today):
        assert find_peeking(cheat, [{}], prices) is not None, cheat.__name__


def test_a_strategy_that_crashes_is_reported_not_raised():
    def broken(prices):
        raise RuntimeError("oops")
    assert "failed to run" in find_peeking(broken, [{}], random_prices(days=300))


def test_a_cheating_proposal_is_refused_and_not_logged():
    folder, log = temporary_log()
    state = run_loop(swinging_prices(), [proposal("cheat", knows_tomorrow)], log_path=log)
    assert "cheat" in state["refused"]
    assert "cheat" not in state["tested"]
    assert backtest.count_experiments(log) == 0
    folder.cleanup()


# --- The proposal rules -----------------------------------------------------

def test_a_proposal_without_a_reason_is_an_error():
    for bad in ("", "it works", None):
        try:
            check_proposals([proposal("idea", follow_recent_move, hypothesis=bad)])
        except ValueError:
            continue
        raise AssertionError(f"a proposal with the reason {bad!r} was allowed")


def test_duplicate_and_baseline_names_are_errors():
    twice = [proposal("idea", follow_recent_move), proposal("idea", follow_recent_move)]
    for bad in (twice, [proposal("buy_and_hold", follow_recent_move)]):
        try:
            check_proposals(bad)
        except ValueError:
            continue
        raise AssertionError("a bad proposal name was allowed")


def test_the_real_proposal_list_follows_the_rules():
    check_proposals(PROPOSALS)


# --- The loop ---------------------------------------------------------------

def test_each_proposal_is_logged_once_however_often_the_loop_runs():
    folder, log = temporary_log()
    ideas = [proposal("fast", follow_recent_move, [{"lookback": 5}, {"lookback": 10}]),
             proposal("slow", follow_recent_move, [{"lookback": 40}])]
    first = run_loop(swinging_prices(), ideas, log_path=log)
    assert [entry["is_new"] for entry in first["tested"].values()] == [True, True]
    assert first["trials"] == 2

    second = run_loop(swinging_prices(), ideas, log_path=log)
    assert [entry["is_new"] for entry in second["tested"].values()] == [False, False]
    assert second["trials"] == 2
    folder.cleanup()


def test_a_real_edge_is_accepted_and_becomes_champion():
    folder, log = temporary_log()
    state = run_loop(swinging_prices(), [proposal("fast", follow_recent_move, [{"lookback": 10}])],
                     log_path=log)
    assert state["tested"]["fast"]["verdict"]["accepted"] is True
    assert state["champion"] == "fast"
    folder.cleanup()


def test_no_edge_means_no_champion():
    # Prices with no pattern: following recent moves cannot help.
    rng = np.random.default_rng(21)
    prices = make_prices(100 * np.exp(np.cumsum(rng.normal(0, 0.03, 2500))), start="2015-01-01")
    folder, log = temporary_log()
    state = run_loop(prices, [proposal("fast", follow_recent_move, [{"lookback": 10}])], log_path=log)
    assert state["tested"]["fast"]["verdict"]["accepted"] is False
    assert state["champion"] is None
    folder.cleanup()


def test_the_champion_is_the_best_of_the_accepted_ideas():
    folder, log = temporary_log()
    ideas = [proposal("slower", follow_recent_move, [{"lookback": 30}]),
             proposal("faster", follow_recent_move, [{"lookback": 10}])]
    state = run_loop(swinging_prices(), ideas, log_path=log)
    accepted = [name for name, entry in state["tested"].items() if entry["verdict"]["accepted"]]
    assert accepted == ["slower", "faster"]
    best = max(accepted, key=lambda name: state["tested"][name]["metrics"]["sharpe"])
    assert state["champion"] == best
    folder.cleanup()


def test_the_bar_counts_every_experiment_in_the_log():
    folder, log = temporary_log()
    for number in range(50):
        backtest.log_experiment(f"earlier idea {number}", {}, "why", {}, path=log)
    state = run_loop(swinging_prices(), [proposal("fast", follow_recent_move)], log_path=log)
    assert state["trials"] == 51
    assert state["required"] > 3.0
    folder.cleanup()


# --- The strategies the loop has tried --------------------------------------

def test_trend_buffer_with_no_band_is_the_plain_trend_filter():
    prices = random_prices()
    pd.testing.assert_series_equal(trend_buffer(prices, window=100, band=0.0),
                                   trend_filter(prices, window=100), check_names=False)


def test_trend_buffer_trades_less_than_the_plain_trend_filter():
    prices = random_prices()
    plain = trend_filter(prices, window=100).diff().abs().sum()
    buffered = trend_buffer(prices, window=100, band=0.06).diff().abs().sum()
    assert 0 < buffered < plain


def test_vol_target_holds_less_when_prices_swing_more():
    rng = np.random.default_rng(2)
    calm = rng.normal(0, 0.01, 300)             # about 19% a year
    wild = rng.normal(0, 0.06, 300)             # about 115% a year
    prices = make_prices(100 * np.exp(np.cumsum(np.concatenate([calm, wild]))))
    positions = vol_target(prices, target=0.6, lookback=30)
    assert positions.max() <= 1.0 and positions.min() >= 0.0
    assert positions.iloc[100:300].mean() == 1.0
    assert 0.3 < positions.iloc[400:].mean() < 0.8


def test_vol_target_ignores_small_adjustments():
    positions = vol_target(random_prices(), target=0.4, lookback=30, step=0.1)
    changes = positions.diff().abs().dropna()
    assert changes[changes > 0].min() >= 0.1 - 1e-12


def test_trend_blend_with_one_length_is_the_plain_trend_filter():
    prices = random_prices()
    pd.testing.assert_series_equal(trend_blend(prices, windows=(100,)),
                                   trend_filter(prices, window=100), check_names=False)


def test_trend_blend_moves_in_steps():
    positions = trend_blend(random_prices(), windows=(20, 50, 100))
    assert set(np.round(positions.unique() * 3).astype(int)) <= {0, 1, 2, 3}
    assert positions.between(0, 1).all()


if __name__ == "__main__":
    tests = [(name, item) for name, item in sorted(globals().items())
             if name.startswith("test_") and callable(item)]
    for name, test in tests:
        test()
        print(f"ok  {name}")
    print(f"\nAll {len(tests)} tests passed.")
