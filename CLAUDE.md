# Working in this repo

This is a research harness for bitcoin trading ideas. Its whole value is
that results are honest, so these rules outrank getting a good score.

## Running a cycle of the improvement loop

1. Add ONE proposal to the end of `proposals.py`, with a real-world reason
   in `hypothesis`. Put any new strategy function in `strategies.py`.
2. Develop and debug it on made-up prices only (see `test_improve.py`).
   Do not run it on the real data until it is finished.
3. Run `python improve.py` once. Report the result as it is.

## Never

- Never read data from `HOLDOUT_START` onward. Use `load_research_data()`.
  `load_holdout_data()` is for the user's one final check, at their request.
- Never edit or delete a tested proposal, or a line in `experiments.jsonl`.
  A tweak after seeing results is a new proposal.
- Never change `config.py`, `backtest.py`, `walk_forward.py` or
  `acceptance.py` to make an idea pass. Changes to those need the user's
  say-so and a reason that has nothing to do with any one idea's score.
- Never describe a rejected idea as promising because its Sharpe is higher.
  The acceptance rule is the verdict.

## Paper trading and risk limits

- Never change a value in `risk_limits.py`, run `paper_trade.py --resume`,
  or delete a `KILL_SWITCH` file unless the user asks for exactly that.
- Never import `risk_limits` or `paper_trade` from research code.
- Never edit `paper/record.csv` or `paper/account.json` by hand, and never
  start the paper account on a past date. After running `paper_trade.py`,
  commit the `paper/` folder so the record survives.
- This repo places no real orders. Adding real trading needs the user's
  explicit request.

## Before committing

Run all five test files: `test_backtest.py`, `test_walk_forward.py`,
`test_acceptance.py`, `test_improve.py`, `test_paper_trade.py`.

The user has basic Python. Keep code plain and comments in everyday words.
