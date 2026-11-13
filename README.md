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

## The files

| File | What it does |
| --- | --- |
| `config.py` | Every setting: fees, slippage, the holdout date, file paths. |
| `fetch_data.py` | Downloads daily BTC-USD candles from Coinbase's public API (no account needed). |
| `backtest.py` | The engine: data loading, the simulation, the metrics, the experiment log. |
| `strategies.py` | Three baselines: buy-and-hold, 200-day trend filter, 50/200 moving-average crossover. |
| `run_baselines.py` | Scores the baselines on the research data and prints a table. |
| `test_backtest.py` | Tests that the engine cannot peek at the future and charges costs correctly. |
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
- **Everything is counted.** Each experiment is appended to
  `experiments.jsonl`. The more ideas tried, the more likely the best one is
  luck, so the count matters later.

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

This is a research project. Nothing here is financial advice.
