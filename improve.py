"""The improvement loop.

    python improve.py            test anything new, then show where everything stands
    python improve.py --folds    the same, plus the year-by-year detail for every idea

One cycle of the loop is:

  1. PROPOSE  Someone adds one idea, with a reason, to proposals.py.
  2. CHECK    The loop refuses the idea if it uses prices from the future.
  3. TEST     The idea is scored by walk-forward on the research data.
  4. LOG      The test is added to experiments.jsonl. This raises the bar.
  5. JUDGE    EVERY idea tried so far is judged again at the new bar.
  6. KEEP     The champion is the best idea that still clears the bar.
              If none does, there is no champion.

Because step 5 re-judges everything, an idea that was the champion can lose
that title as more ideas are tried. That is deliberate: the more you search,
the less any one result proves.

The loop never sees the holdout data, and it cannot change the fees, the
bar, or the engine: those live in other files.
"""

import sys

import numpy as np
import pandas as pd

import config
from acceptance import explain, judge, required_ratio
from backtest import count_experiments, load_research_data, log_experiment, summarize
from proposals import PROPOSALS
from strategies import BASELINES
from walk_forward import score_fixed, walk_forward


# --- Step 2: checks ---------------------------------------------------------

def check_proposals(proposals):
    """Stop early if the proposal list itself breaks the rules."""
    names = [proposal.get("name") for proposal in proposals]
    for proposal in proposals:
        name = proposal.get("name")
        if not name or names.count(name) > 1:
            raise ValueError(f"Every proposal needs its own unique name (problem: {name!r}).")
        if name in BASELINES:
            raise ValueError(f"'{name}' is the name of a baseline. Pick another name.")
        if len(str(proposal.get("hypothesis", "")).strip()) < 40:
            raise ValueError(f"'{name}' needs a written reason (hypothesis) of at least a sentence.")
        if not callable(proposal.get("strategy")) or not proposal.get("grid"):
            raise ValueError(f"'{name}' needs a strategy function and a non-empty grid.")


