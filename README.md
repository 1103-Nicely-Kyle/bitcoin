# Bitcoin research harness

A harness for testing bitcoin trading ideas honestly, on daily prices, with
costs included, plus a loop that tests new ideas one at a time and keeps only
what clears a rising bar, and a paper-trading runner that follows one
strategy forward on real prices with pretend money. It never places a real
trade.

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

Paper trading: download the newest prices and move the pretend account
forward. Run it daily or less often; it catches up on missed days.

```bash
python paper_trade.py
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

```bash
python test_paper_trade.py
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
| `paper_trade.py` | Paper trading: runs one strategy on real prices as they arrive, with pretend money. |
| `risk_limits.py` | The hard limits and the kill switch. Yours to set, by hand. |
| `paper/` | The paper account (`account.json`) and its day-by-day record (`record.csv`). |
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

## Paper trading

`paper_trade.py` follows the strategy named by `PAPER_STRATEGY` in
`config.py`. Until an idea clears the bar, that is a stand-in: the 200-day
trend filter. For each new day it revalues the account at the close, checks
the risk limits, asks the strategy what it wants, lets the limits have the
final say, and "trades" the difference at the close with fee and slippage.

- The account started on 2026-11-12 with a pretend $10,000 and only moves
  forward. It never trades the past, so it says nothing about the holdout.
- Trades are filled at the daily closing price by assumption. This tests
  the strategy on prices that did not exist when it was fixed, and that the
  pipeline works. It does not test getting real orders filled.
- Because of that, the record comes out the same whether you run it daily
  or catch up once a week.
- It only runs baselines for now. Running a walk-forward idea needs a small
  addition, to be built when there is a champion to run.

## Risk limits

These are in `risk_limits.py` and nowhere else. A strategy only says what
position it wants; the limits decide what it gets. No research file imports
them, and a test checks that.

| Limit | Value | What happens |
| --- | --- | --- |
| Largest position | 100% of the account | Anything above is cut down; anything below zero becomes zero. |
| One-day loss | 15% | Sell everything and stop. |
| Fall from the highest value | 40% | Sell everything and stop. |
| One-day price move | 50% | Treat the data as wrong: sell everything and stop. |
| Age of newest price | 1 day | Warn not to act on the position shown. |

A stop stays in place until you clear it:

```bash
python paper_trade.py --resume
```

**Kill switch.** Create a file named `KILL_SWITCH` in this folder and the
position is forced to zero from the next run. Delete the file to carry on.

The values are placeholders for you to choose. For scale, on the research
data (2015 to 2024) the stand-in strategy would have hit the 15% one-day
limit twice and fallen 40% below its high for the first time in January
2018; its worst fall was 72%. A 40% limit will stop this strategy sooner or
later, and clearing the stop is then your decision.

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
