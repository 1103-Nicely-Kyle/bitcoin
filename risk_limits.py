"""The hard limits. These sit between any strategy and the account.

Nothing in the research code (strategies, proposals, the improvement loop)
reads or writes this file. A strategy only ever says what position it WANTS;
the runner passes that through here before anything happens.

These numbers are yours to set. They say how much you are prepared to lose,
which no backtest can decide for you. Change them here, by hand, and nowhere
else.
"""

import math
import os

# The most of the account that may be in bitcoin. 1.0 = all of it.
# Never above 1.0: that would mean borrowing. Never below 0: no betting on falls.
MAX_POSITION = 1.0

# If the account loses this much in a single day, sell everything and stop.
MAX_DAILY_LOSS = 0.15        # 15%

# If the account falls this far below its highest value, sell everything and stop.
MAX_DRAWDOWN = 0.40          # 40%

# If the price moves this much in one day, assume the data is wrong and stop.
# (Bitcoin's largest one-day move in the history used here was 39%.)
MAX_PRICE_JUMP = 0.50        # 50%

# If the newest price is older than this many days, do not act on it.
MAX_DATA_AGE_DAYS = 1

# The kill switch. While a file with this name exists in this folder, the
# position is forced to zero. Create it to stop; delete it to carry on.
KILL_SWITCH_FILE = "KILL_SWITCH"


def limit_position(wanted):
    """Squeeze whatever a strategy asks for into the allowed range."""
    try:
        wanted = float(wanted)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(wanted):
        return 0.0
    return min(max(wanted, 0.0), MAX_POSITION)


def reasons_to_stop(day_return, equity, peak_equity, price_change):
    """Check the account after a day. Returns the reasons to stop (empty = carry on)."""
    reasons = []
    if abs(price_change) > MAX_PRICE_JUMP:
        reasons.append(f"the price moved {price_change:+.0%} in one day, more than "
                       f"{MAX_PRICE_JUMP:.0%}; the data may be wrong")
    if day_return <= -MAX_DAILY_LOSS:
        reasons.append(f"the account lost {-day_return:.1%} in one day, "
                       f"the limit is {MAX_DAILY_LOSS:.0%}")
    drawdown = equity / peak_equity - 1 if peak_equity > 0 else 0.0
    if drawdown <= -MAX_DRAWDOWN:
        reasons.append(f"the account is {-drawdown:.1%} below its highest value, "
                       f"the limit is {MAX_DRAWDOWN:.0%}")
    return reasons


def kill_switch_is_on(path=KILL_SWITCH_FILE):
    return os.path.exists(path)


def data_is_stale(newest_day, today):
    """True if the newest finished day in the data is too old to act on.

    Both arguments are dates. `today` is still in progress, so the newest
    finished day should be yesterday.
    """
    return (today - newest_day).days > MAX_DATA_AGE_DAYS
