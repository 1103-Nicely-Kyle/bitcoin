"""The queue of ideas for the improvement loop.

Each proposal is ONE idea. To try a new idea, add a proposal to the END of
this list and run:

    python improve.py

The rules for proposing (the loop checks the ones it can):

  1. One change per proposal, and a written reason for why it should work
     in the real world - not "it scored well".
  2. Write the proposal BEFORE looking at how it scores.
  3. Never edit or delete a proposal that has been tested. If an idea needs
     adjusting, that is a new proposal, and it counts as a new experiment.
  4. Keep the list of settings ("grid") short. Walk-forward picks between
     them using only past data.

Fields:
  name        a unique label
  hypothesis  why this should work
  strategy    a function from strategies.py
  grid        the settings to choose between ([{}] if there is nothing to choose)
  warmup      the longest look-back any setting needs, in days
"""

from strategies import ma_crossover, trend_blend, trend_buffer, trend_filter, vol_target

PROPOSALS = [
    {
        "name": "wf_trend_filter",
        "hypothesis": "The best trend length changes over time; re-choosing it each year helps.",
        "strategy": trend_filter,
        "grid": [{"window": window} for window in (50, 100, 150, 200, 250, 300)],
        "warmup": 300,
    },
    {
        "name": "wf_ma_crossover",
        "hypothesis": "The best pair of averages changes over time; re-choosing it each year helps.",
        "strategy": ma_crossover,
        "grid": [{"fast": fast, "slow": slow}
                 for fast in (20, 50, 100) for slow in (100, 200, 300) if fast < slow],
        "warmup": 300,
    },
    {
        "name": "trend_buffer",
        "hypothesis": (
            "The trend filter made 91 trades at 0.45% each, and many were quick in-and-out "
            "flips while the price hovered at its average. Those flips carry no information "
            "about the trend. Requiring the price to clear the average by a margin before "
            "acting should remove them and keep the big moves."
        ),
        "strategy": trend_buffer,
        "grid": [{"window": window, "band": band}
                 for window in (100, 200) for band in (0.03, 0.06, 0.10)],
        "warmup": 200,
    },
    {
        "name": "vol_target",
        "hypothesis": (
            "Bitcoin's wild stretches cluster together, and its worst falls happen inside "
            "them, but the extra risk in those stretches has not been matched by extra "
            "return. Holding less when recent swings are large and more when they are small "
            "should give a steadier ride for a similar reward."
        ),
        "strategy": vol_target,
        "grid": [{"target": target, "lookback": lookback}
                 for target in (0.4, 0.6, 0.8) for lookback in (30, 60)],
        "warmup": 60,
    },
    {
        "name": "trend_blend",
        "hypothesis": (
            "Walk-forward showed that the trend length which worked best in the past says "
            "nothing about which will work next. So stop choosing: let six trend lengths "
            "vote and hold the share that say 'hold'. Spreading across lengths should avoid "
            "the damage from any one length being wrong, and scaling in and out in steps "
            "should soften the all-or-nothing flips."
        ),
        "strategy": trend_blend,
        "grid": [{}],
        "warmup": 300,
    },
]
