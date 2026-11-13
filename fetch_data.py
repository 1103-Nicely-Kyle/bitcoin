"""Download daily BTC-USD candles from Coinbase's public API.

No account or API key is needed. Run:

    python fetch_data.py

The result is saved to data/btc_usd_daily.csv.
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

import pandas as pd

import config

API_URL = "https://api.exchange.coinbase.com/products/{product}/candles"
MAX_CANDLES_PER_REQUEST = 300   # Coinbase's limit


def fetch_window(start, end):
    """Ask Coinbase for the candles between two datetimes. Returns raw rows."""
    query = urllib.parse.urlencode({
        "granularity": config.GRANULARITY,
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    url = API_URL.format(product=config.PRODUCT) + "?" + query
    request = urllib.request.Request(url, headers={"User-Agent": "btc-research-harness"})

    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            # 429 = too many requests, 5xx = their problem. Both are worth a retry.
            if error.code != 429 and error.code < 500:
                raise
        except urllib.error.URLError:
            pass
        time.sleep(2 ** attempt)
    raise RuntimeError(f"Coinbase did not answer after 5 tries: {url}")


def rows_to_frame(rows, now=None):
    """Turn Coinbase's raw rows into a clean table, oldest day first.

    Coinbase sends each row as [time, low, high, open, close, volume], newest
    first. The candle for today is still changing, so it is dropped.
    """
    frame = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    frame["date"] = pd.to_datetime(frame["time"], unit="s", utc=True).dt.tz_localize(None)
    frame = frame.drop_duplicates("date").sort_values("date").set_index("date")
    frame = frame[["open", "high", "low", "close", "volume"]].astype(float)

    now = now or datetime.now(timezone.utc)
    today = pd.Timestamp(now.date())
    return frame[frame.index < today]


def download():
    start = datetime.strptime(config.START_DATE, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    step = timedelta(seconds=config.GRANULARITY * (MAX_CANDLES_PER_REQUEST - 1))

    rows = []
    while start < now:
        end = min(start + step, now)
        rows.extend(fetch_window(start, end))
        print(f"  fetched {start.date()} to {end.date()}")
        start = end + timedelta(seconds=config.GRANULARITY)
        time.sleep(0.25)   # be polite to the API

    return rows_to_frame(rows, now)


def main():
    print(f"Downloading {config.PRODUCT} daily candles from Coinbase...")
    frame = download()
    os.makedirs(os.path.dirname(config.DATA_PATH), exist_ok=True)
    frame.to_csv(config.DATA_PATH)
    print(f"Saved {len(frame)} days ({frame.index[0].date()} to {frame.index[-1].date()}) "
          f"to {config.DATA_PATH}")

    gaps = pd.date_range(frame.index[0], frame.index[-1]).difference(frame.index)
    if len(gaps):
        print(f"Note: {len(gaps)} days are missing from Coinbase's history "
              f"(first: {gaps[0].date()}). The backtester steps straight across each gap.")


if __name__ == "__main__":
    main()
