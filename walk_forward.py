"""Walk-forward testing: the honest way to score a strategy that has settings.

This file is the machinery. To run it on real ideas, use: python improve.py

The problem it solves: if you try six settings on the whole history and report
the best one, the score is flattering, because the setting was picked knowing
how that history turned out.

Walk-forward does what you would have had to do in real life:

  1. Stand at a date. Using only prices before it, pick the setting with the
     best score so far.
  2. Trade that setting for the next year. Record what happened.
  3. Move the date forward a year and repeat.

Only the "what happened" pieces are joined together and scored. Every day in
that score was traded with a setting chosen before that day.
"""

import pandas as pd

import config
from backtest import run_backtest, summarize


def walk_forward(prices, strategy, grid, warmup=0, min_train_days=None,
                 test_days=None, objective=None, fee=None, slippage=None):
    """Walk a strategy forward through `prices`, re-choosing its settings as it goes.

    strategy: a function like those in strategies.py
    grid:     the list of settings to choose between, e.g. [{"window": 100}, {"window": 200}]
    Returns (result, folds):
      result - the backtest of the joined-up out-of-sample periods
      folds  - one row per period: what was chosen and how it scored before and after
    """
    min_train_days = config.WF_MIN_TRAIN_DAYS if min_train_days is None else min_train_days
    test_days = config.WF_TEST_DAYS if test_days is None else test_days
    objective = objective or config.OBJECTIVE
    if len(prices) <= min_train_days:
        raise ValueError("Not enough data: need more days than WF_MIN_TRAIN_DAYS.")

    decisions = pd.Series(0.0, index=prices.index)
    chosen = []

    start = min_train_days
    while start < len(prices):
        end = min(start + test_days, len(prices))

        # 1. Choose: score every setting on the days before `start` only.
        train = prices.iloc[:start]
        best_params, best_score = None, None
        for params in grid:
            trained = run_backtest(train, strategy(train, **params), fee, slippage)
            score = summarize(trained.iloc[warmup:])[objective]
            if best_score is None or score > best_score:
                best_params, best_score = params, score

        # 2. Trade: use the chosen setting for the days from `start` to `end`.
        # The strategy sees earlier prices (it needs them for its averages)
        # but nothing after `end`.
        history = prices.iloc[:end]
        decisions.iloc[start:end] = strategy(history, **best_params).iloc[start:end]

        chosen.append({"test_start": prices.index[start], "test_end": prices.index[end - 1],
                       "params": best_params, "train_score": best_score})
        start = end

    # 3. Score the joined-up test periods as one continuous run, so switching
    # settings at a boundary pays trading costs like any other trade.
    result = run_backtest(prices.iloc[min_train_days:], decisions.iloc[min_train_days:],
                          fee, slippage)

    for fold in chosen:
        period = result.loc[fold["test_start"]:fold["test_end"]]
        fold["test_score"] = summarize(period)[objective]
    return result, pd.DataFrame(chosen)


def score_fixed(prices, strategy, params, min_train_days=None):
    """Score a strategy with fixed settings over the same days walk-forward is scored on."""
    min_train_days = config.WF_MIN_TRAIN_DAYS if min_train_days is None else min_train_days
    positions = strategy(prices, **params)
    return run_backtest(prices.iloc[min_train_days:], positions.iloc[min_train_days:])
