"""Tests that prove the engine is honest. Run:

    python test_backtest.py

They use made-up prices, so no download is needed.
"""

import os
import tempfile

import numpy as np
import pandas as pd

import backtest
import config
from backtest import run_backtest, split_research_holdout, summarize
from fetch_data import rows_to_frame
from strategies import buy_and_hold, ma_crossover, trend_filter


def make_prices(closes, start="2024-01-01"):
    index = pd.date_range(start, periods=len(closes), freq="D", name="date")
    return pd.DataFrame({"close": np.array(closes, dtype=float)}, index=index)


def random_prices(days=600, seed=1):
    rng = np.random.default_rng(seed)
    return make_prices(100 * np.exp(np.cumsum(rng.normal(0.001, 0.03, days))))


def test_staying_in_cash_earns_nothing():
    prices = random_prices()
    result = run_backtest(prices, pd.Series(0.0, index=prices.index))
    assert (result["equity"] == 1.0).all()
    assert summarize(result)["trades"] == 0


def test_buy_and_hold_without_costs_matches_the_price():
    prices = random_prices()
    result = run_backtest(prices, buy_and_hold(prices), fee=0, slippage=0)
    expected = prices["close"].iloc[-1] / prices["close"].iloc[0]
    assert np.isclose(result["equity"].iloc[-1], expected)


def test_costs_are_charged_once_for_one_trade():
    prices = random_prices()
    result = run_backtest(prices, buy_and_hold(prices), fee=0.004, slippage=0.0005)
    expected = (1 - 0.0045) * prices["close"].iloc[-1] / prices["close"].iloc[0]
    assert np.isclose(result["equity"].iloc[-1], expected)
    assert summarize(result)["trades"] == 1


def test_every_trade_costs_money():
    prices = make_prices([100.0] * 11)           # price never moves
    flip = pd.Series([1.0, 0.0] * 5 + [1.0], index=prices.index)
    result = run_backtest(prices, flip, fee=0.01, slippage=0)
    trades = summarize(result)["trades"]
    assert trades == 10
    assert np.isclose(result["equity"].iloc[-1], 0.99 ** trades)


def test_a_signal_cannot_earn_the_move_of_its_own_day():
    # Price goes up, down, up, down... A cheat that is "in" on exactly the up
    # days would win every day if it could trade on information from that day.
    prices = make_prices([100, 110] * 20)
    up_today = (prices["close"].pct_change() > 0).astype(float)
    result = run_backtest(prices, up_today, fee=0, slippage=0)
    # In the engine it buys at the close of each up day and so only ever
    # holds through the down days.
    assert result["equity"].iloc[-1] < 1.0
    assert (result["return"] <= 0).all()


def test_changing_the_future_does_not_change_the_past():
    prices = random_prices()
    altered = prices.copy()
    altered.iloc[400:] *= 3.0
    for strategy in (buy_and_hold, trend_filter, ma_crossover):
        before = run_backtest(prices, strategy(prices))
        after = run_backtest(altered, strategy(altered))
        pd.testing.assert_series_equal(before["equity"].iloc[:400], after["equity"].iloc[:400])


def test_strategies_only_use_prices_up_to_today():
    prices = random_prices()
    for strategy in (buy_and_hold, trend_filter, ma_crossover):
        full = strategy(prices)
        for cut in (250, 400, 599):
            partial = strategy(prices.iloc[:cut])
            pd.testing.assert_series_equal(full.iloc[:cut], partial)


def test_trend_strategies_stay_out_until_they_have_enough_history():
    prices = random_prices()
    assert (trend_filter(prices, window=200).iloc[:199] == 0).all()
    assert (ma_crossover(prices, fast=50, slow=200).iloc[:199] == 0).all()


def test_max_drawdown_is_measured_from_the_peak():
    prices = make_prices([100, 200, 100, 150])
    result = run_backtest(prices, buy_and_hold(prices), fee=0, slippage=0)
    assert np.isclose(summarize(result)["max_drawdown"], -0.5)


def test_research_data_stops_before_the_holdout():
    prices = make_prices(range(1, 101), start="2024-11-01")
    research, holdout = split_research_holdout(prices, "2025-01-01")
    assert research.index.max() == pd.Timestamp("2024-12-31")
    assert holdout.index.min() == pd.Timestamp("2025-01-01")
    assert len(research) + len(holdout) == len(prices)


def test_holdout_is_locked_unless_asked_for_on_purpose():
    try:
        backtest.load_holdout_data()
    except PermissionError:
        return
    raise AssertionError("the holdout opened without the explicit flag")


def test_experiment_log_counts_every_run():
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "log.jsonl")
        assert backtest.count_experiments(path) == 0
        backtest.log_experiment("a", {"x": 1}, "why", {"sharpe": 1.0}, path=path)
        backtest.log_experiment("b", {"x": 2}, "why", {"sharpe": 0.5}, path=path)
        assert backtest.count_experiments(path) == 2


def test_coinbase_rows_are_sorted_and_todays_candle_is_dropped():
    day = 86400
    start = int(pd.Timestamp("2024-01-01", tz="UTC").timestamp())
    # Coinbase's order: [time, low, high, open, close, volume], newest first.
    rows = [[start + 2 * day, 1, 4, 2, 3, 10],      # "today", still changing
            [start + day, 1, 4, 2, 3.5, 10],
            [start, 1, 4, 2, 3, 10],
            [start, 1, 4, 2, 3, 10]]                # duplicate
    now = pd.Timestamp("2024-01-03 12:00", tz="UTC").to_pydatetime()
    frame = rows_to_frame(rows, now=now)
    assert list(frame.index) == [pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")]
    assert list(frame["close"]) == [3.0, 3.5]
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]


if __name__ == "__main__":
    tests = [(name, item) for name, item in sorted(globals().items())
             if name.startswith("test_") and callable(item)]
    for name, test in tests:
        test()
        print(f"ok  {name}")
    print(f"\nAll {len(tests)} tests passed.")
