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

## Before committing

Run all four test files: `test_backtest.py`, `test_walk_forward.py`,
`test_acceptance.py`, `test_improve.py`.

The user has basic Python. Keep code plain and comments in everyday words.
