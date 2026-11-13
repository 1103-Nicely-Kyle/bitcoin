"""Paper trading: run a strategy on real prices as they arrive, with pretend money.

    python paper_trade.py             download the newest prices and process any new days
    python paper_trade.py --no-fetch  the same, using the prices already on disk
    python paper_trade.py --resume    clear a stop made by a risk limit, then carry on

Run it once a day, or less often: it catches up on every day it missed, one
at a time, exactly as if it had been run each day.

What happens for each new day, in this order:

  1. The account is revalued at that day's closing price.
  2. The risk limits are checked. If one is broken, the account is stopped.
  3. The strategy is shown prices up to that day and says what it wants.
  4. The limits in risk_limits.py have the final say on the position.
  5. The change in position is "traded" at the close, paying fee and slippage.

No real order is ever placed. The account starts on the day of the first run
and only moves forward from there. It never trades the past.
"""

import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd

import config
import risk_limits
from backtest import load_all_data
from strategies import BASELINES

ACCOUNT_FILE = "account.json"
RECORD_FILE = "record.csv"
RECORD_COLUMNS = ["date", "close", "wanted", "position", "traded", "day_return", "equity", "notes"]


def new_account(strategy_name, start_cash=None):
    start_cash = config.PAPER_START_CASH if start_cash is None else start_cash
    return {
        "strategy": strategy_name,
        "started": None,          # the first day processed
        "start_cash": start_cash,
        "start_close": None,      # bitcoin's price on that first day
        "equity": start_cash,     # what the account is worth now
        "peak": start_cash,       # the most it has been worth since starting (or since a resume)
        "position": 0.0,          # share of the account in bitcoin
        "last_day": None,         # the newest day processed
        "stopped": None,          # None, or the reason a risk limit stopped the account
    }


def process_day(account, day, close, previous_close, wanted, kill_switch_on, cost_per_trade=None):
    """Move the account forward by one day. Returns the line for the record."""
    cost_per_trade = config.FEE + config.SLIPPAGE if cost_per_trade is None else cost_per_trade
    notes = []

    # 1. Revalue at today's close.
    price_change = close / previous_close - 1 if previous_close else 0.0
    day_return = account["position"] * price_change
    equity = account["equity"] * (1 + day_return)
    peak = max(account["peak"], equity)

    # 2. Check the limits. A stop stays in place until a person resumes.
    if not account["stopped"]:
        reasons = risk_limits.reasons_to_stop(day_return, equity, peak, price_change)
        if reasons:
            account["stopped"] = f"{day.date()}: " + "; ".join(reasons)
            notes.append("STOPPED: " + "; ".join(reasons))

    # 3 and 4. What the strategy wants, then what the limits allow.
    position = risk_limits.limit_position(wanted)
    if position != wanted:
        notes.append(f"wanted {wanted} was limited to {position}")
    if account["stopped"]:
        position = 0.0
        if not notes:
            notes.append("stopped by a risk limit")
    if kill_switch_on:
        position = 0.0
        notes.append("kill switch is on")

    # 5. Trade the difference at the close and pay for it.
    traded = abs(position - account["position"])
    equity *= 1 - traded * cost_per_trade

    account.update({"equity": equity, "peak": peak, "position": position,
                    "last_day": str(day.date())})
    if account["started"] is None:
        account.update({"started": str(day.date()), "start_close": float(close)})

    return {"date": str(day.date()), "close": float(close), "wanted": wanted, "position": position,
            "traded": traded, "day_return": day_return, "equity": equity, "notes": " | ".join(notes)}


def process_new_days(account, prices, strategy, params, kill_switch_on=False, cost_per_trade=None):
    """Process every day in `prices` that the account has not seen yet.

    A brand-new account starts on the newest day only. Each day, the strategy
    is shown the prices up to that day and nothing later.
    """
    if account["last_day"] is None:
        new_days = prices.index[-1:]
    else:
        new_days = prices.index[prices.index > pd.Timestamp(account["last_day"])]

    lines = []
    for day in new_days:
        history = prices.loc[:day]
        previous_close = history["close"].iloc[-2] if account["last_day"] is not None else None
        wanted = float(strategy(history, **params).iloc[-1])
        lines.append(process_day(account, day, history["close"].iloc[-1], previous_close,
                                 wanted, kill_switch_on, cost_per_trade))
    return lines


