"""Phase 3 backtesting engine — event study methodology.

Feed it a CSV of historical headlines (historical_events.csv):

    timestamp,headline,source
    2025-06-01T13:30:00Z,"Drone strikes disrupt output at major Gulf oil terminal",Reuters

For each headline it runs the Phase 1 Gemini classification, maps the top
sector to a liquid sector ETF (clean measurement — no single-stock noise),
pulls prices via yfinance, and scores directional correctness at T+1hr and
T+1day.

Gate: >= 55% T+1day accuracy on >= 100 events before paper trading.
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from correlations import (
    REQUEST_SPACING_S, TAXONOMY_FILE, ClassificationError, classify_headline, load_json,
)

CSV_FILE = "historical_events.csv"
RESULTS_FILE = "backtest_results.json"
MIN_EVENTS_FOR_GATE = 100
ACCURACY_GATE_PCT = 55.0

SECTOR_ETF = {
    "Technology": "QQQ",
    "Basic Materials": "XLB",
    "Utilities": "XLU",
    "Consumer Goods": "XLY",
    "Health Care": "XLV",
    "Financial": "XLF",
    "Industrial Goods": "XLI",
    "Services": "XLY",
    "Modern & Digital": "QQQ",
}

# More specific overrides when the top sub-industry is unambiguous
SUB_INDUSTRY_ETF = {
    "Major Integrated Oil & Gas": "XLE",
    "Independent Oil & Gas": "XLE",
    "Oil & Gas Drilling & Exploration": "XLE",
    "Oil & Gas Equipment & Services": "XLE",
    "Oil & Gas Pipelines": "XLE",
    "Oil & Gas Refining & Marketing": "XLE",
    "Aerospace/Defense—Major Diversified": "ITA",
    "Aerospace/Defense Products & Services": "ITA",
    "Semiconductor—Broad Line": "SOXX",
    "Semiconductor—Integrated Circuits": "SOXX",
    "Semiconductor—Equipment & Materials": "SOXX",
    "Semiconductor—Specialized": "SOXX",
}


def pick_etf(top_industry):
    return SUB_INDUSTRY_ETF.get(top_industry["sub_industry"]) or SECTOR_ETF.get(top_industry["sector"])


def daily_prices(ticker, start, end):
    import yfinance as yf

    hist = yf.Ticker(ticker).history(start=start, end=end, interval="1d")
    return hist


def measure(ticker, event_time):
    """Return (pct_1hr, pct_1day) using daily bars.

    Historical 1-minute data is not available on yfinance beyond ~30 days, so
    for backtests the T+1hr window uses same-day open->close as a proxy and
    T+1day uses close->next close (or next open->close for after-hours news).
    """
    hist = daily_prices(ticker, event_time - timedelta(days=5), event_time + timedelta(days=7))
    if hist.empty:
        return None, None
    hist = hist.tz_convert("UTC") if hist.index.tz else hist.tz_localize("UTC")
    after = hist[hist.index >= event_time - timedelta(hours=16)]
    if len(after) < 2:
        return None, None
    day0, day1 = after.iloc[0], after.iloc[1]
    base = float(day0["Open"]) if event_time.hour < 14 else float(day0["Close"])
    pct_1hr = (float(day0["Close"]) - float(day0["Open"])) / float(day0["Open"]) * 100
    pct_1day = (float(day1["Close"]) - base) / base * 100
    return round(pct_1hr, 2), round(pct_1day, 2)


def main():
    if not os.path.exists(CSV_FILE):
        print(f"{CSV_FILE} not found.")
        print("Create it with columns: timestamp,headline,source — then re-run.")
        print("Example row: 2025-06-01T13:30:00Z,\"Oil terminal attacked\",Reuters")
        return

    taxonomy = load_json(TAXONOMY_FILE, None)
    if taxonomy is None:
        sys.exit("taxonomy.json missing")
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY not set")

    results = []
    with open(CSV_FILE, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"[backtest] {len(rows)} historical events loaded")
    for i, row in enumerate(rows, 1):
        if i > 1:
            time.sleep(REQUEST_SPACING_S)
        headline = row["headline"].strip()
        event_time = datetime.strptime(row["timestamp"].strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        try:
            summary, industries = classify_headline(headline, row.get("source", "backtest"), taxonomy)
        except ClassificationError as e:
            print(f"[{i}/{len(rows)}] classify failed: {e}")
            continue
        if not industries:
            print(f"[{i}/{len(rows)}] no industries: {headline[:60]}")
            continue
        top = industries[0]
        etf = pick_etf(top)
        if not etf:
            continue
        pct_1hr, pct_1day = measure(etf, event_time)
        if pct_1day is None:
            print(f"[{i}/{len(rows)}] no price data for {etf}: {headline[:60]}")
            continue
        results.append({
            "timestamp": row["timestamp"].strip(),
            "headline": headline,
            "sector": top["sector"],
            "sub_industry": top["sub_industry"],
            "confidence": top["confidence"],
            "etf": etf,
            "pct_1hr": pct_1hr,
            "pct_1day": pct_1day,
            "correct_1hr": pct_1hr is not None and pct_1hr > 0,
            "correct_1day": pct_1day > 0,
        })
        print(f"[{i}/{len(rows)}] {etf} 1d {pct_1day:+.2f}% conf {top['confidence']} — {headline[:50]}")

    if not results:
        sys.exit("No measurable events — check CSV timestamps and tickers.")

    n = len(results)
    acc_1hr = sum(r["correct_1hr"] for r in results) / n * 100
    acc_1day = sum(r["correct_1day"] for r in results) / n * 100

    # Accuracy by confidence bucket — shows whether confidence is calibrated
    buckets = {}
    for r in results:
        b = f"{r['confidence'] // 20 * 20}-{r['confidence'] // 20 * 20 + 19}"
        buckets.setdefault(b, []).append(r["correct_1day"])
    bucket_acc = {b: round(sum(v) / len(v) * 100, 1) for b, v in sorted(buckets.items())}

    report = {
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "events_measured": n,
        "accuracy_1hr_pct": round(acc_1hr, 1),
        "accuracy_1day_pct": round(acc_1day, 1),
        "accuracy_by_confidence_1day": bucket_acc,
        "gate_pct": ACCURACY_GATE_PCT,
        "gate_min_events": MIN_EVENTS_FOR_GATE,
        "gate_passed": n >= MIN_EVENTS_FOR_GATE and acc_1day >= ACCURACY_GATE_PCT,
        "results": results,
    }
    with open(RESULTS_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print("\n========== BACKTEST REPORT ==========")
    print(f"Events measured : {n}")
    print(f"T+1hr accuracy  : {acc_1hr:.1f}%")
    print(f"T+1day accuracy : {acc_1day:.1f}%")
    print(f"By confidence   : {bucket_acc}")
    if report["gate_passed"]:
        print(f"GATE PASSED — >= {ACCURACY_GATE_PCT}% on >= {MIN_EVENTS_FOR_GATE} events. Proceed to paper trading.")
    elif n < MIN_EVENTS_FOR_GATE:
        print(f"GATE NOT EVALUATED — need >= {MIN_EVENTS_FOR_GATE} events (have {n}).")
    else:
        print(f"GATE FAILED — {acc_1day:.1f}% < {ACCURACY_GATE_PCT}%. Retune prompt/taxonomy and re-run.")


if __name__ == "__main__":
    main()
