# EDDY — Improvements Found While Building

Two lists: things I already fixed in the code (safe, no behavior the spec forbids),
and things worth deciding on before/after launch.

---

## Applied in this build

1. **Gemini free-tier budget math didn't work.** 5 feeds × 25 headlines = up to 125
   new headlines per run × 48 runs/day ≈ 6,000 calls/day — 4× over the 1,500/day free
   limit. Added `MAX_NEW_PER_RUN = 20` (≈ 960 calls/day worst case) in
   `correlations.py`. Newest headlines get priority.

2. **Headlines that fall off the 50-event cap would be re-classified forever.**
   The spec dedupes only against ids currently in `events.json`; once an event rotates
   out, its headline (still in the RSS feed) would be re-sent to Gemini. Added a
   `seen` id list (capped at 1,000) inside `events.json` — the PWA ignores the extra
   key, and no Gemini call is ever spent twice on the same headline. This also
   remembers headlines that classified to *zero* industries, so they aren't retried.

3. **XSS from news content.** Headlines/summaries/URLs come from external RSS feeds
   and an LLM, and get injected into the DOM. Everything rendered is HTML-escaped
   (`EDDY.esc`) and article links get `rel="noopener"`.

4. **Git push race in the workflow.** With a 30-min cron plus manual dispatches, a
   push can be rejected if anything else landed meanwhile. Added
   `git pull --rebase` before `git push` in `update.yml`.

5. **Gemini JSON reliability.** Set `response_mime_type: "application/json"` and low
   temperature in the API call, plus a markdown-fence-stripping fallback parser, plus
   validation that every returned `sub_industry` exists **exactly** in the taxonomy
   (hallucinated names are dropped, confidences clamped to 0–100).

