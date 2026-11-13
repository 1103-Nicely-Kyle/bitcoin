"""Walk-forward testing: the honest way to score a strategy that has settings.

    python walk_forward.py

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
from backtest import (count_experiments, load_research_data, log_experiment,
                      run_backtest, summarize)
from strategies import buy_and_hold, ma_crossover, trend_filter

# The longest look-back any setting below needs. Training scores skip this
# many days at the start so a slow setting is not marked down just for
# needing more history before its first trade.
WARMUP_DAYS = 300

FAMILIES = {
    "wf_trend_filter": {
        "strategy": trend_filter,
        "grid": [{"window": window} for window in (50, 100, 150, 200, 250, 300)],
        "hypothesis": "The best trend length changes over time; re-choosing it each year helps.",
    },
    "wf_ma_crossover": {
        "strategy": ma_crossover,
        "grid": [{"fast": fast, "slow": slow}
                 for fast in (20, 50, 100) for slow in (100, 200, 300) if fast < slow],
        "hypothesis": "The best pair of averages changes over time; re-choosing it each year helps.",
    },
}


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


def describe(params):
    return ", ".join(f"{key}={value}" for key, value in params.items())


def main():
    prices = load_research_data()
    span = prices.index[config.WF_MIN_TRAIN_DAYS:]
    print(f"Research data: {prices.index[0].date()} to {prices.index[-1].date()}. "
          f"Holdout from {config.HOLDOUT_START} is locked.")
    print(f"Settings are chosen by {config.OBJECTIVE} on all earlier data, "
          f"then traded for the next {config.WF_TEST_DAYS} days.")
    print(f"Scored span: {span[0].date()} to {span[-1].date()} ({len(span)} days).")
    print(f"Costs: {config.FEE:.2%} fee + {config.SLIPPAGE:.2%} slippage per trade.")

    rows = {
        "buy_and_hold": summarize(score_fixed(prices, buy_and_hold, {})),
        "fixed trend_filter 200": summarize(score_fixed(prices, trend_filter, {"window": 200})),
        "fixed ma_crossover 50/200": summarize(
            score_fixed(prices, ma_crossover, {"fast": 50, "slow": 200})),
    }

    for name, family in FAMILIES.items():
        result, folds = walk_forward(prices, family["strategy"], family["grid"], warmup=WARMUP_DAYS)
        metrics = summarize(result)
        rows[name] = metrics

        print(f"\n{name}: chosen from {len(family['grid'])} settings each period")
        shown = pd.DataFrame({
            "test period": [f"{a.date()} to {b.date()}"
                            for a, b in zip(folds["test_start"], folds["test_end"])],
            "chosen": folds["params"].map(describe),
            "score before": folds["train_score"].map("{:.2f}".format),
            "score after": folds["test_score"].map("{:.2f}".format),
        })
        print(shown.to_string(index=False))

        log_experiment(name, {
            "grid": family["grid"],
            "objective": config.OBJECTIVE,
            "min_train_days": config.WF_MIN_TRAIN_DAYS,
            "test_days": config.WF_TEST_DAYS,
            "scored_from": str(span[0].date()),
            "scored_to": str(span[-1].date()),
        }, family["hypothesis"], metrics)

    table = pd.DataFrame(rows).T
    print("\nAll scored on the same span, after costs:")
    print(pd.DataFrame({
        "total return": table["total_return"].map("{:,.0%}".format),
        "per year": table["yearly_return"].map("{:.1%}".format),
        "sharpe": table["sharpe"].map("{:.2f}".format),
        "worst drop": table["max_drawdown"].map("{:.1%}".format),
        "trades": table["trades"].astype(int),
        "time in market": table["time_in_market"].map("{:.0%}".format),
    }).to_string())
    print(f"\nExperiments logged so far: {count_experiments()}")


if __name__ == "__main__":
    main()
