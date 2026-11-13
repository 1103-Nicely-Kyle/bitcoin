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
