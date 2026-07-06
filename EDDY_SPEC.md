# EDDY — Event-Driven Dynamic Yield
## Complete Project Specification for Claude Code

---

## 1. Project Overview

EDDY is a free, serverless, installable PWA (Progressive Web App) that monitors global news events, classifies which industries are affected and by how much, maps those industries to US-listed stocks, and surfaces buy signals for manual execution on Robinhood.

**Name:** EDDY — Event-Driven Dynamic Yield  
**Tagline:** Global events. Industry impact. Actionable signals.

### Core principles
- 100% free infrastructure — no servers, no paid domains, no paid APIs beyond one free-tier LLM key
- Manual trading only — EDDY is a signal tool; the human executes all trades on Robinhood
- Long-only signals — only surfaces tickers likely to go UP
- US-listed tickers only — common stocks, US-listed ADRs (e.g. NVO), US-listed ETFs (e.g. JETS, USO)
- Fractional shares — all position sizing assumes fractional share trading on Robinhood
- Real money gates — 55% directional accuracy required at backtesting AND paper trading before live use

---

## 2. Infrastructure (100% Free)

| Component | Technology | Cost |
|---|---|---|
| Compute / cron | GitHub Actions (free on public repos) | $0 |
| Hosting | GitHub Pages | $0 |
| LLM (classification) | Google Gemini Flash API (1,500 req/day free) | $0 |
| Price feed | yfinance Python library | $0 |
| News sources | RSS feeds (no key required) | $0 |
| Push notifications | ntfy.sh (free tier) | $0 |
| PWA / widget | Vanilla HTML/CSS/JS | $0 |

---

## 3. Build Phases

### Phase 1 — Event ingestion + dynamic industry classification
Fetch headlines → Gemini Flash classifies affected industries from full taxonomy → confidence scores 0-100 → write events.json → PWA displays signal board

### Phase 2 — Stock mapping + historical range prediction
Map classified industries to US-listed tickers/ETFs → yfinance ML regression on self-built historical training data → directional signal + historical movement ranges (NOT point predictions)

### Phase 3 — Backtesting + paper trading
Build historical training dataset using event study methodology → backtest directional accuracy → gate: 55% required → paper trade live for 4-6 weeks → gate: 55% required → only then use real money

### Phase 4 — Live deployment + notifications
ntfy.sh push notifications → 5-min cron refresh → feedback loop from outcomes back to confidence weights

**Important: Build all phases in one codebase. Phases 2, 3, 4 components that aren't ready yet should render gracefully as empty/placeholder states — not errors.**

---

## 4. File Structure

```
eddy/
├── .github/
│   └── workflows/
│       └── update.yml          # GitHub Actions cron job
├── .gitattributes               # Cross-platform line endings fix
├── index.html                   # PWA — Home screen
├── event.html                   # PWA — Event detail screen
├── portfolio.html               # PWA — Add/remove stock screen
├── manifest.webmanifest         # PWA manifest
├── sw.js                        # Service worker (offline support)
├── icon-192.png                 # App icon
├── icon-512.png                 # App icon
├── style.css                    # Shared styles
├── app.js                       # Shared JS (portfolio, utils)
├── correlations.py              # Main pipeline: fetch → classify → write
├── backtest.py                  # Phase 3: backtesting engine
├── price_tracker.py             # Phase 3: outcome tracking (checks T+1, T+3, T+5)
├── taxonomy.json                # Full industry taxonomy (Buffett + modern additions)
├── events.json                  # Live output — read by PWA
├── portfolio.json               # User's holdings — read/written by PWA
├── history.json                 # Signal log for accuracy tracking
└── README.md
```

---

## 5. Cross-Platform Setup

Create `.gitattributes` in root with exactly this content:
```
* text=auto
*.py text eol=lf
*.json text eol=lf
*.yml text eol=lf
*.html text eol=lf
*.css text eol=lf
*.js text eol=lf
```

---

## 6. Industry Taxonomy (taxonomy.json)

The LLM must classify events using ONLY these industries. It scores every materially affected industry 0-100. Industries with zero impact should be omitted from output (not returned as 0).

The taxonomy has 9 top-level sectors. Each sector contains sub-industries. The LLM returns scores at the sub-industry level; the PWA groups them by sector.

