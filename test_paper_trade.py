"""Tests for the paper-trading runner and the hard risk limits. Run:

    python test_paper_trade.py

They use made-up prices and a throwaway folder, so nothing real is touched.
"""

import os
import tempfile
from datetime import date

import numpy as np
import pandas as pd

import paper_trade
import risk_limits
from backtest import run_backtest
from fetch_data import merge
from paper_trade import load_account, new_account, process_new_days, resume, save
from strategies import trend_filter
from test_backtest import make_prices

COST = 0.0045


def gentle_prices(days=400, seed=4):
    """Prices that wander without ever moving enough to trip a limit."""
    rng = np.random.default_rng(seed)
    return make_prices(100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, days))))


def always_in(prices):
    return pd.Series(1.0, index=prices.index)


def started_account(prices, strategy=always_in, days_before=1):
    """An account that started `days_before` days before the end of `prices`."""
    account = new_account("test", start_cash=1000)
    process_new_days(account, prices.iloc[:len(prices) - days_before], strategy, {}, cost_per_trade=COST)
    return account


# --- The runner -------------------------------------------------------------

def test_a_new_account_starts_on_the_newest_day_and_never_trades_the_past():
    prices = gentle_prices()
    account = new_account("test", start_cash=1000)
    lines = process_new_days(account, prices, always_in, {}, cost_per_trade=COST)
    assert len(lines) == 1
    assert lines[0]["date"] == str(prices.index[-1].date())
    assert account["started"] == str(prices.index[-1].date())
    assert np.isclose(account["equity"], 1000 * (1 - COST))      # one purchase, nothing else


def test_paper_trading_matches_the_backtester_day_for_day():
    prices = gentle_prices()
    start = 100
    account = new_account("test", start_cash=1.0)
    process_new_days(account, prices.iloc[:start + 1], trend_filter, {"window": 20}, cost_per_trade=COST)
    lines = process_new_days(account, prices, trend_filter, {"window": 20}, cost_per_trade=COST)
    paper = pd.Series([line["equity"] for line in lines],
                      index=pd.to_datetime([line["date"] for line in lines]))

    positions = trend_filter(prices, window=20)
    engine = run_backtest(prices.iloc[start:], positions.iloc[start:], fee=COST, slippage=0)
    # The engine charges for a trade on the day after it is decided; the paper
    # account charges on the day itself. Otherwise they must agree exactly.
    paid_next_day = 1 - engine["traded"].shift(-1) * COST
    expected = (engine["equity"] * paid_next_day).iloc[1:-1]
    assert np.allclose(paper.loc[expected.index], expected)
    assert (engine["traded"] > 0).sum() > 5                       # the test really exercised trading


def test_catching_up_gives_the_same_record_as_running_every_day():
    prices = gentle_prices()
    daily = started_account(prices, trend_filter_20, days_before=30)
    all_at_once = started_account(prices, trend_filter_20, days_before=30)

    daily_lines = []
    for end in range(len(prices) - 29, len(prices) + 1):
        daily_lines += process_new_days(daily, prices.iloc[:end], trend_filter_20, {}, cost_per_trade=COST)
    once_lines = process_new_days(all_at_once, prices, trend_filter_20, {}, cost_per_trade=COST)

    assert len(once_lines) == 30
    assert daily_lines == once_lines
    assert daily == all_at_once


def trend_filter_20(prices):
    return trend_filter(prices, window=20)


def test_running_twice_on_the_same_prices_changes_nothing():
    prices = gentle_prices()
    account = started_account(prices, days_before=5)
    process_new_days(account, prices, always_in, {}, cost_per_trade=COST)
    before = dict(account)
    assert process_new_days(account, prices, always_in, {}, cost_per_trade=COST) == []
    assert account == before


def test_the_strategy_is_only_shown_prices_up_to_the_day_being_processed():
    prices = gentle_prices()
    seen = []

    def spy(history):
        seen.append(history.index[-1])
        return pd.Series(1.0, index=history.index)

    account = started_account(prices, days_before=10)
    lines = process_new_days(account, prices, spy, {}, cost_per_trade=COST)
    assert [str(day.date()) for day in seen] == [line["date"] for line in lines]


def test_the_account_and_record_survive_being_saved_and_loaded():
    prices = gentle_prices()
    with tempfile.TemporaryDirectory() as folder:
        account = new_account("test", start_cash=1000)
        save(folder, account, process_new_days(account, prices.iloc[:-3], always_in, {}, cost_per_trade=COST))
        loaded = load_account(folder, "test")
        assert loaded == account
        save(folder, loaded, process_new_days(loaded, prices, always_in, {}, cost_per_trade=COST))
        record = pd.read_csv(os.path.join(folder, paper_trade.RECORD_FILE))
        assert len(record) == 4
        assert list(record.columns) == paper_trade.RECORD_COLUMNS
        assert np.isclose(record["equity"].iloc[-1], loaded["equity"])


def test_a_record_cannot_quietly_switch_to_another_strategy():
    with tempfile.TemporaryDirectory() as folder:
        save(folder, new_account("first"), [])
        try:
            load_account(folder, "second")
        except ValueError:
            return
        raise AssertionError("the paper record was allowed to change strategy")


# --- The limits -------------------------------------------------------------

