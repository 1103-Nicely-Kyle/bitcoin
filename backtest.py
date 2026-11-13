"""The backtest engine: scores a strategy on past prices, costs included.

How time works here (this is the part that prevents cheating):

  * A strategy looks at prices up to and including today's close and returns
    the position it wants: 1.0 = fully in bitcoin, 0.0 = fully in cash.
  * That position is bought at today's close and earns TOMORROW's price move.
    It never earns the move of the day it was decided on.
  * Every change in position pays the fee and slippage from config.py.
"""

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import config


# --- Loading data -----------------------------------------------------------

def load_all_data(path=None):
    """Load the full price file. Research code should NOT call this directly."""
    path = path or config.DATA_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found. Run: python fetch_data.py")
    return pd.read_csv(path, index_col="date", parse_dates=True).sort_index()


def split_research_holdout(prices, holdout_start=None):
    """Cut a price table in two: (research part, locked holdout part)."""
    cutoff = pd.Timestamp(holdout_start or config.HOLDOUT_START)
    return prices[prices.index < cutoff], prices[prices.index >= cutoff]


def load_research_data(path=None):
    """The data you are allowed to experiment on: everything before the holdout."""
    research, _ = split_research_holdout(load_all_data(path))
    return research


def load_holdout_data(path=None, i_understand_this_is_one_shot=False):
    """The locked data. Looking at it more than once ruins it as a fair test.

    Every call is written to the experiment log so there is a record.
    """
    if not i_understand_this_is_one_shot:
        raise PermissionError(
            "The holdout is locked. It is for one final check of a finished "
            "strategy. If that is really what this is, pass "
            "i_understand_this_is_one_shot=True."
        )
    log_experiment("HOLDOUT ACCESSED", {}, "final check", {})
    _, holdout = split_research_holdout(load_all_data(path))
    return holdout


# --- The engine -------------------------------------------------------------

def run_backtest(prices, positions, fee=None, slippage=None):
    """Simulate holding `positions` over `prices`.

    prices:    table with a 'close' column, one row per day
    positions: one number per day between 0 and 1 - the position the strategy
               wants after seeing that day's close
    Returns a table with the daily return and the growth of 1 dollar ('equity').
    """
    fee = config.FEE if fee is None else fee
    slippage = config.SLIPPAGE if slippage is None else slippage
    cost_per_trade = fee + slippage

    positions = positions.reindex(prices.index).fillna(0.0).clip(0.0, 1.0)

    # The position decided at yesterday's close is the one held today.
    held = positions.shift(1).fillna(0.0)
    price_return = prices["close"].pct_change().fillna(0.0)

    # How much was bought or sold to get into today's holding.
    traded = held.diff().abs()
    traded.iloc[0] = held.iloc[0]

    daily_return = (1 - traded * cost_per_trade) * (1 + held * price_return) - 1

    return pd.DataFrame({
        "held": held,
        "traded": traded,
        "return": daily_return,
        "equity": (1 + daily_return).cumprod(),
    })


def summarize(result):
    """Boil a backtest down to the handful of numbers worth comparing."""
    returns = result["return"]
    equity = (1 + returns).cumprod()   # rebuilt so this also works on a slice
    years = len(returns) / config.PERIODS_PER_YEAR

    total_return = equity.iloc[-1] - 1
    yearly_return = equity.iloc[-1] ** (1 / years) - 1 if years > 0 else 0.0
    volatility = returns.std() * np.sqrt(config.PERIODS_PER_YEAR)
    sharpe = (returns.mean() * config.PERIODS_PER_YEAR / volatility) if volatility > 0 else 0.0
    drawdown = equity / equity.cummax() - 1

    return {
        "total_return": float(total_return),
        "yearly_return": float(yearly_return),
        "sharpe": float(sharpe),
        "max_drawdown": float(drawdown.min()),
        "trades": int((result["traded"] > 0).sum()),
        "time_in_market": float(result["held"].mean()),
    }


# --- The experiment log -----------------------------------------------------

def log_experiment(name, params, hypothesis, metrics, path=None):
    """Append one line to the experiment log. Nothing is ever deleted from it.

    Returns True if a line was added, False if this exact run was already there.

    The count of lines matters: the more ideas you have tried, the more likely
    the best-looking one is just luck.
    """
    path = path or config.EXPERIMENT_LOG
    entry = {
        "when": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "name": name,
        "params": params,
        "hypothesis": hypothesis,
        "fee": config.FEE,
        "slippage": config.SLIPPAGE,
        "metrics": metrics,
    }
    # Re-running the exact same experiment is not a new idea, so it is not
    # logged twice.
    if os.path.exists(path):
        with open(path) as log:
            for line in log:
                if not line.strip():
                    continue
                earlier = json.loads(line)
                if all(earlier.get(key) == value for key, value in entry.items() if key != "when"):
                    return False

    with open(path, "a") as log:
        log.write(json.dumps(entry) + "\n")
    return True


def count_experiments(path=None):
    path = path or config.EXPERIMENT_LOG
    if not os.path.exists(path):
        return 0
    with open(path) as log:
        return sum(1 for line in log if line.strip())
