"""EDDY main pipeline: fetch news -> classify industries -> map tickers -> write JSON.

Runs inside GitHub Actions every 30 minutes. All output files are committed
back to the repo so the GitHub Pages PWA can read them.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import feedparser
import pytz
import requests

import price_tracker

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FEEDS = {
    "Reuters": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    "AP": "https://rsshub.app/apnews/topics/business",
    "CNBC": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
}
MAX_PER_FEED = 25

# Gemini free tier is 1,500 req/day; 48 runs/day * 20 = 960 keeps headroom.
MAX_NEW_PER_RUN = 20

MAX_EVENTS = 50
MAX_SEEN_IDS = 1000
MIN_CONFIDENCE = 20
NOTIFY_CONFIDENCE = 80  # ntfy.sh push threshold (Phase 4)

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")

EVENTS_FILE = "events.json"
PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "history.json"
TAXONOMY_FILE = "taxonomy.json"

SYSTEM_PROMPT = """You are a financial industry analyst. Given a news headline, identify every industry from the provided taxonomy that is materially affected by this event. You reason deeply — including second and third order effects. For example, if Apple raises iPhone prices, you consider not just consumer electronics but also semiconductor supply chains, app ecosystem revenue, consumer credit spending, and emerging market consumer demand.

Return ONLY a JSON object with this exact structure:
{
  "summary": "Two sentence factual summary of the event.",
  "industries": [
    {"sub_industry": "exact name from taxonomy", "sector": "exact sector name", "confidence": 85, "direction": "up"}
  ]
}