```json
{
  "sectors": {
    "Basic Materials": [
      "Agricultural Chemicals", "Aluminum", "Chemicals—Major Diversified",
      "Copper", "Gold", "Independent Oil & Gas", "Industrial Metals & Minerals",
      "Major Integrated Oil & Gas", "Nonmetallic Mineral Mining",
      "Oil & Gas Drilling & Exploration", "Oil & Gas Equipment & Services",
      "Oil & Gas Pipelines", "Oil & Gas Refining & Marketing", "Silver"
    ],
    "Utilities": [
      "Diversified Utilities", "Electric Utilities", "Foreign Utilities",
      "Gas Utilities", "Water Utilities"
    ],
    "Consumer Goods": [
      "Beverages—Wineries & Distillers", "Business Equipment", "Cigarettes",
      "Cleaning Products", "Confectioners", "Dairy Products", "Electronic Equipment",
      "Farm Products", "Food—Major Diversified", "Home Furnishings & Fixtures",
      "Housewares & Accessories", "Meat Products", "Office Supplies",
      "Packaging & Containers", "Paper & Paper Products", "Personal Products",
      "Processed & Packaged Goods", "Recreational Goods", "Recreational Vehicles",
      "Rubber & Plastics", "Sporting Goods", "Textile—Apparel Clothing",
      "Textile—Apparel Footwear & Accessories", "Tobacco Products",
      "Toys & Games", "Trucks & Other Vehicles"
    ],
    "Health Care": [
      "Biotechnology", "Diagnostic Substances", "Drug Delivery",
      "Drug Manufacturers—Major", "Drug Manufacturers—Other", "Drug-Related Products",
      "Drugs—Generic", "Health Care Plans", "Home Health Care", "Hospitals",
      "Long-Term Care Facilities", "Medical Appliances & Equipment",
      "Medical Instruments & Supplies", "Medical Laboratories & Research",
      "Medical Practitioners", "Specialized Health Services"
    ],
    "Financial": [
      "Accident & Health Insurance", "Asset Management", "Closed-End Fund—Debt",
      "Closed-End Fund—Equity", "Closed-End Fund—Foreign", "Credit Services",
      "Diversified Investments", "Foreign Money Center Banks", "Foreign Regional Banks",
      "Investment Brokerage—Regional", "Life Insurance", "Money Center Banks",
      "Mortgage Investment", "Property & Casualty Insurance", "Property Management",
      "Real Estate Development", "REIT—Diversified", "REIT—Health Care",
      "REIT—Hotel/Motel", "REIT—Office", "REIT—Residential", "REIT—Retail",
      "Regional Banks", "Savings & Loans", "Surety & Title Insurance"
    ],
    "Industrial Goods": [
      "Aerospace/Defense—Major Diversified", "Aerospace/Defense Products & Services",
      "Cement", "Diversified Machinery", "Farm & Construction Machinery",
      "General Building Materials", "General Contractors", "Heavy Construction",
      "Industrial Electrical Equipment", "Industrial Equipment & Components",
      "Lumber & Wood Production", "Machine Tools & Accessories",
      "Manufactured Housing", "Metal Fabrication", "Pollution & Treatment Controls",
      "Residential Construction", "Small Tools & Accessories",
      "Textile Industrial", "Waste Management"
    ],
    "Technology": [
      "Application Software", "Business Software & Services", "Communication Equipment",
      "Computer Peripherals", "Data Storage Devices", "Diversified Communication Services",
      "Diversified Computer Systems", "Diversified Electronics",
      "Health Care Information Services", "Information & Delivery Services",
      "Information Technology Services", "Internet Information Providers",
      "Internet Service Providers", "Internet Software & Services",
      "Long-Distance Carriers", "Multimedia & Graphics Software",
      "Networking & Communication Devices", "Personal Computers",
      "Processing Systems & Products", "Scientific & Technical Instruments",
      "Security Software & Services", "Semiconductor—Broad Line",
      "Semiconductor—Equipment & Materials", "Semiconductor—Integrated Circuits",
      "Semiconductor—Specialized", "Technical & System Software",
      "Telecom Services—Domestic", "Telecom Services—Foreign", "Wireless Communications"
    ],
    "Services": [
      "Advertising Agencies", "Air Delivery & Freight Services", "Air Services",
      "Apparel Stores", "Auto Dealerships", "Auto Parts Stores", "Auto Parts Wholesale",
      "Basic Materials Wholesale", "Broadcasting—Radio", "Broadcasting—TV",
      "Building Materials Wholesale", "Business Services", "CATV Systems",
      "Computers Wholesale", "Consumer Services", "Department Stores",
      "Discount & Variety Stores", "Drugstores", "Drug Wholesale",
      "Education & Training Services", "Electronics Stores", "Electronics Wholesale",
      "Entertainment—Diversified", "Food Wholesale", "Gaming Activities",
      "General Entertainment", "Grocery Stores", "Home Improvement Stores",
      "Industrial Equipment Wholesale", "Jewelry Stores", "Lodging",
      "Management Services", "Marketing Services", "Medical Equipment Wholesale",
      "Movie Production & Theaters", "Personal Services", "Publishing—Books",
      "Publishing—Newspapers", "Publishing—Periodicals", "Railroads",
      "Regional Airlines", "Rental & Leasing Services", "Research Services",
      "Resorts & Casinos", "Restaurants", "Security & Protection Services",
      "Shipping", "Specialty Eateries", "Specialty Retail"
    ],
    "Modern & Digital": [
      "Cloud Infrastructure & Services", "Social Media & Platforms",
      "Streaming & Digital Media", "Electric Vehicles & Battery Technology",
      "AI & Machine Learning Infrastructure", "Cryptocurrency & Digital Assets",
      "Cybersecurity", "Gig Economy & Marketplace Platforms",
      "Space & Satellite Technology"
    ]
  }
}
```

