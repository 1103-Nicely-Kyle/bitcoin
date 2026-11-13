"""The baseline strategies. Every later idea has to beat these after costs.

A strategy is a function that takes the price table and returns one number per
day: 1.0 = hold bitcoin, 0.0 = hold cash. The number for a given day may only
use prices up to and including that day.
"""

import pandas as pd


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


BASELINES = {
    "buy_and_hold": (buy_and_hold, {}, "Bitcoin has risen over the long run; do nothing."),
    "trend_filter_200": (trend_filter, {"window": 200},
                         "Big falls happen below the 200-day average; step aside for them."),
    "ma_crossover_50_200": (ma_crossover, {"fast": 50, "slow": 200},
                            "Same idea as the trend filter, with fewer false alarms."),
}
