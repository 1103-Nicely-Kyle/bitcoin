# Bitcoin research harness

A harness for testing bitcoin trading ideas honestly, on daily prices, with
costs included, plus a loop that tests new ideas one at a time and keeps only
what clears a rising bar. It does not place trades.

## Run it

```bash
pip install pandas numpy
```

Download the prices (no account needed):

```bash
python fetch_data.py
```

Run the improvement loop: it tests anything new in `proposals.py` and shows
where every idea stands.

```bash
python improve.py
```

The same, with the year-by-year detail for every idea:

```bash
python improve.py --folds
```

Score just the three baselines over the whole research period:

```bash
python run_baselines.py
```

Run the tests (made-up prices, nothing is downloaded):

```bash
python test_backtest.py
```

```bash
python test_walk_forward.py
```

```bash
python test_acceptance.py
```

```bash
python test_improve.py
```

## The files

| File | What it does |
| --- | --- |
| `config.py` | Every setting: fees, slippage, the holdout date, the bar. |
| `fetch_data.py` | Downloads daily BTC-USD candles from Coinbase's public API. |
| `backtest.py` | The engine: data loading, the simulation, the metrics, the experiment log. |
| `strategies.py` | The three baselines and the strategies the loop has tried. |
| `walk_forward.py` | Scores a strategy that has settings: chooses the setting on past data, trades it for the next year, repeats. |
| `acceptance.py` | The acceptance rule: decides whether a lead over the baselines is bigger than luck. |
| `proposals.py` | The queue of ideas. Add one here to start a cycle. |
| `improve.py` | The loop: checks, tests, logs and judges every proposal. |
| `run_baselines.py` | Scores the baselines on the whole research period. |
| `experiments.jsonl` | One line per experiment ever run. Never delete lines from it. |
| `test_*.py` | Tests for each part above. |

## How one cycle of the loop works

1. **Propose.** Add one idea to the end of `proposals.py`, with a written
   reason for why it should work in the real world.
2. **Check.** The loop refuses the idea if its positions change when later
   prices are removed, which means it was using the future.
3. **Test.** The idea is scored by walk-forward on the research data.
4. **Log.** The test is added to `experiments.jsonl`. This raises the bar.
5. **Judge.** Every idea tried so far is judged again at the new bar.
6. **Keep.** The champion is the best idea that still clears the bar. If
   none does, there is no champion.

Because step 5 re-judges everything, a champion can lose its title as more
ideas are tried. That is deliberate: the more you search, the less any one
result proves.

### Rules for proposing

- One change per proposal, with a reason that is not "it scored well".
- Write the proposal before looking at how it scores.
- Never edit or delete a tested proposal. An adjusted idea is a new
  proposal and counts as a new experiment.
- Do not change `config.py`, the engine, or the acceptance rule to make an
  idea pass.

## The rules the harness enforces

- **No peeking.** A position decided at today's close earns tomorrow's price
  move, never today's. Every proposal is checked for this automatically.
- **Costs always.** Every change in position pays the fee and slippage in
  `config.py`. The fee there (0.40%) is a placeholder: replace it with what
  your exchange charges you.
- **Locked holdout.** Data from `HOLDOUT_START` (2025-01-01) onward is not
  available to research code. It is for one final check of a finished
  strategy. Do not move the date after seeing results.
- **Settings are chosen blind.** Each setting is picked using only earlier
  prices, then scored on the following year. The score used to pick is
  Sharpe (return per unit of risk).
- **A lead has to be bigger than luck.** A candidate is accepted only if its
  Sharpe lead over every baseline is several times larger than the noise in
  that lead. The noise is measured by reshuffling the history in 30-day
  chunks. The bar rises with the number of experiments in the log: 1.64
  times the noise for the first idea, 2.33 after 5, 2.58 after 10, 3.29
  after 100.
- **Everything is counted.** Each experiment is appended to
  `experiments.jsonl`. Re-running an identical experiment does not add a
  line.

## Results so far

Scored span 2018-07-19 to 2024-12-31, after 0.45% cost per trade. The
holdout has not been touched. With 8 experiments logged, a lead must be at
least 2.50 times its own noise against every baseline.

| Strategy | Sharpe | Per year | Worst drop | Trades | Lead / noise | Status |
| --- | --- | --- | --- | --- | --- | --- |
| Buy and hold | 0.93 | 47.7% | -76.7% | 1 | | baseline |
| Trend filter, fixed 200-day | 0.99 | 42.8% | -66.4% | 45 | | baseline |
| MA crossover, fixed 50/200 | 0.94 | 42.0% | -66.2% | 13 | | baseline |
| `wf_trend_filter` | 1.03 | 45.9% | -62.3% | 91 | +0.16 | rejected |
| `wf_ma_crossover` | 0.67 | 23.0% | -71.2% | 15 | -1.68 | rejected |
| `trend_buffer` | 1.11 | 52.9% | -65.2% | 23 | +0.44 | rejected |
| `vol_target` | 0.95 | 41.5% | -68.7% | 80 | -0.13 | rejected |
| `trend_blend` | 1.13 | 50.7% | -55.5% | 314 | +0.80 | rejected |

"Lead / noise" is against whichever baseline the idea did worst against.
"Trades" counts days with any trading, so an idea that moves in small steps
shows a high number.

**Champion: none.** Nothing has cleared the bar.

The bar is high. For the trend ideas, the noise in a lead over buy-and-hold
on this span is 0.25 to 0.3, so one of them needs a Sharpe of roughly 1.6 to
1.7 against buy-and-hold's 0.93 to be accepted. The rule was checked on
made-up strategies with no edge at all: it accepted 5.8% of them when it was
aiming for 5%.

For reference, over the whole research period (2015-07-20 to 2024-12-31)
the baselines scored: buy and hold 1.23 Sharpe with a -83.8% worst drop,
200-day trend filter 1.24 with -71.6%, 50/200 crossover 1.23 with -72.7%.

This is a research project. Nothing here is financial advice.
