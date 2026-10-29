# =============================================================================
# Daily run stages. The agent drives them in order:
#
#   prepare  history update -> features for the scan universe -> regime,
#            breadth, sectors, macro, earnings calendar
#            -> runs/<as_of>/{market.json, universe.csv, features.json, earnings.json}
#   enrich   news, analyst trends, metrics and SEC filings for the tickers the
#            agent shortlisted -> runs/<as_of>/enrich.json
#   publish  validate runs/<as_of>/analysis.json, derive levels, update the
#            ledger, write the plaintext dashboard payload, encrypt it into
#            the public site
# =============================================================================
import csv
import datetime as dt
import os
import subprocess

from . import analysis as analysis_mod
from . import features as feat_mod
from . import history, ledger, sources, universe
from .common import REPO_ROOT, SITE_DATA_DIR, log, read_json, write_json

EARNINGS_AHEAD_DAYS = 45
NASDAQ_AHEAD_WEEKDAYS = 10
NEWS_LOOKBACK_DAYS = 10
FILINGS_LOOKBACK_DAYS = 30
MAX_ENRICH = 40
# A report this close can gap straight through any ATR stop; the prompt says
# not to list such names, and publish enforces it.
MIN_EARNINGS_SESSIONS = 4
FRED_SERIES = {"vix": "VIXCLS", "hy_oas": "BAMLH0A0HYM2", "ust10y": "DGS10", "curve_10y2y": "T10Y2Y"}
CSV_COLUMNS = ("ticker", "name", "sector", "index", "eligible", "close", "atr_pct", "chg_1d_pct",
               "ret_5d_pct", "ret_21d_pct", "ret_63d_pct", "ret_126d_pct", "rs_rank", "rs_rising",
               "trend_stack", "sma200_rising", "ext_ema21_atr", "close_vs_ema50_atr", "dist_52wh_atr",
               "pct_off_52wh", "base_range_15d_atr", "bars_since_squeeze", "prior_20d_high_dist_atr",
               "vol_ratio", "adv20_usd_m", "tags", "next_earnings", "earn_sessions")


def run_dir(root, as_of):
    return os.path.join(root, "runs", as_of)


def weekdays_between(start, end):
    """Weekdays in (start, end]. Holidays are ignored: a slight overcount is the safe direction."""
    if end <= start:
        return 0
    return sum(1 for i in range(1, (end - start).days + 1) if (start + dt.timedelta(days=i)).weekday() < 5)