---

## 7. Data Schemas

### events.json
Written by `correlations.py` every cron run. Read by the PWA.

```json
{
  "updated": "2025-09-15T14:32:00Z",
  "sources": ["Reuters", "AP", "CNBC", "Yahoo Finance", "MarketWatch"],
  "count": 12,
  "events": [
    {
      "id": "abc123",
      "time": "2025-09-15T14:10:00Z",
      "source": "Reuters",
      "headline": "Drone strikes disrupt output at major Gulf oil terminal",
      "url": "https://reuters.com/...",
      "summary": "A two-sentence LLM-generated summary of the event.",
      "industries": [
        {
          "sector": "Basic Materials",
          "sub_industry": "Major Integrated Oil & Gas",
          "confidence": 91,
          "direction": "up"
        },
        {
          "sector": "Basic Materials",
          "sub_industry": "Oil & Gas Refining & Marketing",
          "confidence": 83,
          "direction": "up"
        },
        {
          "sector": "Industrial Goods",
          "sub_industry": "Aerospace/Defense—Major Diversified",
          "confidence": 74,
          "direction": "up"
        }
      ],
      "tickers": [
        {
          "ticker": "XOM",
          "name": "Exxon Mobil",
          "type": "stock",
          "confidence": 89,
          "direction": "up",
          "rationale": "Direct US-listed oil producer; supply disruption lifts crude price.",
          "hist_range_1d": {"low": 1.2, "high": 4.5},
          "hist_range_5d": {"low": 0.8, "high": 6.2}
        },
        {
          "ticker": "USO",
          "name": "US Oil Fund ETF",
          "type": "etf",
          "confidence": 88,
          "direction": "up",
          "rationale": "Tracks crude futures directly.",
          "hist_range_1d": {"low": 1.0, "high": 3.8},
          "hist_range_5d": {"low": 0.5, "high": 5.1}
        }
      ]
    }
  ]
}
```

**Notes:**
- `industries` array: only sectors with confidence > 0 are included
- `tickers` array: empty in Phase 1, populated in Phase 2
- `hist_range_*`: empty in Phase 1 and 2, populated after Phase 3 training data is built
- `direction` is always "up" (long-only strategy)
- Sort events by `time` descending (newest first)

### portfolio.json
Written by the PWA when user adds/removes stocks. Updated by `correlations.py` on each run (to refresh current prices via yfinance).

```json
{
  "holdings": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "shares": 0.5,
      "price_at_purchase": 185.00,
      "current_price": 192.50,
      "current_value": 96.25,
      "gain_loss_pct": 4.05,
      "last_price_update": "2025-09-15T14:32:00Z"
    }
  ],
  "total_invested": 185.00,
  "total_current_value": 192.50,
  "total_gain_loss_pct": 4.05,
  "last_updated": "2025-09-15T14:32:00Z"
}
```