Rules:
- Only include industries with meaningful impact (confidence >= 20)
- direction is ALWAYS "up" (we are long-only)
- Use ONLY sub-industry names that appear exactly in the provided taxonomy
- Confidence 80-100: near-certain direct impact
- Confidence 60-79: likely direct impact
- Confidence 40-59: probable indirect impact
- Confidence 20-39: possible second-order effect
- Do not include any explanation outside the JSON object
- Do not wrap in markdown code blocks"""

INDUSTRY_TO_TICKERS = {
    "Major Integrated Oil & Gas": [
        {"ticker": "XOM", "name": "Exxon Mobil", "type": "stock"},
        {"ticker": "CVX", "name": "Chevron", "type": "stock"},
        {"ticker": "USO", "name": "US Oil Fund ETF", "type": "etf"},
    ],
    "Oil & Gas Drilling & Exploration": [
        {"ticker": "XOP", "name": "SPDR S&P Oil & Gas E&P ETF", "type": "etf"},
        {"ticker": "USO", "name": "US Oil Fund ETF", "type": "etf"},
    ],
    "Aerospace/Defense—Major Diversified": [
        {"ticker": "LMT", "name": "Lockheed Martin", "type": "stock"},
        {"ticker": "RTX", "name": "Raytheon Technologies", "type": "stock"},
        {"ticker": "ITA", "name": "iShares US Aerospace & Defense ETF", "type": "etf"},
    ],
    "Aerospace/Defense Products & Services": [
        {"ticker": "NOC", "name": "Northrop Grumman", "type": "stock"},
        {"ticker": "ITA", "name": "iShares US Aerospace & Defense ETF", "type": "etf"},
    ],
    "Semiconductor—Integrated Circuits": [
        {"ticker": "NVDA", "name": "Nvidia", "type": "stock"},
        {"ticker": "AMD", "name": "Advanced Micro Devices", "type": "stock"},
        {"ticker": "SOXX", "name": "iShares Semiconductor ETF", "type": "etf"},
    ],
    "Semiconductor—Broad Line": [
        {"ticker": "INTC", "name": "Intel", "type": "stock"},
        {"ticker": "SOXX", "name": "iShares Semiconductor ETF", "type": "etf"},
    ],
    "Semiconductor—Equipment & Materials": [
        {"ticker": "AMAT", "name": "Applied Materials", "type": "stock"},
        {"ticker": "LRCX", "name": "Lam Research", "type": "stock"},
        {"ticker": "SOXX", "name": "iShares Semiconductor ETF", "type": "etf"},
    ],
    "Drug Manufacturers—Major": [
        {"ticker": "LLY", "name": "Eli Lilly", "type": "stock"},
        {"ticker": "PFE", "name": "Pfizer", "type": "stock"},
        {"ticker": "XBI", "name": "SPDR Biotech ETF", "type": "etf"},
    ],
    "Biotechnology": [
        {"ticker": "LLY", "name": "Eli Lilly", "type": "stock"},
        {"ticker": "MRNA", "name": "Moderna", "type": "stock"},
        {"ticker": "XBI", "name": "SPDR Biotech ETF", "type": "etf"},
    ],
    "Drug Manufacturers—Other": [
        {"ticker": "NVO", "name": "Novo Nordisk ADR", "type": "adr"},
        {"ticker": "XBI", "name": "SPDR Biotech ETF", "type": "etf"},
    ],
    "Regional Airlines": [
        {"ticker": "JETS", "name": "US Global Jets ETF", "type": "etf"},
        {"ticker": "UAL", "name": "United Airlines", "type": "stock"},
        {"ticker": "DAL", "name": "Delta Air Lines", "type": "stock"},
    ],
    "Air Services": [
        {"ticker": "JETS", "name": "US Global Jets ETF", "type": "etf"},
    ],
    "Lodging": [
        {"ticker": "ABNB", "name": "Airbnb", "type": "stock"},
        {"ticker": "MAR", "name": "Marriott International", "type": "stock"},
        {"ticker": "BKNG", "name": "Booking Holdings", "type": "stock"},
    ],
    "Resorts & Casinos": [
        {"ticker": "WYNN", "name": "Wynn Resorts", "type": "stock"},
        {"ticker": "MGM", "name": "MGM Resorts", "type": "stock"},
    ],
    "Application Software": [
        {"ticker": "MSFT", "name": "Microsoft", "type": "stock"},
        {"ticker": "CRM", "name": "Salesforce", "type": "stock"},
        {"ticker": "IGV", "name": "iShares Expanded Tech-Software ETF", "type": "etf"},
    ],
    "Internet Software & Services": [
        {"ticker": "GOOGL", "name": "Alphabet", "type": "stock"},
        {"ticker": "META", "name": "Meta Platforms", "type": "stock"},
    ],
    "Electronic Equipment": [
        {"ticker": "AAPL", "name": "Apple Inc.", "type": "stock"},
        {"ticker": "QCOM", "name": "Qualcomm", "type": "stock"},
    ],
    "Money Center Banks": [
        {"ticker": "JPM", "name": "JPMorgan Chase", "type": "stock"},
        {"ticker": "BAC", "name": "Bank of America", "type": "stock"},
        {"ticker": "KBE", "name": "SPDR Bank ETF", "type": "etf"},
    ],
    "Asset Management": [
        {"ticker": "BLK", "name": "BlackRock", "type": "stock"},
        {"ticker": "GS", "name": "Goldman Sachs", "type": "stock"},
    ],
    "Gold": [
        {"ticker": "GLD", "name": "SPDR Gold Shares ETF", "type": "etf"},
        {"ticker": "NEM", "name": "Newmont Corporation", "type": "stock"},
    ],
    "Restaurants": [
        {"ticker": "MCD", "name": "McDonald's", "type": "stock"},
        {"ticker": "CMG", "name": "Chipotle Mexican Grill", "type": "stock"},
    ],
    "Grocery Stores": [
        {"ticker": "KR", "name": "Kroger", "type": "stock"},
        {"ticker": "WMT", "name": "Walmart", "type": "stock"},
    ],
    "Cloud Infrastructure & Services": [
        {"ticker": "AMZN", "name": "Amazon (AWS)", "type": "stock"},
        {"ticker": "MSFT", "name": "Microsoft (Azure)", "type": "stock"},
        {"ticker": "GOOGL", "name": "Alphabet (GCP)", "type": "stock"},
    ],
    "Electric Vehicles & Battery Technology": [
        {"ticker": "TSLA", "name": "Tesla", "type": "stock"},
        {"ticker": "LIT", "name": "Global X Lithium & Battery Tech ETF", "type": "etf"},
        {"ticker": "DRIV", "name": "Global X Autonomous & EV ETF", "type": "etf"},
    ],
    "AI & Machine Learning Infrastructure": [
        {"ticker": "NVDA", "name": "Nvidia", "type": "stock"},
        {"ticker": "AMD", "name": "Advanced Micro Devices", "type": "stock"},
        {"ticker": "BOTZ", "name": "Global X Robotics & AI ETF", "type": "etf"},
    ],
    "Cybersecurity": [
        {"ticker": "CRWD", "name": "CrowdStrike", "type": "stock"},
        {"ticker": "PANW", "name": "Palo Alto Networks", "type": "stock"},
        {"ticker": "CIBR", "name": "First Trust Nasdaq Cybersecurity ETF", "type": "etf"},
    ],
    "Social Media & Platforms": [
        {"ticker": "META", "name": "Meta Platforms", "type": "stock"},
        {"ticker": "SNAP", "name": "Snap Inc.", "type": "stock"},
    ],
    "Streaming & Digital Media": [
        {"ticker": "NFLX", "name": "Netflix", "type": "stock"},
        {"ticker": "DIS", "name": "Walt Disney", "type": "stock"},
    ],
    "Gig Economy & Marketplace Platforms": [
        {"ticker": "UBER", "name": "Uber", "type": "stock"},
        {"ticker": "LYFT", "name": "Lyft", "type": "stock"},
        {"ticker": "ABNB", "name": "Airbnb", "type": "stock"},
    ],
    "Shipping": [
        {"ticker": "FDX", "name": "FedEx", "type": "stock"},
        {"ticker": "UPS", "name": "United Parcel Service", "type": "stock"},
    ],
    "Trucking": [
        {"ticker": "XPO", "name": "XPO Inc.", "type": "stock"},
        {"ticker": "JBHT", "name": "J.B. Hunt Transport", "type": "stock"},
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def headline_id(title):
    return hashlib.md5(title.strip().lower().encode("utf-8")).hexdigest()[:12]


def is_market_hours(dt):
    et = pytz.timezone("America/New_York")
    local = dt.astimezone(et)
    if local.weekday() >= 5:  # weekend
        return False
    market_open = local.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = local.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= local <= market_close


# ---------------------------------------------------------------------------
# Step 2-4: fetch + dedupe headlines
# ---------------------------------------------------------------------------


def fetch_feeds():
    """Fetch all RSS feeds; a broken feed is skipped, never fatal."""
    items = []
    for source, url in FEEDS.items():
        try:
            resp = requests.get(url, timeout=20, headers={"User-Agent": "EDDY/1.0 (+github pages pwa)"})
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            for entry in feed.entries[:MAX_PER_FEED]:
                title = (entry.get("title") or "").strip()
                if not title:
                    continue
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                if published:
                    ts = datetime(*published[:6], tzinfo=timezone.utc)
                else:
                    ts = utcnow()
                items.append({
                    "id": headline_id(title),
                    "time": iso(ts),
                    "source": source,
                    "headline": title,
                    "url": entry.get("link") or "",
                })
            print(f"[feeds] {source}: {min(len(feed.entries), MAX_PER_FEED)} items")
        except Exception as e:  # noqa: BLE001 — one bad feed must not kill the run
            print(f"[feeds] {source} FAILED: {e}", file=sys.stderr)

    # Dedupe by id (MD5 of lowercased title), keep first occurrence
    seen, unique = set(), []
    for item in items:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique.append(item)
    return unique


# ---------------------------------------------------------------------------
# Step 5-7: Gemini classification
# ---------------------------------------------------------------------------

_model = None


def get_model():
    global _model
    if _model is None:
        import google.generativeai as genai

        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        _model = genai.GenerativeModel(
            GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            generation_config={"response_mime_type": "application/json", "temperature": 0.2},
        )
    return _model


def parse_llm_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    return json.loads(text)


def classify_headline(headline, source, taxonomy):
    """Return (summary, industries) validated against the taxonomy, or (None, []) on failure."""
    sub_to_sector = {
        sub: sector for sector, subs in taxonomy["sectors"].items() for sub in subs
    }
    user_msg = f"Taxonomy: {json.dumps(taxonomy)}\n\nHeadline: {headline}\n\nSource: {source}"
    try:
        resp = get_model().generate_content(user_msg)
        data = parse_llm_json(resp.text)
    except Exception as e:  # noqa: BLE001 — classification failure skips the headline
        print(f"[gemini] classify failed for '{headline[:60]}': {e}", file=sys.stderr)
        return None, []

    industries = []
    for item in data.get("industries", []):
        sub = item.get("sub_industry")
        if sub not in sub_to_sector:
            continue  # hallucinated name — drop it
        try:
            confidence = int(round(float(item.get("confidence", 0))))
        except (TypeError, ValueError):
            continue
        confidence = max(0, min(100, confidence))
        if confidence < MIN_CONFIDENCE:
            continue
        industries.append({
            "sector": sub_to_sector[sub],
            "sub_industry": sub,
            "confidence": confidence,
            "direction": "up",
        })
    industries.sort(key=lambda x: x["confidence"], reverse=True)
    summary = (data.get("summary") or "").strip()
    return summary, industries


# ---------------------------------------------------------------------------
# Step 8: ticker mapping (Phase 2)
# ---------------------------------------------------------------------------


def map_tickers(industries):
    best = {}
    for ind in industries:
        for t in INDUSTRY_TO_TICKERS.get(ind["sub_industry"], []):
            existing = best.get(t["ticker"])
            if existing is None or ind["confidence"] > existing["confidence"]:
                best[t["ticker"]] = {
                    "ticker": t["ticker"],
                    "name": t["name"],
                    "type": t["type"],
                    "confidence": ind["confidence"],
                    "direction": "up",
                    "rationale": f"Mapped from {ind['sub_industry']} ({ind['sector']}).",
                    "hist_range_1d": None,
                    "hist_range_5d": None,
                }
    return sorted(best.values(), key=lambda x: x["confidence"], reverse=True)


# ---------------------------------------------------------------------------
# Step 9: portfolio price refresh
# ---------------------------------------------------------------------------


def update_portfolio_prices():
    portfolio = load_json(PORTFOLIO_FILE, {"holdings": []})
    holdings = portfolio.get("holdings", [])
    if not holdings:
        portfolio.setdefault("total_invested", 0)
        portfolio.setdefault("total_current_value", 0)
        portfolio.setdefault("total_gain_loss_pct", 0)
        portfolio["last_updated"] = iso(utcnow())
        save_json(PORTFOLIO_FILE, portfolio)
        return

    tickers = [h["ticker"] for h in holdings]
    prices = price_tracker.current_prices(tickers)
    now = iso(utcnow())
    total_invested = 0.0
    total_value = 0.0
    for h in holdings:
        shares = float(h.get("shares", 0))
        buy = float(h.get("price_at_purchase", 0))
        price = prices.get(h["ticker"])
        if price is not None:
            h["current_price"] = round(price, 2)
            h["last_price_update"] = now
        current = float(h.get("current_price") or buy)
        h["current_value"] = round(shares * current, 2)
        h["gain_loss_pct"] = round((current - buy) / buy * 100, 2) if buy else 0
        total_invested += shares * buy
        total_value += shares * current

    portfolio["total_invested"] = round(total_invested, 2)
    portfolio["total_current_value"] = round(total_value, 2)
    portfolio["total_gain_loss_pct"] = (
        round((total_value - total_invested) / total_invested * 100, 2) if total_invested else 0
    )
    portfolio["last_updated"] = now
    save_json(PORTFOLIO_FILE, portfolio)
    print(f"[portfolio] refreshed {len(holdings)} holdings")


# ---------------------------------------------------------------------------
# Step 10: signal logging + outcome tracking (Phase 3 plumbing)
# ---------------------------------------------------------------------------


def log_signals(history, event):
    """Append one history signal per surfaced ticker (long-only, direction up)."""
    existing = {s["id"] for s in history["signals"]}
    tickers = [t["ticker"] for t in event["tickers"]]
    if not tickers:
        return
    prices = price_tracker.current_prices(tickers)
    now = utcnow()
    for t in event["tickers"]:
        sid = f"{event['id']}_{t['ticker']}"
        if sid in existing:
            continue
        top = event["industries"][0] if event["industries"] else {}
        history["signals"].append({
            "id": sid,
            "event_id": event["id"],
            "logged_at": iso(now),
            "headline": event["headline"],
            "sector": top.get("sector"),
            "sub_industry": top.get("sub_industry"),
            "ticker": t["ticker"],
            "direction_predicted": "up",
            "confidence": t["confidence"],
            "price_at_signal": prices.get(t["ticker"]),
            "price_t10min": None,
            "price_t1hr": None,
            "price_t1day": None,
            "price_t5day": None,
            "outcome_1d": None,
            "outcome_5d": None,
            "correct_1d": None,
            "correct_5d": None,
            "market_hours": is_market_hours(now),
        })


# ---------------------------------------------------------------------------
# Phase 4: ntfy.sh push notifications (no-op unless NTFY_TOPIC is set)
# ---------------------------------------------------------------------------


def notify(event):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        return
    strong = [t for t in event["tickers"] if t["confidence"] >= NOTIFY_CONFIDENCE]
    if not strong:
        return
    tickers = ", ".join(f"{t['ticker']} ({t['confidence']}%)" for t in strong[:5])
    try:
        requests.post(
            f"https://ntfy.sh/{topic}",
            data=f"{event['headline']}\nSignals: {tickers}".encode("utf-8"),
            headers={"Title": "EDDY signal", "Tags": "chart_with_upwards_trend"},
            timeout=10,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[ntfy] push failed: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    taxonomy = load_json(TAXONOMY_FILE, None)
    if taxonomy is None:
        print("taxonomy.json missing — aborting", file=sys.stderr)
        sys.exit(1)

    events_doc = load_json(EVENTS_FILE, {"events": [], "seen": []})
    events = events_doc.get("events", [])
    known_ids = {e["id"] for e in events} | set(events_doc.get("seen", []))

    headlines = fetch_feeds()
    fresh = [h for h in headlines if h["id"] not in known_ids]
    fresh.sort(key=lambda h: h["time"], reverse=True)
    budget = fresh[:MAX_NEW_PER_RUN]
    if len(fresh) > MAX_NEW_PER_RUN:
        print(f"[budget] {len(fresh)} new headlines, classifying newest {MAX_NEW_PER_RUN}")

    history = load_json(HISTORY_FILE, {"signals": [], "accuracy": {}})
    seen = list(events_doc.get("seen", []))

    if budget and not os.environ.get("GEMINI_API_KEY"):
        print("[gemini] GEMINI_API_KEY not set — skipping classification", file=sys.stderr)
        budget = []

    for item in budget:
        summary, industries = classify_headline(item["headline"], item["source"], taxonomy)
        seen.append(item["id"])  # never re-spend a Gemini call on this headline
        if summary is None or not industries:
            continue
        event = {
            **item,
            "summary": summary,
            "industries": industries,
            "tickers": map_tickers(industries),
        }
        events.append(event)
        log_signals(history, event)
        notify(event)
        print(f"[event] {item['source']}: {item['headline'][:70]} -> {len(industries)} industries, {len(event['tickers'])} tickers")

    # Step 9: refresh portfolio prices
    try:
        update_portfolio_prices()
    except Exception as e:  # noqa: BLE001
        print(f"[portfolio] update failed: {e}", file=sys.stderr)

    # Step 10: fill in due T+ price checkpoints and recompute accuracy
    try:
        price_tracker.update_history(history)
    except Exception as e:  # noqa: BLE001
        print(f"[tracker] update failed: {e}", file=sys.stderr)
    save_json(HISTORY_FILE, history)

    # Step 11: write events.json
    events.sort(key=lambda e: e["time"], reverse=True)
    events = events[:MAX_EVENTS]
    save_json(EVENTS_FILE, {
        "updated": iso(utcnow()),
        "sources": list(FEEDS.keys()),
        "count": len(events),
        "events": events,
        "seen": seen[-MAX_SEEN_IDS:],
    })
    print(f"[done] {len(events)} events live, {len(history['signals'])} signals logged")


if __name__ == "__main__":
    main()
