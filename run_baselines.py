"""Score the baseline strategies on the research data and print a table.

    python run_baselines.py

Only data before the holdout date is used. Each run is added to the
experiment log.
"""

import pandas as pd

import config
from backtest import (count_experiments, load_research_data, log_experiment,
                      run_backtest, summarize)
from strategies import BASELINES


def main():
    prices = load_research_data()
    print(f"Research data: {prices.index[0].date()} to {prices.index[-1].date()} "
          f"({len(prices)} days). Holdout from {config.HOLDOUT_START} is locked.")
    print(f"Costs: {config.FEE:.2%} fee + {config.SLIPPAGE:.2%} slippage per trade.\n")

    rows = {}
    for name, (strategy, params, hypothesis) in BASELINES.items():
        positions = strategy(prices, **params)
        metrics = summarize(run_backtest(prices, positions))
        log_experiment(name, params, hypothesis, metrics)
        rows[name] = metrics

    table = pd.DataFrame(rows).T
    shown = pd.DataFrame({
        "total return": table["total_return"].map("{:,.0%}".format),
        "per year": table["yearly_return"].map("{:.1%}".format),
        "sharpe": table["sharpe"].map("{:.2f}".format),
        "worst drop": table["max_drawdown"].map("{:.1%}".format),
        "trades": table["trades"].astype(int),
        "time in market": table["time_in_market"].map("{:.0%}".format),
    })
    print(shown.to_string())
    print(f"\nExperiments logged so far: {count_experiments()}")


if __name__ == "__main__":
    main()