### history.json
Append-only log of every signal fired. Used for Phase 3 accuracy tracking.

```json
{
  "signals": [
    {
      "id": "abc123_XOM",
      "event_id": "abc123",
      "logged_at": "2025-09-15T14:32:00Z",
      "headline": "Drone strikes disrupt output at major Gulf oil terminal",
      "sector": "Basic Materials",
      "sub_industry": "Major Integrated Oil & Gas",
      "ticker": "XOM",
      "direction_predicted": "up",
      "confidence": 89,
      "price_at_signal": 112.34,
      "price_t10min": null,
      "price_t1hr": null,
      "price_t1day": null,
      "price_t5day": null,
      "outcome_1d": null,
      "outcome_5d": null,
      "correct_1d": null,
      "correct_5d": null,
      "market_hours": true
    }
  ],
  "accuracy": {
    "total_signals": 0,
    "resolved_1d": 0,
    "correct_1d": 0,
    "accuracy_1d_pct": null,
    "resolved_5d": 0,
    "correct_5d": 0,
    "accuracy_5d_pct": null
  }
}
```

---

## 8. Backend: correlations.py

This is the main pipeline script. Runs inside GitHub Actions every 30 minutes.

### Steps in order:
1. Load `taxonomy.json`
2. Fetch RSS feeds from all 5 sources (timeout 20s each, skip on error)
3. Deduplicate headlines by MD5 hash of lowercased title
4. Filter to headlines not already in `events.json` (by id)
5. For each new headline, call Gemini Flash API:
   - Send headline + full taxonomy
   - Receive structured JSON: list of `{sub_industry, sector, confidence, direction}` for all materially affected industries
   - Also receive a 2-sentence summary of the event
6. Filter results: only keep industries with confidence >= 20
7. Sort industries by confidence descending
8. For Phase 2: map industries to tickers (see ticker mapping section)
9. Update `portfolio.json` with current prices via yfinance for all portfolio holdings
10. Update `history.json`: check T+10min/1hr/1day/5day prices for any logged signals that are due
11. Write updated `events.json` (max 50 events, sorted by time desc)
12. Commit and push changes

### RSS Feed Sources:
```python
FEEDS = {
    "Reuters": "https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best",
    "AP": "https://rsshub.app/apnews/topics/business",
    "CNBC": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories"
}
MAX_PER_FEED = 25
```

### Gemini Flash API call:

Use Google Generative AI Python SDK (`google-generativeai`). API key stored as GitHub Secret `GEMINI_API_KEY`.

**System prompt:**
```
You are a financial industry analyst. Given a news headline, identify every industry from the provided taxonomy that is materially affected by this event. You reason deeply — including second and third order effects. For example, if Apple raises iPhone prices, you consider not just consumer electronics but also semiconductor supply chains, app ecosystem revenue, consumer credit spending, and emerging market consumer demand.

Return ONLY a JSON object with this exact structure:
{
  "summary": "Two sentence factual summary of the event.",
  "industries": [
    {"sub_industry": "exact name from taxonomy", "sector": "exact sector name", "confidence": 85, "direction": "up"}
  ]
}

Rules:
- Only include industries with meaningful impact (confidence >= 20)
- direction should be "up" if the industry benefits from this event, or "down" if the industry is harmed. Be honest about both.
- Use ONLY sub-industry names that appear exactly in the provided taxonomy
- Confidence 80-100: near-certain direct impact
- Confidence 60-79: likely direct impact  
- Confidence 40-59: probable indirect impact
- Confidence 20-39: possible second-order effect
- Do not include any explanation outside the JSON object
- Do not wrap in markdown code blocks
```

**User message format:**
```
Taxonomy: {json.dumps(taxonomy)}

Headline: {headline}

Source: {source}
```

### Market hours check:
```python
import pytz
def is_market_hours(dt):
    et = pytz.timezone('America/New_York')
    local = dt.astimezone(et)
    if local.weekday() >= 5:  # weekend
        return False
    market_open = local.replace(hour=9, minute=30, second=0)
    market_close = local.replace(hour=16, minute=0, second=0)
    return market_open <= local <= market_close
```

Pre-market news (before 9:30 ET): measure price impact at next-day open, not T+10min.

