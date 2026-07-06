# EDDY — Setup & Tokens Guide

Everything you need to get EDDY running, both **locally** and on **GitHub**
(production). Follow the section you need.

- **Local** = run the pipeline and the PWA on your own machine to test.
- **GitHub** = the serverless production setup (Actions runs the pipeline every
  30 min, GitHub Pages hosts the app).

---

## Tokens you need

| Token | Required? | Used for | Where to get it |
|---|---|---|---|
| `GEMINI_API_KEY` | **Yes** | Classifying events with Gemini Flash | Google AI Studio (free) |
| `NTFY_TOPIC` | Optional | Phase 4 push notifications | You invent the string (free) |

> Treat `GEMINI_API_KEY` like a password. Never commit it to the repo or paste
> it into chats/issues. It only ever lives in your local shell session or in a
> GitHub encrypted secret.

---

## 1. Get your Gemini API key (required)

1. Go to <https://aistudio.google.com/app/apikey>
2. Sign in with your Google account.
3. Click **Create API key** → **Create API key in new project** (or pick an
   existing project).
4. Copy the key — it looks like `AIzaSy...`.

Free tier is enough: the pipeline caps itself at ~20 classifications per run
(~960/day), under the 1,500/day free limit.

## 2. (Optional) Choose an ntfy topic for push notifications

No account needed — it's just a secret string you make up.

1. Pick a hard-to-guess name, e.g. `eddy-signals-x9f2k8`.
2. Install the **ntfy** app (iOS/Android) and **subscribe** to that exact topic.
3. Use that string as `NTFY_TOPIC`.

Skip this if you don't want notifications yet — the code is a no-op without it.

---

## 3. Local setup

Run everything on your own machine to test before deploying.

### 3a. Install dependencies (one time)

```powershell
pip install google-generativeai yfinance feedparser pytz requests
```

### 3b. Set your token for the current shell session

**Windows PowerShell:**
```powershell
$env:GEMINI_API_KEY = "paste-your-key-here"
# optional:
$env:NTFY_TOPIC = "eddy-signals-x9f2k8"
```

**macOS / Linux (bash/zsh):**
```bash
export GEMINI_API_KEY="paste-your-key-here"
# optional:
export NTFY_TOPIC="eddy-signals-x9f2k8"
```

> This only lasts for the current terminal window. Open a new terminal and
> you'll need to set it again. Do **not** hardcode the key into any file.

### 3c. Run one pipeline pass

```powershell
python correlations.py
```

This fetches news, classifies industries, maps tickers, and rewrites
`events.json` / `portfolio.json` / `history.json`.

### 3d. View the app

```powershell
python -m http.server 8000
```

Open <http://localhost:8000>. Refresh after a pipeline run to see fresh signals.

### 3e. (Optional) Other scripts

```powershell
python price_tracker.py     # fill outcome prices + recompute accuracy
python backtest.py          # Phase 3 backtest (needs historical_events.csv first)
```

---

## 4. GitHub setup (production)

The production app is serverless: **GitHub Actions** runs the pipeline on a cron
and **GitHub Pages** hosts the PWA. No server to manage.

Repo: <https://github.com/Srinivas142000/EDDY>

### 4a. Add the secrets

1. Go to **Settings → Secrets and variables → Actions**
   (<https://github.com/Srinivas142000/EDDY/settings/secrets/actions>).
2. Click **New repository secret**.
3. Name: `GEMINI_API_KEY` — Value: paste your key → **Add secret**.
4. (Optional) **New repository secret** again → Name: `NTFY_TOPIC` —
   Value: your topic string → **Add secret**.

These are encrypted; the workflow reads them via
`${{ secrets.GEMINI_API_KEY }}` (see `.github/workflows/update.yml`).

### 4b. Enable GitHub Pages

1. Go to **Settings → Pages**
   (<https://github.com/Srinivas142000/EDDY/settings/pages>).
2. **Source:** Deploy from a branch.
3. **Branch:** `main`, **Folder:** `/ (root)` → **Save**.
4. After ~1 min the app is live at
   **<https://srinivas142000.github.io/EDDY/>**.

### 4c. Run the pipeline

1. Go to the **Actions** tab
   (<https://github.com/Srinivas142000/EDDY/actions>).
2. If prompted, click **I understand my workflows, enable them**.
3. Select **Update EDDY signals** → **Run workflow** → **Run workflow**.
4. It runs now and then automatically every 30 minutes, committing fresh JSON
   back to the repo.

### 4d. Install the PWA

Open <https://srinivas142000.github.io/EDDY/>:
- **Phone:** browser menu → **Add to Home Screen**.
- **Desktop Chrome/Edge:** install icon in the address bar.

---

## 5. Portfolio sync (how prices auto-refresh)

GitHub Pages is read-only, so the PWA stores your holdings in **localStorage** on
your device. To have the cron job refresh your prices:

1. In the app: **Portfolio → Export portfolio.json**.
2. Commit the downloaded `portfolio.json` to the repo root.
3. The pipeline refreshes its prices every 30 min; the app merges them back into
   your local holdings automatically.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `GEMINI_API_KEY not set` | You didn't set the env var in this shell (§3b) or the GitHub secret (§4a). |
| Classification skipped in logs | Same as above — key missing or empty. |
| Pages shows 404 | Pages not enabled yet, or wrong branch/folder (§4b). Wait 1–2 min after enabling. |
| No push notifications | `NTFY_TOPIC` not set, or you didn't subscribe to that exact topic in the ntfy app. |
| Workflow didn't run | Enable workflows in the Actions tab (§4c), then run manually once. |

---

## Disclaimer

EDDY is a signal tool only. All trades are executed manually. Past industry
correlations do not guarantee future price movements. Not financial advice.
Phase 3 accuracy validation required before real money.
