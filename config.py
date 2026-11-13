"""All the settings in one place.

Change numbers here, not inside the other files.
"""

# --- Market -----------------------------------------------------------------
PRODUCT = "BTC-USD"          # Coinbase product id
GRANULARITY = 86400          # seconds per candle (86400 = one day)
START_DATE = "2015-07-20"    # first day Coinbase has BTC-USD candles
PERIODS_PER_YEAR = 365       # bitcoin trades every day of the year

# --- Costs ------------------------------------------------------------------
# Charged every time the position changes, as a fraction of the amount traded.
# REPLACE THE FEE with what your exchange actually charges you.
FEE = 0.0040                 # 0.40% per trade (placeholder)
SLIPPAGE = 0.0005            # 0.05% per trade (price moves against you a bit)

# --- Holdout ----------------------------------------------------------------
# Everything from this date onward is locked away from research. It is used
# once, at the very end, to check a finished strategy. Do not move this date
# after you have looked at any results.
HOLDOUT_START = "2025-01-01"

# --- Files ------------------------------------------------------------------
DATA_PATH = "data/btc_usd_daily.csv"
EXPERIMENT_LOG = "experiments.jsonl"

# --- Walk-forward testing ---------------------------------------------------
# Settings are chosen on past data, then scored on the following stretch that
# was not used to choose them. Then the window moves forward and it repeats.
OBJECTIVE = "sharpe"         # the score used to choose settings (return per unit of risk)
WF_MIN_TRAIN_DAYS = 1095     # the first choice uses the first 3 years; later ones use everything so far
WF_TEST_DAYS = 365           # each choice is then scored on the next year

# --- Acceptance rule --------------------------------------------------------
# A new idea is only accepted if its lead over every baseline is clearly
# bigger than the lead that luck alone could produce.
ACCEPT_ALPHA = 0.05          # if no idea tried had any real edge, the chance that even one gets accepted
ACCEPT_BLOCK_DAYS = 30       # history is reshuffled in 30-day chunks to measure how much luck moves the score
ACCEPT_RESAMPLES = 2000      # how many reshuffled histories to try

# --- Paper trading ----------------------------------------------------------
# Pretend trading with pretend money, on real prices as they arrive.
# The hard limits on it are NOT here. They are in risk_limits.py.
PAPER_STRATEGY = "trend_filter_200"   # a baseline from strategies.py; a stand-in until there is a champion
PAPER_START_CASH = 10_000             # pretend dollars
PAPER_FOLDER = "paper"                # where the account and its day-by-day record are kept