---

## 9. Ticker Mapping (Phase 2)

Map classified sub-industries to US-listed tickers. Every ticker must be buyable on Robinhood.

```python
INDUSTRY_TO_TICKERS = {
    "Major Integrated Oil & Gas": [
        {"ticker": "XOM", "name": "Exxon Mobil", "type": "stock"},
        {"ticker": "CVX", "name": "Chevron", "type": "stock"},
        {"ticker": "USO", "name": "US Oil Fund ETF", "type": "etf"}
    ],
    "Oil & Gas Drilling & Exploration": [
        {"ticker": "XOP", "name": "SPDR S&P Oil & Gas E&P ETF", "type": "etf"},
        {"ticker": "USO", "name": "US Oil Fund ETF", "type": "etf"}
    ],
    "Aerospace/Defense—Major Diversified": [
        {"ticker": "LMT", "name": "Lockheed Martin", "type": "stock"},
        {"ticker": "RTX", "name": "Raytheon Technologies", "type": "stock"},
        {"ticker": "ITA", "name": "iShares US Aerospace & Defense ETF", "type": "etf"}
    ],
    "Aerospace/Defense Products & Services": [
        {"ticker": "NOC", "name": "Northrop Grumman", "type": "stock"},
        {"ticker": "ITA", "name": "iShares US Aerospace & Defense ETF", "type": "etf"}
    ],
    "Semiconductor—Integrated Circuits": [
        {"ticker": "NVDA", "name": "Nvidia", "type": "stock"},
        {"ticker": "AMD", "name": "Advanced Micro Devices", "type": "stock"},
        {"ticker": "SOXX", "name": "iShares Semiconductor ETF", "type": "etf"}
    ],
    "Semiconductor—Broad Line": [
        {"ticker": "INTC", "name": "Intel", "type": "stock"},
        {"ticker": "SOXX", "name": "iShares Semiconductor ETF", "type": "etf"}
    ],
    "Semiconductor—Equipment & Materials": [
        {"ticker": "AMAT", "name": "Applied Materials", "type": "stock"},
        {"ticker": "LRCX", "name": "Lam Research", "type": "stock"},
        {"ticker": "SOXX", "name": "iShares Semiconductor ETF", "type": "etf"}
    ],
    "Drug Manufacturers—Major": [
        {"ticker": "LLY", "name": "Eli Lilly", "type": "stock"},
        {"ticker": "PFE", "name": "Pfizer", "type": "stock"},
        {"ticker": "XBI", "name": "SPDR Biotech ETF", "type": "etf"}
    ],
    "Biotechnology": [
        {"ticker": "LLY", "name": "Eli Lilly", "type": "stock"},
        {"ticker": "MRNA", "name": "Moderna", "type": "stock"},
        {"ticker": "XBI", "name": "SPDR Biotech ETF", "type": "etf"}
    ],
    "Drug Manufacturers—Other": [
        {"ticker": "NVO", "name": "Novo Nordisk ADR", "type": "adr"},
        {"ticker": "XBI", "name": "SPDR Biotech ETF", "type": "etf"}
    ],
    "Regional Airlines": [
        {"ticker": "JETS", "name": "US Global Jets ETF", "type": "etf"},
        {"ticker": "UAL", "name": "United Airlines", "type": "stock"},
        {"ticker": "DAL", "name": "Delta Air Lines", "type": "stock"}
    ],
    "Air Services": [
        {"ticker": "JETS", "name": "US Global Jets ETF", "type": "etf"}
    ],
    "Lodging": [
        {"ticker": "ABNB", "name": "Airbnb", "type": "stock"},
        {"ticker": "MAR", "name": "Marriott International", "type": "stock"},
        {"ticker": "BKNG", "name": "Booking Holdings", "type": "stock"}
    ],
    "Resorts & Casinos": [
        {"ticker": "WYNN", "name": "Wynn Resorts", "type": "stock"},
        {"ticker": "MGM", "name": "MGM Resorts", "type": "stock"}
    ],
    "Application Software": [
        {"ticker": "MSFT", "name": "Microsoft", "type": "stock"},
        {"ticker": "CRM", "name": "Salesforce", "type": "stock"},
        {"ticker": "IGV", "name": "iShares Expanded Tech-Software ETF", "type": "etf"}
    ],
    "Internet Software & Services": [
        {"ticker": "GOOGL", "name": "Alphabet", "type": "stock"},
        {"ticker": "META", "name": "Meta Platforms", "type": "stock"}
    ],
    "Electronic Equipment": [
        {"ticker": "AAPL", "name": "Apple Inc.", "type": "stock"},
        {"ticker": "QCOM", "name": "Qualcomm", "type": "stock"}
    ],
    "Money Center Banks": [
        {"ticker": "JPM", "name": "JPMorgan Chase", "type": "stock"},
        {"ticker": "BAC", "name": "Bank of America", "type": "stock"},
        {"ticker": "KBE", "name": "SPDR Bank ETF", "type": "etf"}
    ],
    "Asset Management": [
        {"ticker": "BLK", "name": "BlackRock", "type": "stock"},
        {"ticker": "GS", "name": "Goldman Sachs", "type": "stock"}
    ],
    "Gold": [
        {"ticker": "GLD", "name": "SPDR Gold Shares ETF", "type": "etf"},
        {"ticker": "NEM", "name": "Newmont Corporation", "type": "stock"}
    ],
    "Restaurants": [
        {"ticker": "MCD", "name": "McDonald's", "type": "stock"},
        {"ticker": "CMG", "name": "Chipotle Mexican Grill", "type": "stock"}
    ],
    "Grocery Stores": [
        {"ticker": "KR", "name": "Kroger", "type": "stock"},
        {"ticker": "WMT", "name": "Walmart", "type": "stock"}
    ],
    "Cloud Infrastructure & Services": [
        {"ticker": "AMZN", "name": "Amazon (AWS)", "type": "stock"},
        {"ticker": "MSFT", "name": "Microsoft (Azure)", "type": "stock"},
        {"ticker": "GOOGL", "name": "Alphabet (GCP)", "type": "stock"}
    ],
    "Electric Vehicles & Battery Technology": [
        {"ticker": "TSLA", "name": "Tesla", "type": "stock"},
        {"ticker": "LIT", "name": "Global X Lithium & Battery Tech ETF", "type": "etf"},
        {"ticker": "DRIV", "name": "Global X Autonomous & EV ETF", "type": "etf"}
    ],
    "AI & Machine Learning Infrastructure": [
        {"ticker": "NVDA", "name": "Nvidia", "type": "stock"},
        {"ticker": "AMD", "name": "Advanced Micro Devices", "type": "stock"},
        {"ticker": "BOTZ", "name": "Global X Robotics & AI ETF", "type": "etf"}
    ],
    "Cybersecurity": [
        {"ticker": "CRWD", "name": "CrowdStrike", "type": "stock"},
        {"ticker": "PANW", "name": "Palo Alto Networks", "type": "stock"},
        {"ticker": "CIBR", "name": "First Trust Nasdaq Cybersecurity ETF", "type": "etf"}
    ],
    "Social Media & Platforms": [
        {"ticker": "META", "name": "Meta Platforms", "type": "stock"},
        {"ticker": "SNAP", "name": "Snap Inc.", "type": "stock"}
    ],
    "Streaming & Digital Media": [
        {"ticker": "NFLX", "name": "Netflix", "type": "stock"},
        {"ticker": "DIS", "name": "Walt Disney", "type": "stock"}
    ],
    "Gig Economy & Marketplace Platforms": [
        {"ticker": "UBER", "name": "Uber", "type": "stock"},
        {"ticker": "LYFT", "name": "Lyft", "type": "stock"},
        {"ticker": "ABNB", "name": "Airbnb", "type": "stock"}
    ],
    "Shipping": [
        {"ticker": "FDX", "name": "FedEx", "type": "stock"},
        {"ticker": "UPS", "name": "United Parcel Service", "type": "stock"}
    ],
    "Trucking": [
        {"ticker": "XPO", "name": "XPO Inc.", "type": "stock"},
        {"ticker": "JBHT", "name": "J.B. Hunt Transport", "type": "stock"}
    ]
}
```