6. **`is_market_hours()` bug in the spec.** The spec's version doesn't zero out
   microseconds in `replace()`, and more importantly the untouched `microsecond`
   makes `market_open <= local` comparisons slightly wrong at the boundary. Fixed
   with `microsecond=0`. (Market *holidays* still count as open — see #14.)

7. **One bad feed / one bad ticker must never kill the run.** Every feed fetch,
   Gemini call, yfinance lookup, and ntfy push is individually wrapped; failures log
   to stderr and the run continues, so `events.json` always gets written.

8. **Backtest measures confidence calibration, not just overall accuracy.** The
   report breaks T+1day accuracy down by confidence bucket (20–39, 40–59, …). If
   80–100 signals aren't more accurate than 20–39 ones, the confidence score is
   noise and the UI's "70%+" filter is meaningless — this is the single most useful
   diagnostic for retuning the prompt.

9. **Intraday price data limits handled.** yfinance only serves 1-minute bars for
   ~the last 7 days, so `price_tracker.py` uses 1m/1h intervals for recent
   checkpoints, and `backtest.py` (which looks at old events) explicitly uses daily
   bars with open/close proxies instead of pretending T+10min is measurable
   historically.

10. **Phase 4 built in but inert.** ntfy.sh pushes fire only if an `NTFY_TOPIC`
    secret is set (confidence ≥ 80 signals). No secret → silent no-op, matching the
    "placeholder, not error" principle.

11. **Offline fallback for data files.** The service worker is network-first for
    `*.json` but saves each successful response, so the app still shows the last
    signals when offline (the spec's network-first alone would show nothing).

---

## Recommended — needs your decision

12. **Two of the five RSS feed URLs are unreliable.** The spec-mandated Reuters feed
    (`reutersagency.com/feed/…`) was discontinued when Reuters Agency rebranded, and
    the AP feed goes through `rsshub.app`, a free public proxy that rate-limits
    aggressively. The code keeps them (they fail gracefully), but expect most runs to
    have 3 working sources. Good replacements: CNBC has multiple topic feeds,
    `feeds.a.dj.com/rss/RSSMarketsMain.xml` (WSJ Markets), Seeking Alpha
    (`seekingalpha.com/market_currents.xml`), and Investing.com RSS.

13. **The biggest design flaw: "direction is ALWAYS up" makes bad news a buy
    signal.** The LLM must list every *materially affected* industry, and every one is
    labeled `up`. A headline like "FAA grounds Boeing fleet" will classify Regional
    Airlines with high confidence — and EDDY will surface JETS/UAL/DAL as *buy*
    signals. Long-only doesn't require this: let the LLM return `up`/`down` per
    industry and simply *filter to only the ups* for signals. Same long-only product,
    dramatically better signal quality. This is a one-line prompt change + one filter
    line, but it changes spec behavior, so I left it as specced.

14. **Market holidays count as market hours.** `is_market_hours()` only checks
    weekends. On Thanksgiving, signals get logged with `market_hours: true` and
    T+10min checkpoints that can't exist. `pandas_market_calendars` (free) fixes
    this properly; a hardcoded NYSE holiday list is the zero-dependency version.

15. **Accuracy needs a baseline to mean anything.** Stocks drift up ~53% of days
    anyway, so 55% raw "did it go up" accuracy is barely above coin-flip-with-drift.
    Event studies normally measure *abnormal* return: `ticker return − SPY return`
    over the same window. One extra yfinance call per checkpoint. Strongly
    recommended before trusting the Phase 3 gate.

16. **`history.json` grows forever.** Append-only with ~all mapped tickers logged
    per event, it will hit thousands of entries within weeks, slowing every cron run
    (each unresolved signal is a yfinance call) and bloating the repo. Suggest:
    only log signals with confidence ≥ 60, and archive fully-resolved signals older
    than 90 days to a `history-archive.json`.

17. **`google-generativeai` SDK is deprecated.** Google replaced it with the
    `google-genai` package (`from google import genai`). The old one still works but
    stopped getting new models/features in 2025. Kept per spec; migration is ~10
    lines in `correlations.py` (`get_model()` only).

18. **GitHub Actions cron is best-effort, not exact.** `*/30` frequently runs
    5–20 minutes late (sometimes skipped entirely at peak hours), and the Phase 4
    ambition of "5-min cron refresh" is not realistic on free Actions. For true
    5-minute freshness you'd need an external pinger (e.g. cron-job.org hitting a
    `repository_dispatch` webhook — still $0).

19. **T+10min/T+1hr checkpoints depend on run timing.** The tracker back-fills the
    correct historical minute-bar, so a delayed run still measures the right price —
    but only within yfinance's ~7-day 1-minute window. Fine in steady state; just
    don't pause the workflow for a week with unresolved signals pending.

20. **Portfolio export/commit loop is the clunkiest UX in the app.** Works as
    specced, but a nicer $0 option: store the portfolio in a GitHub Gist via a
    fine-grained PAT entered once in Settings (gist scope only). The PWA can then
    read *and write* it, and the cron job can read it. Middle ground with zero
    tokens: the current export button.

21. **Near-duplicate headlines aren't deduped across sources.** MD5 of the lowercased
    title only catches exact matches; "Oil prices surge after Gulf attack" (Reuters)
    and "Oil surges following attack in Gulf" (CNBC) both spend a Gemini call and
    both appear on the board. Cheap fix: normalized-token-set similarity check
    against the last ~100 headlines before classifying.

22. **`pytz` can be dropped.** Python 3.9+ has `zoneinfo` in the stdlib
    (`ZoneInfo("America/New_York")`) — one less dependency. Kept pytz per spec.

23. **Ticker coverage is thin.** Only 31 of ~180 taxonomy sub-industries map to
    tickers, so most classified events surface zero signals. Notably missing:
    Electric Utilities (XLU), Regional Banks (KRE), Railroads (UNP/CSX), Copper
    (FCX/COPX), Agricultural Chemicals (MOS/NTR), Cryptocurrency (COIN/IBIT), Space
    & Satellite (RKLB/ARKX), Homebuilders (ITB). Also note the spec's map contains
    "Trucking", which isn't in the taxonomy (spec calls the sub-industry
    "Trucks & Other Vehicles") — so that entry can never fire. Expanding the map is
    pure data entry and the highest-leverage Phase 2 improvement.

24. **Consider `fetch` freshness vs. GitHub Pages CDN.** Pages caches with
    `max-age=600`, so even with `cache: no-store` the CDN may serve up-to-10-minute-old
    JSON. Acceptable for a 30-min cadence; worth knowing before wondering why a
    manual Action run doesn't show up instantly.

---

**My top 3 if you only act on a few:** #13 (direction), #15 (SPY baseline), #23
(ticker coverage). #13 and #15 directly determine whether the Phase 3 gate means
anything; #23 determines whether the app produces signals at all.