# =============================================================================
# Earnings calendar (Finnhub, cross-checked with Nasdaq)
# =============================================================================
def _finnhub_calendar(start, end):
    """Finnhub caps one response at 1500 rows, so query in chunks and split full ones."""
    rows = sources.safe(sources.finnhub_earnings_calendar, start, end, default=[]) or []
    if len(rows) >= 1500 and (end - start).days > 0:
        mid = start + dt.timedelta(days=(end - start).days // 2)
        return _finnhub_calendar(start, mid) + _finnhub_calendar(mid + dt.timedelta(days=1), end)
    return rows


def build_earnings(as_of, tickers):
    wanted = set(tickers)
    finnhub = {}
    start = as_of - dt.timedelta(days=10)
    while start <= as_of + dt.timedelta(days=EARNINGS_AHEAD_DAYS):
        end = start + dt.timedelta(days=6)
        for row in _finnhub_calendar(start, end):
            if row["ticker"] in wanted:
                finnhub.setdefault(row["ticker"], []).append(row)
        start = end + dt.timedelta(days=1)

    nasdaq, day, checked = {}, as_of, 0
    while checked < NASDAQ_AHEAD_WEEKDAYS:
        day += dt.timedelta(days=1)
        if day.weekday() >= 5:
            continue
        checked += 1
        for row in sources.safe(sources.nasdaq_earnings, day, default=[]) or []:
            if row["ticker"] in wanted:
                nasdaq[row["ticker"]] = row

    out = {}
    for t in wanted:
        rows = sorted(finnhub.get(t, []), key=lambda r: r["date"])
        upcoming = [r for r in rows if r["date"] > as_of.isoformat()]
        recent = [r for r in rows if r["date"] <= as_of.isoformat()]
        nxt = dict(upcoming[0]) if upcoming else None
        nq = nasdaq.get(t)
        if nq and (not nxt or nq["date"] < nxt["date"]):
            nxt = {"ticker": t, "date": nq["date"], "hour": nq["time"]}
        if nxt:
            nxt["sources"] = [s for s, hit in (("finnhub", bool(upcoming)), ("nasdaq", bool(nq))) if hit]
            nxt["conflict"] = bool(upcoming and nq and upcoming[0]["date"] != nq["date"])
            if nq:
                nxt["nasdaq_eps_forecast"], nxt["nasdaq_n_estimates"] = nq["eps_forecast"], nq["n_estimates"]
            nxt["sessions_away"] = weekdays_between(as_of, dt.date.fromisoformat(nxt["date"]))
        out[t] = {"next": nxt, "last_reported": recent[-1]["date"] if recent else None}
    return out


# =============================================================================
# Prepare
# =============================================================================
def _macro():
    out = {}
    for name, series_id in FRED_SERIES.items():
        obs = sources.safe(sources.fred_series, series_id, 60, default=[]) or []
        if obs:
            last_date, last = obs[-1]
            prior = obs[-21][1] if len(obs) > 21 else None
            out[name] = {"series": series_id, "date": last_date, "value": last,
                         "chg_20obs": round(last - prior, 3) if prior is not None else None}
    return out


def prepare(root, update_history=True):
    members = universe.load(root)
    stored = sorted(set(members) | set(history.BENCHMARKS))
    if update_history:
        history.update(root, stored)
        history.refresh_splits(root)
    days, panel = history.load_panel(root, stored)
    if len(days) < feat_mod.MIN_BARS:
        raise SystemExit(f"only {len(days)} sessions stored; need {feat_mod.MIN_BARS} (run the backfill)")
    as_of = days[-1]
    scan = universe.scan_tickers(members)

    spy_by_day = {d: b[3] for d, b in zip(days, panel["SPY"]) if b}
    feats = {}
    for t in scan:
        f = feat_mod.ticker_features(panel[t], spy_by_day, days)
        if f:
            feats[t] = f
    feat_mod.finalize_rs(feats)

    benchmarks = {b: feat_mod.benchmark_state(panel[b]) for b in ("SPY", "QQQ", "IWM", "RSP", "DIA", "SMH")}
    spy63 = benchmarks["SPY"]["ret_63d_pct"] if benchmarks["SPY"] else None
    sectors = []
    for sector, etf in sorted(history.SECTOR_ETF.items()):
        st = feat_mod.benchmark_state(panel[etf])
        if st:
            members_in = [t for t in feats if members[t]["sector"] == sector]
            sectors.append({"sector": sector, "etf": etf, **{k: st[k] for k in ("ret_21d_pct", "ret_63d_pct", "risk_on_gate")},
                            "rs_63d_vs_spy": round(st["ret_63d_pct"] - spy63, 2) if spy63 is not None else None,
                            "members": len(members_in),
                            "pct_trend_stack": round(100 * sum(feats[t]["trend_stack"] for t in members_in) / len(members_in), 1)
                            if members_in else None})
    breadth = feat_mod.breadth(panel, list(feats), days)
    macro = _macro()
    vix = macro.get("vix", {}).get("value")
    earnings = build_earnings(as_of, list(feats))

    out_dir = run_dir(root, as_of.isoformat())
    for t, f in feats.items():
        nxt = earnings.get(t, {}).get("next")
        f["next_earnings"] = nxt["date"] if nxt else None
        f["earn_sessions"] = nxt["sessions_away"] if nxt else None
    _write_csv(os.path.join(out_dir, "universe.csv"), feats, members)
    write_json(os.path.join(out_dir, "features.json"),
               {t: {k: v for k, v in f.items() if not k.startswith("_")} for t, f in feats.items()}, compact=True)
    write_json(os.path.join(out_dir, "earnings.json"), earnings, compact=True)
    market = {
        "as_of": as_of.isoformat(),
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sessions_stored": len(days),
        "universe": {"scan_members": len(scan), "with_features": len(feats),
                     "eligible": sum(f["eligible"] for f in feats.values())},
        "benchmarks": benchmarks, "sectors": sectors, "breadth": breadth, "macro": macro,
        "baseline_regime": feat_mod.baseline_regime(benchmarks["SPY"], breadth, vix),
        "tag_counts": _tag_counts(feats),
        "data_quality": {
            "history_break_truncated": sorted(t for t, f in feats.items() if f.get("history_break")),
            "excluded_short_or_broken_history": sorted(set(scan) - set(feats)),
        },
        "earnings_coverage": {"with_next_date": sum(1 for e in earnings.values() if e["next"]),
                              "conflicts": sorted(t for t, e in earnings.items() if e["next"] and e["next"]["conflict"])},
    }
    write_json(os.path.join(out_dir, "market.json"), market)
    log("prepare.done", as_of=as_of.isoformat(), features=len(feats), out=out_dir)
    return out_dir


def _tag_counts(feats):
    counts = {}
    for f in feats.values():
        if f["eligible"]:
            for tag in f["tags"]:
                counts[tag] = counts.get(tag, 0) + 1
    return counts


def _write_csv(path, feats, members):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(CSV_COLUMNS)
        for t in sorted(feats, key=lambda k: -(feats[k]["rs_rank"] or 0)):
            f, m = feats[t], members[t]
            row = {"ticker": t, "name": m["name"], "sector": m["sector"], "index": m["index"], **f,
                   "tags": "|".join(f["tags"])}
            writer.writerow(["" if row.get(c) is None else row.get(c) for c in CSV_COLUMNS])


# =============================================================================
# Enrich
# =============================================================================
def latest_as_of(root):
    runs = os.path.join(root, "runs")
    dates = sorted(d for d in os.listdir(runs) if len(d) == 10) if os.path.isdir(runs) else []
    if not dates:
        raise SystemExit("no prepared run found (run `prepare` first)")
    return dates[-1]


def enrich(root, tickers, as_of=None):
    as_of = as_of or latest_as_of(root)
    out_dir = run_dir(root, as_of)
    feats = read_json(os.path.join(out_dir, "features.json"), {})
    tickers = [t.strip().upper() for t in tickers if t.strip()]
    unknown = [t for t in tickers if t not in feats]
    if unknown:
        raise SystemExit(f"not in today's feature table: {', '.join(unknown)}")
    if len(tickers) > MAX_ENRICH:
        raise SystemExit(f"at most {MAX_ENRICH} tickers per enrich call (Finnhub free-tier budget)")

    day = dt.date.fromisoformat(as_of)
    ciks = _cik_map(root)
    path = os.path.join(out_dir, "enrich.json")
    result = read_json(path, {})
    for t in tickers:
        cik = ciks.get(t) or ciks.get(t.replace(".", "-"))
        result[t] = {
            "news": sources.safe(sources.finnhub_company_news, t, day - dt.timedelta(days=NEWS_LOOKBACK_DAYS),
                                 day + dt.timedelta(days=1), default=[]),
            "recommendations": sources.safe(sources.finnhub_recommendations, t, default=[]),
            "metrics": sources.safe(sources.finnhub_metrics, t, default={}),
            "sec_filings": sources.safe(sources.sec_recent_filings, cik, day - dt.timedelta(days=FILINGS_LOOKBACK_DAYS),
                                        default=[]) if cik else [],
        }
        log("enrich.ticker", ticker=t, news=len(result[t]["news"] or []), filings=len(result[t]["sec_filings"] or []))
    write_json(path, result)
    return path


def _cik_map(root):
    path = os.path.join(root, "sec_ciks.json")
    cached = read_json(path)
    if cached and (dt.date.today() - dt.date.fromisoformat(cached["fetched"])).days < 7:
        return cached["ciks"]
    ciks = sources.safe(sources.sec_ticker_ciks, default=None)
    if ciks is None:
        return cached["ciks"] if cached else {}
    write_json(path, {"fetched": dt.date.today().isoformat(), "ciks": ciks}, compact=True)
    return ciks


# =============================================================================
# Publish
# =============================================================================
def publish(root, as_of=None, encrypt=True):
    as_of = as_of or latest_as_of(root)
    out_dir = run_dir(root, as_of)
    feats = read_json(os.path.join(out_dir, "features.json"))
    market = read_json(os.path.join(out_dir, "market.json"))
    earnings = read_json(os.path.join(out_dir, "earnings.json"), {})
    enriched = read_json(os.path.join(out_dir, "enrich.json"), {})
    raw = read_json(os.path.join(out_dir, "analysis.json"))
    if raw is None:
        raise SystemExit(f"{out_dir}/analysis.json not found")
    members = universe.load(root)
    unknown_member = {"name": "", "sector": "Unknown", "index": ""}
    result = analysis_mod.validate(raw, as_of, feats)

    for c in result["candidates"]:
        f = feats[c["ticker"]]
        c["levels"] = analysis_mod.levels(c, f)
        member = members.get(c["ticker"], unknown_member)  # index changes between runs
        c["name"], c["sector"] = member["name"], member["sector"]
        c["features"] = {k: f.get(k) for k in ("rs_rank", "rs_rising", "trend_stack", "ext_ema21_atr", "dist_52wh_atr",
                                               "pct_off_52wh", "atr_pct", "ret_21d_pct", "ret_63d_pct", "vol_ratio",
                                               "adv20_usd_m", "bars_since_squeeze", "tags")}
        nxt = (earnings.get(c["ticker"]) or {}).get("next")
        if nxt and nxt["sessions_away"] < MIN_EARNINGS_SESSIONS:
            raise analysis_mod.AnalysisError(
                f"{c['ticker']}: earnings {nxt['date']} are {nxt['sessions_away']} session(s) away; "
                f"candidates need >= {MIN_EARNINGS_SESSIONS} (move it to the watchlist)")
        c["earnings"] = nxt
        c["earnings_inside_horizon"] = bool(nxt and nxt["sessions_away"] <= c["horizon_sessions"])
        c["news"] = [n for n in (enriched.get(c["ticker"], {}).get("news") or [])[:5] if n.get("url", "").startswith("https://")]
    for item in result["watchlist"] + result["avoid"]:
        item["name"] = members.get(item["ticker"], unknown_member)["name"]
        item["close"] = feats[item["ticker"]]["close"]

    published_utc = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    picks = _update_ledger(root, as_of, result, feats, published_utc)
    day_payload = {"as_of": as_of, "generated_utc": published_utc,
                   "analysis": result,
                   "market": {k: market[k] for k in ("benchmarks", "sectors", "macro", "baseline_regime", "universe", "tag_counts")},
                   "breadth": market["breadth"]}
    dash = os.path.join(root, "dashboard")
    write_json(os.path.join(dash, "days", f"{as_of}.json"), day_payload, compact=True)
    write_json(os.path.join(dash, "ledger.json"), {"updated": as_of, "stats": ledger.stats(picks), "picks": picks}, compact=True)
    days = sorted(name[:10] for name in os.listdir(os.path.join(dash, "days")) if name.endswith(".json"))
    write_json(os.path.join(dash, "index.json"), {"latest": days[-1], "days": days}, compact=True)
    log("publish.payload", as_of=as_of, candidates=len(result["candidates"]), ledger=len(picks))
    if encrypt:
        encrypt_dashboard(dash)
    return dash


def _update_ledger(root, as_of, result, feats, published_utc):
    path = os.path.join(root, "ledger.json")
    picks = {p["id"]: p for p in read_json(path, [])}
    for c in result["candidates"]:
        pick = ledger.new_pick(as_of, c, c["levels"], feats[c["ticker"]], c["sector"], published_utc)
        picks.setdefault(pick["id"], pick)  # a re-publish never rewrites a past call
    tickers = sorted({p["ticker"] for p in picks.values()} | {"SPY"})
    days, panel = history.load_panel(root, tickers)
    for p in picks.values():
        if p["status"] in ("pending", "open") and panel.get(p["ticker"]):
            ledger.evaluate(p, days, panel[p["ticker"]], panel["SPY"])
    ordered = sorted(picks.values(), key=lambda p: (p["as_of"], p["ticker"]))
    write_json(path, ordered)
    return ordered


def encrypt_dashboard(dash_dir):
    """Encrypt the plaintext payload into the public site (Node: stdlib has no AES-GCM)."""
    script = os.path.join(REPO_ROOT, "tools", "encrypt-dashboard.mjs")
    subprocess.run(["node", script, "--src", dash_dir, "--dst", SITE_DATA_DIR], check=True)
    log("publish.encrypted", dst=SITE_DATA_DIR)
