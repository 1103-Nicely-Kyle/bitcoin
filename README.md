# Bitcoin research harness

A harness for testing bitcoin trading ideas honestly, on daily prices, with
costs included. It does not place trades and does not improve itself yet.
This is stage 1: the part that measures.

## Run it

```bash
pip install pandas numpy
```

```bash
python test_backtest.py
```

```bash
python fetch_data.py
```

```bash
python run_baselines.py
```

```bash
python test_walk_forward.py
```

```bash
python walk_forward.py
```

## The files

| File | What it does |
| --- | --- |
| `config.py` | Every setting: fees, slippage, the holdout date, file paths. |
| `fetch_data.py` | Downloads daily BTC-USD candles from Coinbase's public API (no account needed). |
| `backtest.py` | The engine: data loading, the simulation, the metrics, the experiment log. |
| `strategies.py` | Three baselines: buy-and-hold, 200-day trend filter, 50/200 moving-average crossover. |
| `run_baselines.py` | Scores the baselines on the research data and prints a table. |
| `test_backtest.py` | Tests that the engine cannot peek at the future and charges costs correctly. |
| `walk_forward.py` | Scores strategies that have settings: chooses the setting on past data, trades it for the next year, repeats. |
| `test_walk_forward.py` | Tests that a choice never sees the days it is scored on. |
| `experiments.jsonl` | One line per experiment ever run. Never delete lines from it. |

## The rules the harness enforces

- **No peeking.** A position decided at today's close earns tomorrow's price
  move, never today's.
- **Costs always.** Every change in position pays the fee and slippage in
  `config.py`. The fee there (0.40%) is a placeholder: replace it with what
  your exchange charges you.
- **Locked holdout.** Data from `HOLDOUT_START` (2025-01-01) onward is not
  available to research code. It is for one final check of a finished
  strategy. Do not move the date after seeing results.
- **Settings are chosen blind.** A strategy with settings is scored by
  walk-forward: each setting is picked using only earlier prices, then
  scored on the following year. The score used to pick is Sharpe (return per
  unit of risk), set by `OBJECTIVE` in `config.py`.
- **Everything is counted.** Each experiment is appended to
  `experiments.jsonl`. The more ideas tried, the more likely the best one is
  luck, so the count matters later. Re-running an identical experiment does
  not add a line.

## Baseline results

Research data 2015-07-20 to 2024-12-31, after 0.45% cost per trade:

| Strategy | Total return | Per year | Sharpe | Worst drop | Trades | Time in market |
| --- | --- | --- | --- | --- | --- | --- |
| Buy and hold | 33,091% | 84.7% | 1.23 | -83.8% | 1 | 100% |
| Trend filter (200-day) | 14,261% | 69.1% | 1.24 | -71.6% | 53 | 60% |
| MA crossover (50/200) | 16,727% | 71.9% | 1.23 | -72.7% | 15 | 60% |

Neither trend strategy beat simply holding. They gave up return for a
somewhat smaller worst drop, and the risk-adjusted score (Sharpe) came out
the same. That is the bar any new idea has to clear.

## Walk-forward results

Settings re-chosen every 365 days from all earlier data. Scored span
2018-07-19 to 2024-12-31, after costs. The fixed baselines are scored on the
same span for comparison.

| Strategy | Total return | Per year | Sharpe | Worst drop | Trades | Time in market |
| --- | --- | --- | --- | --- | --- | --- |
| Buy and hold | 1,144% | 47.7% | 0.93 | -76.7% | 1 | 100% |
| Trend filter, fixed 200-day | 898% | 42.8% | 0.99 | -66.4% | 45 | 56% |
| MA crossover, fixed 50/200 | 862% | 42.0% | 0.94 | -66.2% | 13 | 55% |
| Trend filter, walk-forward | 1,048% | 45.9% | 1.03 | -62.3% | 91 | 57% |
| MA crossover, walk-forward | 280% | 23.0% | 0.67 | -71.2% | 15 | 57% |

Re-choosing settings did not produce an edge. The walk-forward trend filter
has the highest Sharpe, but its lead over buy-and-hold (0.10) is far inside
what chance alone produces on six years of data: resampling the same days
puts the difference anywhere from -0.48 to +0.68. The walk-forward crossover
did clearly worse than leaving its settings alone.

In every period the chosen setting had scored between 1.3 and 2.2 on the
data it was picked from. On the year that followed it scored anywhere from
-1.4 to 2.8. That gap is why nothing here is judged on the data it was
tuned on.

This is a research project. Nothing here is financial advice.