def find_peeking(strategy, grid, prices):
    """Check that a strategy only uses prices up to each day.

    The strategy is run on the full history and again on histories that stop
    early. If the early days come out differently when later days exist, the
    strategy is using the future. Returns a description of the problem, or
    None if there isn't one.
    """
    days = len(prices)
    cuts = sorted({days // 3, days // 2, (2 * days) // 3, days - 37, days - 1})
    for params in grid:
        try:
            full = strategy(prices, **params)
        except Exception as error:               # a broken strategy is refused, not a crash
            return f"it failed to run with {params}: {error}"
        if not isinstance(full, pd.Series) or not full.index.equals(prices.index):
            return f"with {params} it did not return one position per day"
        for cut in cuts:
            if cut < 2:
                continue
            early = strategy(prices.iloc[:cut], **params)
            if not np.allclose(early.to_numpy(dtype=float), full.iloc[:cut].to_numpy(dtype=float),
                               equal_nan=True):
                return (f"with {params}, its positions before {prices.index[cut].date()} "
                        f"change depending on prices after that date")
    return None


# --- Steps 3 to 6 -----------------------------------------------------------

def run_loop(prices, proposals=PROPOSALS, baselines=BASELINES, log_path=None):
    """Run the loop over every proposal and return where everything stands."""
    check_proposals(proposals)
    span = prices.index[config.WF_MIN_TRAIN_DAYS:]

    baseline_results = {name: score_fixed(prices, strategy, params)
                        for name, (strategy, params, _) in baselines.items()}

    tested, refused = {}, {}
    for proposal in proposals:
        name = proposal["name"]

        problem = find_peeking(proposal["strategy"], proposal["grid"], prices)
        if problem:
            refused[name] = problem
            continue

        result, folds = walk_forward(prices, proposal["strategy"], proposal["grid"],
                                     warmup=proposal.get("warmup", 0))
        metrics = summarize(result)
        is_new = log_experiment(name, {
            "grid": proposal["grid"],
            "objective": config.OBJECTIVE,
            "min_train_days": config.WF_MIN_TRAIN_DAYS,
            "test_days": config.WF_TEST_DAYS,
            "scored_from": str(span[0].date()),
            "scored_to": str(span[-1].date()),
        }, proposal["hypothesis"], metrics, path=log_path)
        tested[name] = {"result": result, "folds": folds, "metrics": metrics, "is_new": is_new}

    # Everything is judged at the same bar, set by the total number of
    # experiments in the log - including the ones just added.
    trials = count_experiments(log_path)
    baseline_returns = {name: result["return"] for name, result in baseline_results.items()}
    for entry in tested.values():
        entry["verdict"] = judge(entry["result"]["return"], baseline_returns, trials=trials)

    accepted = [name for name, entry in tested.items() if entry["verdict"]["accepted"]]
    champion = max(accepted, key=lambda name: tested[name]["metrics"]["sharpe"]) if accepted else None

    return {"span": span, "baselines": baseline_results, "tested": tested, "refused": refused,
            "trials": trials, "required": required_ratio(trials), "champion": champion}


# --- Printing ---------------------------------------------------------------

def describe(params):
    return ", ".join(f"{key}={value}" for key, value in params.items()) or "(nothing to choose)"


def fold_table(folds):
    return pd.DataFrame({
        "test period": [f"{a.date()} to {b.date()}"
                        for a, b in zip(folds["test_start"], folds["test_end"])],
        "chosen": folds["params"].map(describe),
        "score before": folds["train_score"].map("{:.2f}".format),
        "score after": folds["test_score"].map("{:.2f}".format),
    }).to_string(index=False)


def leaderboard(state):
    rows = []
    for name, result in state["baselines"].items():
        rows.append({"name": name, **summarize(result), "weakest": None, "status": "baseline"})
    for name, entry in state["tested"].items():
        weakest = min(c["ratio"] for c in entry["verdict"]["comparisons"].values())
        status = "ACCEPTED" if entry["verdict"]["accepted"] else "rejected"
        rows.append({"name": name, **entry["metrics"], "weakest": weakest, "status": status})

    table = pd.DataFrame(rows).set_index("name")
    return pd.DataFrame({
        "sharpe": table["sharpe"].map("{:.2f}".format),
        "per year": table["yearly_return"].map("{:.1%}".format),
        "worst drop": table["max_drawdown"].map("{:.1%}".format),
        "trades": table["trades"].astype(int),
        "in market": table["time_in_market"].map("{:.0%}".format),
        "lead/noise": table["weakest"].map(lambda value: "" if pd.isna(value) else f"{value:+.2f}"),
        "status": table["status"],
    }).rename_axis(None).to_string()


def main():
    show_all_folds = "--folds" in sys.argv
    prices = load_research_data()
    state = run_loop(prices)
    span = state["span"]

    print(f"Research data: {prices.index[0].date()} to {prices.index[-1].date()}. "
          f"Holdout from {config.HOLDOUT_START} is locked.")
    print(f"Scored span: {span[0].date()} to {span[-1].date()} ({len(span)} days). "
          f"Costs: {config.FEE:.2%} fee + {config.SLIPPAGE:.2%} slippage per trade.")

    new = [name for name, entry in state["tested"].items() if entry["is_new"]]
    print(f"\nNew this run: {', '.join(new) if new else 'nothing (no untested proposals)'}")

    for name, problem in state["refused"].items():
        print(f"\nREFUSED {name}: {problem}. It was not scored or logged.")

    for name, entry in state["tested"].items():
        if entry["is_new"] or show_all_folds:
            print(f"\n{name}: settings chosen each period, and how they scored before and after")
            print(fold_table(entry["folds"]))

    print(f"\nWhere everything stands (lead/noise is against the toughest baseline):")
    print(leaderboard(state))

    print(f"\nThe bar: with {state['trials']} experiments logged, a lead must be at least "
          f"{state['required']:.2f} times its own noise, against every baseline.")
    for name, entry in state["tested"].items():
        if entry["is_new"] or entry["verdict"]["accepted"]:
            print(explain(name, entry["verdict"]))

    if state["champion"]:
        print(f"\nChampion: {state['champion']}")
    else:
        print("\nChampion: none. Nothing has cleared the bar.")


if __name__ == "__main__":
    main()
