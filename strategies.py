"""The strategies: the three baselines every idea has to beat after costs,
and the ideas tried by the improvement loop (see proposals.py).

A strategy is a function that takes the price table and returns one number per
day: 1.0 = hold bitcoin, 0.0 = hold cash. The number for a given day may only
use prices up to and including that day.
"""

import numpy as np
import pandas as pd

import config


def buy_and_hold(prices):
    """Buy on day one and never sell."""
    return pd.Series(1.0, index=prices.index)


def trend_filter(prices, window=200):
    """Hold bitcoin only while the price is above its average of the last `window` days."""
    average = prices["close"].rolling(window).mean()
    return (prices["close"] > average).astype(float)


def ma_crossover(prices, fast=50, slow=200):
    """Hold bitcoin only while the fast moving average is above the slow one."""
    fast_average = prices["close"].rolling(fast).mean()
    slow_average = prices["close"].rolling(slow).mean()
    return (fast_average > slow_average).astype(float)


def trend_buffer(prices, window=200, band=0.05):
    """A trend filter with a dead zone around the average.

    Buy only once the price is `band` above the average (0.05 = 5%), sell only
    once it is `band` below. In between, keep whatever was held.
    """
    close = prices["close"]
    average = close.rolling(window).mean()
    signal = pd.Series(np.nan, index=prices.index)
    signal[close > average * (1 + band)] = 1.0
    signal[close < average * (1 - band)] = 0.0
    return signal.ffill().fillna(0.0)       # ffill = "keep the last decision"


def vol_target(prices, target=0.6, lookback=30, step=0.1):
    """Hold less bitcoin when it has been swinging wildly, more when it is calm.

    `target` is the yearly swing to aim for (0.6 = 60%). The position is
    target / recent swing, never more than 100%. To avoid paying fees for
    tiny adjustments, it only trades when the wanted position is at least
    `step` away from the current one.
    """
    daily_move = prices["close"].pct_change()
    recent_swing = daily_move.rolling(lookback).std() * np.sqrt(config.PERIODS_PER_YEAR)
    wanted = (target / recent_swing).clip(upper=1.0).fillna(0.0)

    positions = []
    current = 0.0
    for value in wanted:
        if abs(value - current) >= step:
            current = value
        positions.append(current)
    return pd.Series(positions, index=prices.index)


def trend_blend(prices, windows=(50, 100, 150, 200, 250, 300)):
    """Several trend filters voting. The position is the share that say "hold".

    With six windows the position moves in steps of one sixth instead of
    jumping between all-in and all-out.
    """
    close = prices["close"]
    votes = [(close > close.rolling(window).mean()).astype(float) for window in windows]
    return sum(votes) / len(windows)


BASELINES = {
    "buy_and_hold": (buy_and_hold, {}, "Bitcoin has risen over the long run; do nothing."),
    "trend_filter_200": (trend_filter, {"window": 200},
                         "Big falls happen below the 200-day average; step aside for them."),
    "ma_crossover_50_200": (ma_crossover, {"fast": 50, "slow": 200},
                            "Same idea as the trend filter, with fewer false alarms."),
}
