# Spike: can a free-data daily agent job work?

Throwaway feasibility spike, 2026-10-29. Not production code.

**Question:** At a 07:00 CET run, can a scheduled Claude agent get everything
it needs from free sources only: the universe, daily bars, fundamentals,
earnings dates, news, and macro?

## Phases

| # | What | Status |
|---|---|---|
| 1 | Local probe of every free source (`probe.py`) | **Done**, with and without keys |
| 2 | The same probe inside a Claude Code cloud session, plus web search (`cloud-task-prompt.md`) | **Passed** 2026-10-29 17:30 UTC. Report on branch `claude/spike-free-data-probe`. |
| 3 | Push to the repo triggers the hashira Pages deploy (minimal static page) | Not started |

## Phase 1 results (local, no keys, 2026-10-29 16:45 UTC)

| Source | Need | Result |
|---|---|---|
| Wikipedia S&P 500 / 400 | Universe | ✅ 503 + 400 tickers parsed |
| SEC EDGAR (tickers, submissions, XBRL company facts) | Fundamentals, filings, Form 4 | ✅ All 200. Facts current to the 2026-06-27 period. |
| Nasdaq earnings calendar (unofficial) | Earnings dates | ✅ 303 reporting today, 610 on 11-05. Includes pre/after-market timing, consensus EPS and number of estimates. |
| Massive grouped daily (keyed) | Daily bars, whole market in one call | ✅ 2026-10-28: 12,613 tickers in one call. 2026-10-29: 403 at 13:06 ET, which confirms the after-00:00-ET unlock rule. |
| Massive reference splits (keyed) | Re-adjusting stored history | ✅ Also lists upcoming splits |
| Finnhub free (keyed) | Same-day quote, earnings calendar, company news, recommendation trends, basic financials | ✅ All 200 |
| Finnhub free (keyed) | Price target, EPS estimates, daily candles | ❌ 403, premium only |
| FRED (keyed) | 10-year yield and other macro series | ✅ Latest 2026-10-27, the normal 1–2 day publication lag |
| Stooq | Daily bars (fallback) | ❌ JavaScript proof-of-work bot check in front of CSV downloads. Excluded; not circumvented. |
| Yahoo chart API | Daily bars (fallback) | ❌ 429 even from a residential IP. Its terms also forbid redistribution. |

## Timing: run at 07:00 CET

- A run at 03:00 CET (21:00–22:00 ET) gets data **one session old**. Massive's
  free plan only releases a day's bars after 00:00 ET.
- **Decision (2026-10-29): run at 07:00 CET.** The probe shows `stale=0` on
  every sampled date, including both daylight-saving periods.
- FRED's keyless graph CSV refuses scripted clients (HTTP/2 stream errors), so
  FRED keeps the keyed API.

## Running it

```bash
cp .env.example .env        # fill in the keys; .env is gitignored
python3 probe.py --out results/local-keyed.json
# In a cloud session, keys come from network secrets instead:
python3 probe.py --proxy-auth --out results/cloud.json
```

The Massive probe sleeps 13 s between calls to stay under the free limit of 5 calls/min.

## Phase 2 results (cloud session, 2026-10-29 17:30 UTC)

- **Every needed source works through the agent proxy:** Wikipedia, SEC,
  Massive, Finnhub, Nasdaq and FRED. Massive and Finnhub authenticated with
  **proxy-injected network secrets**; no key was in the session.
- **Push works:** the run committed its report and pushed to a `claude/` branch.
- Run took about 4 minutes in total, 76 s of it the probe. 30 s of that was the
  dead FRED CSV timeout, so drop that probe.
- **Web search works, but can't be trusted for numbers.** Earnings dates
  conflicted across sites, price-target consensus was stale or undated, and
  breadth results were 2018–2025. Implications:
  - Hard numbers come from structured APIs: earnings dates from the Finnhub
    and Nasdaq calendars, and breadth **computed** from Massive grouped daily.
  - Web search is for qualitative catalysts only, and every claim must carry a
    date.
- Stooq was blocked by the allowlist. That's expected, since it isn't listed
  and was already dropped.