def resume(account):
    """Clear a stop. The highest value is reset so the same fall does not stop it again at once."""
    account["stopped"] = None
    account["peak"] = account["equity"]


# --- Saving and loading -----------------------------------------------------

def load_account(folder, strategy_name):
    path = os.path.join(folder, ACCOUNT_FILE)
    if not os.path.exists(path):
        return new_account(strategy_name)
    with open(path) as file:
        account = json.load(file)
    if account["strategy"] != strategy_name:
        raise ValueError(
            f"This paper account was started with '{account['strategy']}', but config.py now "
            f"says '{strategy_name}'. A record must follow one strategy. To start a fresh "
            f"record, move or delete the '{folder}' folder.")
    return account


def save(folder, account, lines):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, ACCOUNT_FILE), "w") as file:
        json.dump(account, file, indent=2)
    if lines:
        path = os.path.join(folder, RECORD_FILE)
        pd.DataFrame(lines, columns=RECORD_COLUMNS).to_csv(
            path, mode="a", index=False, header=not os.path.exists(path))


# --- The command ------------------------------------------------------------

def main():
    name = config.PAPER_STRATEGY
    if name not in BASELINES:
        raise SystemExit(f"'{name}' is not a baseline in strategies.py. "
                         f"Choose one of: {', '.join(BASELINES)}.")
    strategy, params, _ = BASELINES[name]

    if "--no-fetch" not in sys.argv:
        import fetch_data
        print("Downloading the newest prices...")
        fetch_data.update()
    prices = load_all_data()

    account = load_account(config.PAPER_FOLDER, name)
    if "--resume" in sys.argv:
        if account["stopped"]:
            print(f"Resuming. The account had been stopped: {account['stopped']}")
            resume(account)
        else:
            print("Nothing to resume: the account was not stopped.")

    kill_switch_on = risk_limits.kill_switch_is_on()
    lines = process_new_days(account, prices, strategy, params, kill_switch_on)
    save(config.PAPER_FOLDER, account, lines)

    newest = prices.index[-1]
    print(f"\nPaper trading '{name}' with pretend money. Started {account['started']}.")
    print(f"Prices up to {newest.date()}: bitcoin closed at ${prices['close'].iloc[-1]:,.2f}.")
    print(f"New days processed: {len(lines)}.")
    for line in lines:
        if line["notes"]:
            print(f"  {line['date']}: {line['notes']}")

    change = account["equity"] / account["start_cash"] - 1
    cost = config.FEE + config.SLIPPAGE
    held = (1 - cost) * prices["close"].iloc[-1] / account["start_close"] - 1
    print(f"\nAccount: ${account['equity']:,.2f} ({change:+.2%} since the start). "
          f"Buying and holding from the same day: {held:+.2%}.")
    print(f"Position now: {account['position']:.0%} bitcoin, {1 - account['position']:.0%} cash.")

    if account["stopped"]:
        print(f"\nSTOPPED by a risk limit on {account['stopped']}")
        print("The position stays at zero until you run: python paper_trade.py --resume")
    if kill_switch_on:
        print(f"\nKILL SWITCH IS ON: the file '{risk_limits.KILL_SWITCH_FILE}' exists. "
              f"The position stays at zero until you delete it.")
    if risk_limits.data_is_stale(newest.date(), datetime.now(timezone.utc).date()):
        print(f"\nWARNING: the newest price is from {newest.date()}, which is out of date. "
              f"Do not act on the position shown above.")
    if not (account["stopped"] or kill_switch_on):
        print("Risk limits: all clear.")


if __name__ == "__main__":
    main()