---

## 10. GitHub Actions Workflow (.github/workflows/update.yml)

```yaml
name: Update EDDY signals

on:
  schedule:
    - cron: "*/30 * * * *"
  workflow_dispatch: {}

permissions:
  contents: write

concurrency:
  group: update-signals
  cancel-in-progress: true

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install google-generativeai yfinance feedparser pytz requests

      - name: Run pipeline
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python correlations.py

      - name: Commit changes
        run: |
          git config user.name "eddy-bot"
          git config user.email "bot@users.noreply.github.com"
          git add events.json portfolio.json history.json
          git diff --staged --quiet || git commit -m "update signals $(date -u +%FT%TZ)"
          git push
```

---

## 11. UX Specification

### Design language
- Dark theme: background `#0E1116`, panel `#161B22`, panel-2 `#1C232C`, borders `#283039`
- Text: primary `#E6EDF3`, muted `#8B949E`
- Up/positive: `#3FB950` (green)
- Accent/amber: `#E3B341`
- Font: Space Grotesk (sans) + JetBrains Mono (mono for tickers, numbers, badges)
- Load both from Google Fonts

---

### Screen 1: Home (index.html)

**Header bar:**
- Left: house icon (links to index.html)
- Center: "EDDY" wordmark
- Right: settings/gear icon (links to settings section or modal)

