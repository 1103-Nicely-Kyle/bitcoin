"""Tests that walk-forward never lets a choice see the days it is scored on. Run:

    python test_walk_forward.py

They use made-up prices, so no download is needed.
"""

import os
import tempfile

import numpy as np
import pandas as pd

import backtest
from backtest import run_backtest, summarize
from strategies import ma_crossover, trend_filter
from test_backtest import make_prices, random_prices
from walk_forward import score_fixed, walk_forward

TREND_GRID = [{"window": window} for window in (20, 50, 100)]
SETTINGS = dict(min_train_days=300, test_days=100)


def test_test_periods_follow_each_other_with_no_gaps_or_overlap():
    prices = random_prices(days=750)
    result, folds = walk_forward(prices, trend_filter, TREND_GRID, **SETTINGS)
    assert folds["test_start"].iloc[0] == prices.index[300]
    assert folds["test_end"].iloc[-1] == prices.index[-1]
    for previous_end, next_start in zip(folds["test_end"], folds["test_start"].iloc[1:]):
        assert next_start == previous_end + pd.Timedelta(days=1)
    assert len(folds) == 5                       # 100, 100, 100, 100 and a last 50
    assert result.index.equals(prices.index[300:])


def test_changing_later_prices_does_not_change_earlier_choices_or_results():
    prices = random_prices(days=750)
    altered = prices.copy()
    altered.iloc[500:] *= np.linspace(1, 5, 250)[:, None]

    result, folds = walk_forward(prices, trend_filter, TREND_GRID, **SETTINGS)
    altered_result, altered_folds = walk_forward(altered, trend_filter, TREND_GRID, **SETTINGS)

    # Periods starting at days 300, 400 and 500 were all chosen from prices
    # before day 500, so those choices must be identical.
    assert list(folds["params"].iloc[:3]) == list(altered_folds["params"].iloc[:3])
    assert list(folds["train_score"].iloc[:3]) == list(altered_folds["train_score"].iloc[:3])
    cutoff = prices.index[499]
    pd.testing.assert_series_equal(result["equity"].loc[:cutoff],
                                   altered_result["equity"].loc[:cutoff])


def test_the_setting_chosen_is_the_best_one_on_the_training_days():
    prices = random_prices(days=750, seed=3)
    _, folds = walk_forward(prices, trend_filter, TREND_GRID, **SETTINGS)
    for _, fold in folds.iterrows():
        train = prices[prices.index < fold["test_start"]]
        scores = [summarize(run_backtest(train, trend_filter(train, **params)))["sharpe"]
                  for params in TREND_GRID]
        assert np.isclose(fold["train_score"], max(scores))
        assert fold["params"] == TREND_GRID[int(np.argmax(scores))]


def test_with_one_setting_walk_forward_equals_a_plain_backtest():
    prices = random_prices(days=750)
    params = {"fast": 20, "slow": 60}
    result, _ = walk_forward(prices, ma_crossover, [params], **SETTINGS)
    plain = score_fixed(prices, ma_crossover, params, min_train_days=300)
    pd.testing.assert_frame_equal(result, plain)


def test_warmup_days_are_left_out_of_the_training_score():
    prices = random_prices(days=750)
    _, folds = walk_forward(prices, trend_filter, [{"window": 50}], warmup=100, **SETTINGS)
    train = prices.iloc[:300]
    trained = run_backtest(train, trend_filter(train, window=50))
    assert np.isclose(folds["train_score"].iloc[0], summarize(trained.iloc[100:])["sharpe"])


def test_walk_forward_exposes_settings_that_were_fitted_to_noise():
    # Prices with no pattern and no overall rise or fall, and 100 "strategies"
    # that are coin flips. The best coin flip always looks good on the days it
    # was picked from. Walk-forward shows it is worth nothing afterwards.
    moves = np.random.default_rng(11).normal(0, 0.03, 3000)
    prices = make_prices(100 * np.exp(np.cumsum(moves - moves.mean())))
    flips = np.random.default_rng(12).integers(0, 2, size=(100, 3000)).astype(float)

    def coin_flip(prices, which):
        return pd.Series(flips[which, :len(prices)], index=prices.index)

    grid = [{"which": which} for which in range(100)]
    result, folds = walk_forward(prices, coin_flip, grid, min_train_days=500,
                                 test_days=250, fee=0, slippage=0)
    looked_like = folds["train_score"].mean()
    turned_out = summarize(result)["sharpe"]
    assert looked_like > 0.7      # a "good" strategy, judged on the days it was picked from
    assert turned_out < 0.3       # nothing, judged on the days after


def test_too_little_data_is_an_error_not_a_silent_empty_result():
    prices = random_prices(days=200)
    try:
        walk_forward(prices, trend_filter, TREND_GRID, **SETTINGS)
    except ValueError:
        return
    raise AssertionError("walk-forward ran without enough data")


def test_summary_of_a_slice_only_reflects_that_slice():
    prices = make_prices([100, 200, 100, 150, 300])
    result = run_backtest(prices, pd.Series(1.0, index=prices.index), fee=0, slippage=0)
    last_two_days = summarize(result.iloc[3:])
    assert np.isclose(last_two_days["total_return"], 2.0)      # 100 -> 300
    assert np.isclose(last_two_days["max_drawdown"], 0.0)


def test_the_same_run_is_only_logged_once():
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "log.jsonl")
        assert backtest.log_experiment("a", {"x": 1}, "why", {"sharpe": 1.0}, path=path) is True
        assert backtest.log_experiment("a", {"x": 1}, "why", {"sharpe": 1.0}, path=path) is False
        assert backtest.log_experiment("a", {"x": 2}, "why", {"sharpe": 1.0}, path=path) is True
        assert backtest.count_experiments(path) == 2


if __name__ == "__main__":
    tests = [(name, item) for name, item in sorted(globals().items())
             if name.startswith("test_") and callable(item)]
    for name, test in tests:
        test()
        print(f"ok  {name}")
    print(f"\nAll {len(tests)} tests passed.")
