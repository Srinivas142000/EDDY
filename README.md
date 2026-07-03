# EDDY — Event-Driven Dynamic Yield

**Global events. Industry impact. Actionable signals.**

EDDY is a free, serverless, installable PWA that monitors global news, uses Gemini
Flash to classify which industries each event affects (with 0–100 confidence),
maps those industries to US-listed stocks and ETFs, and surfaces long-only buy
signals for **manual** execution on Robinhood.

## How it works

```
RSS feeds ──▶ dedupe ──▶ Gemini Flash classification ──▶ ticker mapping
   (5 sources)              (full industry taxonomy)         (Phase 2)
                                     │
                                     ▼
              events.json / portfolio.json / history.json
                                     │
                    GitHub Pages ◀───┴───▶ ntfy.sh push (Phase 4)
                        (PWA)
```

- **Compute:** GitHub Actions cron, every 30 minutes — free on public repos
- **Hosting:** GitHub Pages — free
- **LLM:** Google Gemini Flash free tier (the pipeline caps itself at 20
  classifications per run ≈ 960/day, under the 1,500/day free limit)
- **Prices:** yfinance
- **Everything else:** vanilla HTML/CSS/JS, zero build step

## Build phases

| Phase | What | Status gate |
|---|---|---|
| 1 | Event ingestion + industry classification → signal board | — |
| 2 | Industry → ticker mapping | — |
| 3 | Backtesting + paper trading | **55% directional accuracy required** |
| 4 | ntfy.sh push notifications + feedback loop | after Phase 3 gate |

All phases live in this one codebase; components without data yet render as
graceful placeholders.

## Deploy

1. Create a **public** GitHub repo named `eddy`
2. Upload all files keeping the folder structure intact (`.github/workflows/update.yml` matters)
3. Get a free Gemini key at https://aistudio.google.com/app/apikey
4. Repo → Settings → Secrets and variables → Actions → add secret `GEMINI_API_KEY`
5. (Optional, Phase 4) add secret `NTFY_TOPIC` with a hard-to-guess topic name,
   then subscribe to it in the [ntfy app](https://ntfy.sh)
6. Settings → Pages → Deploy from branch `main` / root
7. Actions tab → enable workflows → run **Update EDDY signals** manually once
8. Open `https://YOURNAME.github.io/eddy/` on your phone → **Add to Home Screen**
   (desktop Chrome/Edge: install icon in the address bar)

## Portfolio workflow

GitHub Pages is read-only, so the PWA stores your holdings in **localStorage**
on your device. To have the cron job refresh your prices every 30 minutes:
open **Portfolio → Export portfolio.json** and commit the downloaded file to the
repo root. The app merges the repo's refreshed prices back into your local
holdings automatically.

## Backtesting (Phase 3)

```bash
# 1. Create historical_events.csv:  timestamp,headline,source
# 2. Run:
GEMINI_API_KEY=... python backtest.py
```

The report prints accuracy at T+1hr and T+1day (measured against sector ETFs),
plus accuracy broken down by confidence bucket. The gate requires **≥ 55%
T+1day accuracy on ≥ 100 events**, then 4–6 weeks of paper trading at ≥ 55%,
before any real money.

## Local development

```bash
pip install google-generativeai yfinance feedparser pytz requests
GEMINI_API_KEY=... python correlations.py   # one pipeline run
python -m http.server 8000                  # then open http://localhost:8000
```

## Disclaimer

> EDDY is a signal tool only. All trades are executed manually. Past industry
> correlations do not guarantee future price movements. Not financial advice.
> Phase 3 accuracy validation required before real money.
