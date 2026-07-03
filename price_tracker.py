"""Phase 3 outcome tracking: fill T+10min / T+1hr / T+1day / T+5day prices
for logged signals and recompute directional accuracy.

Used as a library by correlations.py and runnable standalone:
    python price_tracker.py
"""

import json
import sys
from datetime import datetime, timedelta, timezone

CHECKPOINTS = [
    ("price_t10min", timedelta(minutes=10)),
    ("price_t1hr", timedelta(hours=1)),
    ("price_t1day", timedelta(days=1)),
    ("price_t5day", timedelta(days=5)),
]

HISTORY_FILE = "history.json"


def _yf():
    import yfinance

    return yfinance


def current_prices(tickers):
    """Best-effort latest price per ticker. Missing tickers are simply absent."""
    prices = {}
    if not tickers:
        return prices
    yf = _yf()
    try:
        data = yf.download(
            list(set(tickers)), period="5d", interval="1d",
            progress=False, auto_adjust=True, group_by="ticker", threads=False,
        )
        for ticker in set(tickers):
            try:
                # Column layout differs by yfinance version: MultiIndex when
                # grouped by ticker, flat when a single ticker collapses.
                closes = data[ticker]["Close"] if ticker in data.columns.get_level_values(0) else data["Close"]
                closes = closes.dropna()
                if len(closes):
                    prices[ticker] = round(float(closes.iloc[-1]), 4)
            except (KeyError, TypeError):
                continue
    except Exception as e:  # noqa: BLE001
        print(f"[prices] batch download failed: {e}", file=sys.stderr)
    return prices


def price_at(ticker, when, market_hours):
    """Price of `ticker` at datetime `when` (UTC).

    Intraday (1-minute) data only exists for ~the last 7 days on yfinance, which
    is fine: this runs every 30 minutes, so checkpoints are always recent.
    For signals fired outside market hours, the next session's first trade is
    the correct measurement point — the first bar at/after `when` handles that.
    """
    yf = _yf()
    try:
        interval = "1m" if (datetime.now(timezone.utc) - when) < timedelta(days=6) else "1h"
        hist = yf.Ticker(ticker).history(
            start=when - timedelta(minutes=5),
            end=when + timedelta(days=4),
            interval=interval,
        )
        if hist.empty:
            return None
        target = when.astimezone(hist.index.tz) if hist.index.tz else when.replace(tzinfo=None)
        hist = hist[hist.index >= target]
        if hist.empty:
            return None
        return round(float(hist["Close"].iloc[0]), 4)
    except Exception as e:  # noqa: BLE001
        print(f"[prices] {ticker} @ {when}: {e}", file=sys.stderr)
        return None


def update_history(history):
    """Fill any due, still-null checkpoints and recompute the accuracy block."""
    now = datetime.now(timezone.utc)
    updated = 0
    for sig in history.get("signals", []):
        base = sig.get("price_at_signal")
        logged = datetime.strptime(sig["logged_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        for field, delta in CHECKPOINTS:
            if sig.get(field) is None and now >= logged + delta:
                price = price_at(sig["ticker"], logged + delta, sig.get("market_hours", True))
                if price is not None:
                    sig[field] = price
                    updated += 1
        if base:
            if sig.get("price_t1day") is not None and sig.get("outcome_1d") is None:
                sig["outcome_1d"] = round((sig["price_t1day"] - base) / base * 100, 2)
                sig["correct_1d"] = sig["outcome_1d"] > 0
            if sig.get("price_t5day") is not None and sig.get("outcome_5d") is None:
                sig["outcome_5d"] = round((sig["price_t5day"] - base) / base * 100, 2)
                sig["correct_5d"] = sig["outcome_5d"] > 0

    signals = history.get("signals", [])
    resolved_1d = [s for s in signals if s.get("correct_1d") is not None]
    resolved_5d = [s for s in signals if s.get("correct_5d") is not None]
    correct_1d = sum(1 for s in resolved_1d if s["correct_1d"])
    correct_5d = sum(1 for s in resolved_5d if s["correct_5d"])
    history["accuracy"] = {
        "total_signals": len(signals),
        "resolved_1d": len(resolved_1d),
        "correct_1d": correct_1d,
        "accuracy_1d_pct": round(correct_1d / len(resolved_1d) * 100, 1) if resolved_1d else None,
        "resolved_5d": len(resolved_5d),
        "correct_5d": correct_5d,
        "accuracy_5d_pct": round(correct_5d / len(resolved_5d) * 100, 1) if resolved_5d else None,
    }
    if updated:
        print(f"[tracker] filled {updated} price checkpoints")
    return history


def main():
    try:
        with open(HISTORY_FILE, encoding="utf-8") as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("history.json missing or invalid — nothing to track")
        return
    update_history(history)
    with open(HISTORY_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
        f.write("\n")
    acc = history["accuracy"]
    print(f"[tracker] 1d accuracy: {acc['accuracy_1d_pct']}% ({acc['resolved_1d']} resolved)")
    print(f"[tracker] 5d accuracy: {acc['accuracy_5d_pct']}% ({acc['resolved_5d']} resolved)")


if __name__ == "__main__":
    main()