**Recent Events strip (horizontal scroll):**
- Shows max 5 events with confidence >= 70 (high-signal only)
- Each card: headline truncated to 2 lines, top sector name, confidence badge, timestamp
- Tapping a card navigates to event.html?id={event_id}
- If fewer than 2 high-confidence events: show all events regardless of threshold

**Filter + sort bar:**
- Filter chips: ALL | by sector name (dynamically generated from current events)
- Sort: "Newest" | "Highest confidence"
- Confidence threshold toggle: "70%+" | "All"

**Portfolio circle:**
- Centered donut chart showing portfolio breakdown by ticker
- Center of donut: total current value in dollars (e.g. "XXXX $")
- Outside the donut: individual ticker labels with current value
- Below donut: list of holdings (ticker, shares, current price, gain/loss %)
- "+ Add Stock" button → portfolio.html
- "- Remove Stock" button → portfolio.html

**Past Events table:**
- Full list of all events (not just high-confidence), sorted by selected sort order
- Columns: time | source | headline (truncated) | top sector | confidence bar | "Read" link
- "Read" navigates to event.html?id={event_id}
- "+ More" loads older events
- Confidence bar: thin horizontal bar, green fill, width proportional to confidence %

**Confidence signal visual (on every event row/card):**
- 3-dot strength indicator: 1 dot (20-49%), 2 dots (50-74%), 3 dots (75-100%)
- Dots are green (#3FB950), empty dots are gray (#283039)
- Shown in both the horizontal scroll cards and the past events table

---

### Screen 2: Event Detail (event.html?id={id})

**Header:**
- Back arrow (← returns to index.html)
- Center: "EDDY" wordmark
- Right: house icon

**Article section:**
- Source badge (e.g. "REUTERS")
- Full headline (large, bold)
- 2-sentence LLM summary
- "Read full article ↗" link to original URL

**Industry impact pie chart:**
- Colourful pie/donut chart, one slice per sector with any affected sub-industries
- Legend: sector colour + name + top confidence score for that sector
- Example: 🔴 Technology 91% · 🔵 Financial 54% · 🟡 Industrial 38%
- Tapping a slice expands sub-industry list below chart

**Sub-industry breakdown (below chart):**
- Grouped by sector
- Each row: sub-industry name | confidence bar | confidence percentage
- Sorted by confidence descending within each sector

**P.Stock section (Portfolio Stock — stocks the user already holds):**
- Only shown if user has portfolio holdings
- Heading: "Your portfolio — affected"
- For each holding that appears in `tickers` array OR whose industry matches classified industries:
  - Ticker badge, company name, confidence, current price, your gain/loss %
  - If the event affects a stock you hold: highlight it clearly

**Non-P.Stock section (stocks not in portfolio):**
- Heading: "Signal — watch these"
- All tickers from `tickers` array not in user's portfolio
- Each row: ticker badge | company name | type (ETF/ADR/Stock) | confidence bar | direction (always ▲)
- Rationale shown on expand/tap

**Historical range (Phase 3 — shows as placeholder until data exists):**
- "1-day range: awaiting data" / "+1.2% to +4.5% (based on N similar events)" once populated

---

### Screen 3: Add / Remove Stock (portfolio.html)

**Header:**
- Left: house icon
- Center: "EDDY"
- Right: back arrow or close

**Add Stock form:**
- Title: "Add Stock"
- Field: Ticker (text input, auto-uppercase, e.g. "AAPL")
- Field: Price @ Purchase (number input, e.g. 185.00)
- Field: Shares / Amount of Stock (number input, allows decimals for fractional e.g. 0.5)
- Note below: "Fractional shares supported — enter decimal amounts"
- Button: "Add Stock" (saves to portfolio.json)

**Current Holdings list:**
- Each holding: ticker | shares | purchase price | current price | gain/loss % | remove button (×)
- Removing updates portfolio.json

**Important:** portfolio.json is committed to the repo by the cron job (it updates prices). The PWA reads it from GitHub Pages URL. The PWA writes to it via... see note below.

**Portfolio write mechanism:**
Since GitHub Pages is read-only, portfolio changes made in the PWA must be stored in localStorage as the source of truth for the user's own device. The cron job reads `portfolio.json` from the repo (committed manually or via a separate mechanism). For simplicity in Phase 1: the user adds stocks in the PWA (stored in localStorage), and separately the portfolio.json in the repo is manually updated. Add a "Export portfolio.json" button that downloads the current localStorage portfolio as a file the user can commit to the repo. Document this workflow clearly in the UI.

---

## 12. PWA Configuration

### manifest.webmanifest
```json
{
  "name": "EDDY — Event-Driven Dynamic Yield",
  "short_name": "EDDY",
  "description": "Global events mapped to industry impact and stock signals.",
  "start_url": "./index.html",
  "display": "standalone",
  "orientation": "portrait",
  "background_color": "#0E1116",
  "theme_color": "#0E1116",
  "icons": [
    {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
    {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}
  ]
}
```

### sw.js (Service Worker)
- Cache shell (index.html, event.html, portfolio.html, style.css, app.js, manifest, icons)
- Network-first for events.json and portfolio.json (always want fresh data)
- Cache-first for everything else
- Version cache key: "eddy-v1"

---

## 13. Phase 3 — Backtesting (backtest.py)

### Event study methodology:
1. Collect past headlines with timestamps (can use RSS archive or manually curated CSV)
2. For each headline: run Phase 1 classification (Gemini) to get industry + confidence
3. Map to sector ETF (not individual stock — use ETF for clean measurement):
   - Technology → QQQ
   - Energy → XLE
   - Defense → ITA
   - Semiconductors → SOXX
   - Healthcare → XLV
   - Financial → XLF
   - Consumer → XLY
   - Industrial → XLI
   - Basic Materials → XLB
4. Pull ETF price at headline timestamp using yfinance
5. Pull ETF price at T+10min, T+1hr, T+1day (handle pre-market: use next open)
6. Compute direction: did price go UP? Binary correct/incorrect
7. Append to history.json

### Accuracy gate:
- Run on minimum 100 historical events
- Calculate accuracy per window (T+1hr, T+1day)
- If T+1day accuracy >= 55%: proceed to paper trading
- If < 55%: retune prompt or taxonomy, repeat

---

## 14. Python Dependencies

```
google-generativeai
yfinance
feedparser
pytz
requests
pandas
scikit-learn
numpy
```

Install line for GitHub Actions:
```
pip install google-generativeai yfinance feedparser pytz requests pandas scikit-learn numpy
```

---

## 15. Secrets Required

Add these in GitHub repo → Settings → Secrets → Actions → New repository secret:

| Secret name | Value |
|---|---|
| `GEMINI_API_KEY` | Your Google AI Studio free API key |

Get Gemini API key free at: https://aistudio.google.com/app/apikey

---

## 16. Deploy Steps (for README)

1. Create public GitHub repo named `eddy`
2. Upload all files keeping folder structure intact
3. Add `GEMINI_API_KEY` secret in repo settings
4. Settings → Pages → Deploy from branch `main` / root
5. Actions → Enable workflows → Run "Update EDDY signals" manually
6. Open `https://YOURNAME.github.io/eddy/` on phone → Add to Home Screen
7. On desktop Chrome/Edge → install icon in address bar

---

## 17. Honest Disclaimers (must appear in UI footer)

"EDDY is a signal tool only. All trades are executed manually. Past industry correlations do not guarantee future price movements. Not financial advice. Phase 3 accuracy validation required before real money."
