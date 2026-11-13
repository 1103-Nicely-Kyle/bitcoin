"""The acceptance rule: is a new idea's lead bigger than luck?

A strategy can score higher than buy-and-hold just by chance, and the more
ideas you try, the more likely it is that one of them does. This file decides
whether a lead is real enough to keep. It works in three steps:

  1. LEAD.  The candidate's Sharpe minus the baseline's Sharpe, over the same days.

  2. NOISE. How much that lead moves around by luck. To measure it, the
     history is cut into 30-day chunks, the chunks are drawn at random to
     build thousands of alternative histories, and the lead is re-measured
     on each one. The spread of those leads is the noise.

  3. BAR.   The lead divided by the noise has to clear a bar. The bar starts
     at 1.64 for the first idea ever tried and rises with every experiment
     in the log: 2.33 after 5, 2.58 after 10, 3.29 after 100.

The candidate has to clear the bar against EVERY baseline, not just one.
"""

from statistics import NormalDist

import numpy as np

import config
from backtest import count_experiments


def sharpe_of(returns):
    """Sharpe for each row of daily returns (one row = one history)."""
    returns = np.atleast_2d(returns)
    mean = returns.mean(axis=1)
    spread = returns.std(axis=1, ddof=1)
    score = np.divide(mean, spread, out=np.zeros_like(mean), where=spread > 0)
    return score * np.sqrt(config.PERIODS_PER_YEAR)


def required_ratio(trials, alpha=None):
    """The bar: how many times bigger than the noise a lead must be.

    It rises with `trials`, the number of experiments tried so far, so that
    the chance of accepting ANY idea by luck stays at `alpha` in total.
    """
    alpha = config.ACCEPT_ALPHA if alpha is None else alpha
    return NormalDist().inv_cdf(1 - alpha / max(1, trials))


def compare(candidate, baseline, block_days=None, resamples=None, seed=0):
    """Measure the candidate's lead over one baseline, and the noise in that lead.

    Both arguments are daily returns over the same days.
    """
    block_days = config.ACCEPT_BLOCK_DAYS if block_days is None else block_days
    resamples = config.ACCEPT_RESAMPLES if resamples is None else resamples
    if not candidate.index.equals(baseline.index):
        raise ValueError("The candidate and the baseline must cover exactly the same days.")

    ours = candidate.to_numpy(dtype=float)
    theirs = baseline.to_numpy(dtype=float)
    days = len(ours)
    lead = float(sharpe_of(ours)[0] - sharpe_of(theirs)[0])

    # Build the alternative histories. Each is made of 30-day chunks starting
    # at random days (wrapping round at the end). The SAME days are used for
    # the candidate and the baseline, so a day that was bad for both stays
    # bad for both.
    rng = np.random.default_rng(seed)
    blocks = -(-days // block_days)                      # rounded up
    starts = rng.integers(0, days, size=(resamples, blocks))
    picked = (starts[:, :, None] + np.arange(block_days)) % days
    picked = picked.reshape(resamples, -1)[:, :days]

    leads = sharpe_of(ours[picked]) - sharpe_of(theirs[picked])
    noise = float(leads.std(ddof=1))
    ratio = lead / noise if noise > 0 else 0.0
    return {"lead": lead, "noise": noise, "ratio": float(ratio)}


def judge(candidate, baselines, trials=None, **settings):
    """Decide whether a candidate is accepted.

    candidate: its daily returns
    baselines: {name: daily returns} - the candidate must beat every one
    trials:    experiments tried so far (default: the number of lines in the log)
    """
    trials = count_experiments() if trials is None else trials
    required = required_ratio(trials)
    comparisons = {name: compare(candidate, baseline, **settings)
                   for name, baseline in baselines.items()}
    accepted = all(result["ratio"] >= required for result in comparisons.values())
    return {"accepted": accepted, "trials": trials, "required": required,
            "comparisons": comparisons}


def explain(name, verdict):
    """Turn a verdict into a few readable lines."""
    lines = [f"{name}: {'ACCEPTED' if verdict['accepted'] else 'REJECTED'}"]
    for baseline, result in verdict["comparisons"].items():
        passed = "pass" if result["ratio"] >= verdict["required"] else "fail"
        lines.append(f"  vs {baseline:<28} lead {result['lead']:+.2f}   noise {result['noise']:.2f}   "
                     f"lead/noise {result['ratio']:+.2f}   needs {verdict['required']:.2f}   {passed}")
    return "\n".join(lines)