def test_no_strategy_can_get_past_the_position_limit():
    assert risk_limits.MAX_POSITION <= 1.0, "above 1.0 would mean borrowing"
    for wanted in (3.0, 1.0001, float("inf")):
        assert risk_limits.limit_position(wanted) <= risk_limits.MAX_POSITION
    for wanted in (-1.0, float("nan"), float("-inf"), None, "all of it"):
        assert risk_limits.limit_position(wanted) == 0.0
    assert risk_limits.limit_position(0.5) == min(0.5, risk_limits.MAX_POSITION)

    prices = gentle_prices()
    account = new_account("test", start_cash=1000)
    lines = process_new_days(account, prices, lambda p: pd.Series(5.0, index=p.index), {}, cost_per_trade=COST)
    assert account["position"] == risk_limits.MAX_POSITION
    assert "limited" in lines[0]["notes"]


def test_a_big_one_day_loss_stops_the_account():
    closes = [100.0] * 50 + [100 * (1 - risk_limits.MAX_DAILY_LOSS - 0.03)] + [70.0, 90.0, 120.0]
    prices = make_prices(closes)
    account = started_account(prices.iloc[:50], days_before=0)
    lines = process_new_days(account, prices, always_in, {}, cost_per_trade=COST)

    assert account["stopped"] and "in one day" in account["stopped"]
    assert "STOPPED" in lines[0]["notes"]
    assert [line["position"] for line in lines] == [0.0, 0.0, 0.0, 0.0]
    # Once out, later price moves no longer touch the account.
    assert len({line["equity"] for line in lines}) == 1


def test_a_long_slide_stops_the_account_at_the_drawdown_limit():
    falls = 0.97 ** np.arange(60)                                  # 3% a day, every day
    prices = make_prices(100 * falls)
    account = started_account(prices.iloc[:1], days_before=0)
    lines = process_new_days(account, prices, always_in, {}, cost_per_trade=COST)

    assert account["stopped"] and "below its highest value" in account["stopped"]
    lowest = min(line["equity"] for line in lines) / 1000
    assert -risk_limits.MAX_DRAWDOWN - 0.05 < lowest - 1 < -risk_limits.MAX_DRAWDOWN
    assert lines[-1]["position"] == 0.0


def test_an_impossible_price_move_stops_the_account():
    prices = make_prices([100.0] * 10 + [100 * (1 + risk_limits.MAX_PRICE_JUMP + 0.3), 105.0])
    account = started_account(prices.iloc[:10], days_before=0)
    process_new_days(account, prices, always_in, {}, cost_per_trade=COST)
    assert account["stopped"] and "data may be wrong" in account["stopped"]
    assert account["position"] == 0.0


def test_the_kill_switch_forces_the_position_to_zero_and_releases_when_removed():
    prices = gentle_prices()
    account = started_account(prices, days_before=3)
    assert account["position"] == 1.0

    process_new_days(account, prices.iloc[:-2], always_in, {}, kill_switch_on=True, cost_per_trade=COST)
    assert account["position"] == 0.0
    assert account["stopped"] is None                              # a kill switch is not a limit stop

    process_new_days(account, prices, always_in, {}, kill_switch_on=False, cost_per_trade=COST)
    assert account["position"] == 1.0


def test_the_kill_switch_is_a_file():
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, risk_limits.KILL_SWITCH_FILE)
        assert risk_limits.kill_switch_is_on(path) is False
        open(path, "w").close()
        assert risk_limits.kill_switch_is_on(path) is True


def test_a_stopped_account_stays_stopped_until_resumed():
    closes = [100.0] * 20 + [70.0] + [70.0] * 5
    prices = make_prices(closes)
    account = started_account(prices.iloc[:20], days_before=0)
    process_new_days(account, prices.iloc[:23], always_in, {}, cost_per_trade=COST)
    assert account["stopped"] and account["position"] == 0.0

    resume(account)
    assert account["stopped"] is None
    assert account["peak"] == account["equity"]                    # the old fall is not counted twice
    process_new_days(account, prices, always_in, {}, cost_per_trade=COST)
    assert account["position"] == 1.0
    assert account["stopped"] is None


def test_old_prices_are_flagged_as_stale():
    assert risk_limits.data_is_stale(date(2026, 1, 9), date(2026, 1, 10)) is False
    assert risk_limits.data_is_stale(date(2026, 1, 7), date(2026, 1, 10)) is True


def test_the_research_code_has_no_route_to_the_limits():
    # The improvement loop and everything it uses must not mention the limits
    # or the paper-trading runner, and the limits must not depend on them.
    for name in ("strategies.py", "proposals.py", "improve.py", "walk_forward.py",
                 "acceptance.py", "backtest.py", "config.py", "run_baselines.py"):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), name)) as file:
            code = [line for line in file if line.lstrip().startswith(("import ", "from "))]
        assert not any("risk_limits" in line or "paper_trade" in line for line in code), name
    with open(risk_limits.__file__) as file:
        imports = [line.strip() for line in file if line.startswith(("import ", "from "))]
    assert imports == ["import math", "import os"]


# --- The downloader's update ------------------------------------------------

def test_new_days_are_added_and_overlapping_days_are_replaced():
    old = make_prices([1, 2, 3, 4], start="2024-01-01")
    new = make_prices([30, 40, 50], start="2024-01-03")
    merged = merge(old, new)
    assert list(merged["close"]) == [1, 2, 30, 40, 50]
    assert merged.index.is_monotonic_increasing and merged.index.is_unique


if __name__ == "__main__":
    tests = [(name, item) for name, item in sorted(globals().items())
             if name.startswith("test_") and callable(item)]
    for name, test in tests:
        test()
        print(f"ok  {name}")
    print(f"\nAll {len(tests)} tests passed.")
