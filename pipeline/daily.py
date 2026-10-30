# =============================================================================
# Daily run stages. The agent drives them in order:
#
#   prepare  history update -> features for the scan universe -> regime,
#            breadth, sectors, macro, earnings calendar
#            -> runs/<as_of>/{market.json, universe.csv, features.json, earnings.json,
#                             book.json (open positions with marks and flags)}
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

EARNINGS_AHEAD_DAYS = 100
EARNINGS_BACK_DAYS = 100     # far enough to find the last report, so the next one can be estimated
QUARTER_DAYS, QUARTER_SESSIONS = 91, 63
NASDAQ_AHEAD_WEEKDAYS = 10
NEWS_LOOKBACK_DAYS = 10
FILINGS_LOOKBACK_DAYS = 30
MAX_ENRICH = 40
# A report this close can gap straight through any ATR stop; the prompt says
# not to open such names, and publish enforces it. Later reports are held through.
MIN_EARNINGS_SESSIONS = 4
# The book: 2-6 month positions, so few names at a time and no sector pile-ups.
MAX_OPEN_POSITIONS, MAX_PER_SECTOR = 12, 3
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
    start = as_of - dt.timedelta(days=EARNINGS_BACK_DAYS)
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
        last = recent[-1]["date"] if recent else None
        if not nxt and last:
            # Nothing published yet: one quarter after the last report, flagged as an estimate.
            est = dt.date.fromisoformat(last) + dt.timedelta(days=QUARTER_DAYS)
            while est <= as_of:
                est += dt.timedelta(days=QUARTER_DAYS)
            nxt = {"ticker": t, "date": est.isoformat(), "hour": "", "estimated": True}
        if nxt:
            nxt.setdefault("estimated", False)
            nxt["sources"] = ["estimate"] if nxt["estimated"] else [
                s for s, hit in (("finnhub", bool(upcoming)), ("nasdaq", bool(nq))) if hit]
            nxt["conflict"] = bool(upcoming and nq and upcoming[0]["date"] != nq["date"])
            if nq:
                nxt["nasdaq_eps_forecast"], nxt["nasdaq_n_estimates"] = nq["eps_forecast"], nq["n_estimates"]
            nxt["sessions_away"] = weekdays_between(as_of, dt.date.fromisoformat(nxt["date"]))
        out[t] = {"next": nxt, "last_reported": last}
    return out


def reports_in_hold(nxt, horizon_sessions):
    """Earnings reports expected inside a hold of `horizon_sessions` (one per quarter after the next)."""
    if not nxt or nxt.get("sessions_away") is None or nxt["sessions_away"] > horizon_sessions:
        return 0
    return 1 + (horizon_sessions - nxt["sessions_away"]) // QUARTER_SESSIONS


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
    momentum = feat_mod.momentum_health(panel["MTUM"], panel["SPY"], panel["RSP"])
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
        "benchmarks": benchmarks, "sectors": sectors, "breadth": breadth, "macro": macro, "momentum": momentum,
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
    # The open book as of the last publish, so the agent reviews holdings before adding names.
    book = book_view(open_book(root, as_of.isoformat()), feats, earnings)
    write_json(os.path.join(out_dir, "book.json"), {"positions": book, "max_open": MAX_OPEN_POSITIONS,
                                                    "max_per_sector": MAX_PER_SECTOR})
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
def open_book(root, as_of):
    """Open position rows of the current rules opened before `as_of` (today's rows are this run's,
    so a re-publish stays idempotent)."""
    return [r for r in read_json(os.path.join(root, "ledger.json"), [])
            if ledger.version_of(r) == ledger.RULES_VERSION and ledger.is_open(r) and r["as_of"] < as_of]


def book_view(rows, feats, earnings, reviews=()):
    """Open positions with their mark and mechanical flags, for the agent and the dashboard."""
    notes = {r["ticker"]: r for r in reviews}
    out = []
    for r in rows:
        f = feats.get(r["ticker"]) or {}
        nxt = (earnings.get(r["ticker"]) or {}).get("next")
        mark = r.get("mark") or {}
        close, atr = f.get("close"), f.get("atr")
        flags = []
        if close and atr and close - r["stop"] < atr:
            flags.append("near_stop")
        if (f.get("close_vs_ema50_atr") or 0) < 0:
            flags.append("below_ema50")
        if f.get("rs_rank") is not None and f["rs_rank"] < 60:
            flags.append("rs_faded")
        if nxt and nxt.get("sessions_away") is not None and nxt["sessions_away"] <= 5:
            flags.append("earnings_soon")
        if r.get("horizon_sessions") and mark.get("sessions", 0) >= r["horizon_sessions"]:
            flags.append("review_due")
        if r.get("targets_hit") and r["targets_hit"][0]:
            flags.append("upside_reached")
        out.append({"ticker": r["ticker"], "sector": r["sector"], "as_of": r["as_of"], "status": r["status"],
                    "entry": r["entry"], "entry_date": r["entry_date"], "stop": r["stop"], "close": close,
                    "stop_dist_pct": round(100 * (r["stop"] / close - 1), 1) if close else None,
                    "position_pct": r.get("position_pct"), "horizon_sessions": r.get("horizon_sessions"),
                    "mark": mark or None, "next_earnings": nxt, "flags": flags, "review": notes.get(r["ticker"])})
    return out


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
    book = open_book(root, as_of)
    result = analysis_mod.validate(raw, as_of, feats, held={r["ticker"] for r in book})
    scale = (market.get("momentum") or {}).get("size_scale")

    if len(book) + len(result["candidates"]) > MAX_OPEN_POSITIONS:
        raise analysis_mod.AnalysisError(
            f"{len(book)} positions are open; at most {MAX_OPEN_POSITIONS} (exit one in 'reviews' first, or watchlist the new names)")
    sectors = {}
    for r in book:
        sectors[r["sector"]] = sectors.get(r["sector"], 0) + 1
    for c in result["candidates"]:
        f = feats[c["ticker"]]
        member = members.get(c["ticker"], unknown_member)  # index changes between runs
        c["name"], c["sector"] = member["name"], member["sector"]
        sectors[c["sector"]] = sectors.get(c["sector"], 0) + 1
        if sectors[c["sector"]] > MAX_PER_SECTOR:
            raise analysis_mod.AnalysisError(
                f"{c['ticker']}: would be position {sectors[c['sector']]} in {c['sector']} (max {MAX_PER_SECTOR})")
        nxt = (earnings.get(c["ticker"]) or {}).get("next")
        if nxt and nxt["sessions_away"] < MIN_EARNINGS_SESSIONS:
            raise analysis_mod.AnalysisError(
                f"{c['ticker']}: earnings {nxt['date']} are {nxt['sessions_away']} session(s) away; "
                f"new positions need >= {MIN_EARNINGS_SESSIONS} (move it to the watchlist)")
        c["levels"] = analysis_mod.levels(c, f)
        c["levels"]["position_pct"] = analysis_mod.position_size(
            c["levels"]["stop_pct"], scale, nxt["sessions_away"] if nxt else None)
        c["features"] = {k: f.get(k) for k in ("rs_rank", "rs_rising", "trend_stack", "ext_ema21_atr", "dist_52wh_atr",
                                               "pct_off_52wh", "atr_pct", "ret_21d_pct", "ret_63d_pct", "ret_126d_pct",
                                               "vol_ratio", "adv20_usd_m", "bars_since_squeeze", "tags")}
        c["earnings"] = nxt
        c["reports_in_hold"] = reports_in_hold(nxt, c["horizon_sessions"])
        c["news"] = [n for n in (enriched.get(c["ticker"], {}).get("news") or [])[:5] if n.get("url", "").startswith("https://")]
    for item in result["watchlist"] + result["avoid"]:
        item["name"] = members.get(item["ticker"], unknown_member)["name"]
        item["close"] = feats[item["ticker"]]["close"]

    published_utc = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    picks = _update_ledger(root, as_of, result, feats, published_utc, scale)
    risk_on = bool((market["benchmarks"].get("SPY") or {}).get("risk_on_gate"))
    control = _update_control(root, as_of, feats, risk_on, earnings, members, picks, published_utc, scale)
    held = [p for p in picks if ledger.version_of(p) == ledger.RULES_VERSION and ledger.is_open(p) and p["as_of"] < as_of]
    day_payload = {"as_of": as_of, "generated_utc": published_utc,
                   "analysis": result,
                   "book": book_view(held, feats, earnings, result["reviews"]),
                   "limits": {"max_open": MAX_OPEN_POSITIONS, "max_per_sector": MAX_PER_SECTOR,
                              "max_new": analysis_mod.MAX_CANDIDATES,
                              "risk_per_trade_pct": analysis_mod.RISK_PER_TRADE_PCT},
                   "market": {k: market[k] for k in ("benchmarks", "sectors", "macro", "baseline_regime", "universe", "tag_counts")},
                   "momentum": market.get("momentum"),
                   "breadth": market["breadth"]}
    dash = os.path.join(root, "dashboard")
    write_json(os.path.join(dash, "days", f"{as_of}.json"), day_payload, compact=True)
    write_json(os.path.join(dash, "ledger.json"), {"updated": as_of, "stats": ledger.stats(picks), "picks": picks,
                                                   "control": ledger.control_stats(control)}, compact=True)
    days = sorted(name[:10] for name in os.listdir(os.path.join(dash, "days")) if name.endswith(".json"))
    write_json(os.path.join(dash, "index.json"), {"latest": days[-1], "days": days}, compact=True)
    log("publish.payload", as_of=as_of, candidates=len(result["candidates"]), ledger=len(picks), book=len(held))
    if encrypt:
        encrypt_dashboard(dash)
    return dash


def _update_ledger(root, as_of, result, feats, published_utc, scale=None):
    path = os.path.join(root, "ledger.json")
    picks = {p["id"]: p for p in read_json(path, [])}
    for c in result["candidates"]:
        pick = ledger.new_pick(as_of, c, c["levels"], feats[c["ticker"]], c["sector"], published_utc, scale)
        picks.setdefault(pick["id"], pick)  # a re-publish never rewrites a past call
    return _evaluate_and_write(root, path, picks)


def _update_control(root, as_of, feats, risk_on, earnings, members, picks, published_utc, scale=None):
    """Track every in-context mechanical signal of `as_of` at fixed levels (see ledger.py).
    Same hard earnings rule as new positions, one open row per ticker. `picked` follows the
    ledger, so a re-publish keeps it in step; outcomes are never rewritten."""
    path = os.path.join(root, "control.json")
    rows = {r["id"]: r for r in read_json(path, [])}
    picked = {p["ticker"] for p in picks if p["as_of"] == as_of}
    held = {r["ticker"] for r in rows.values()
            if ledger.version_of(r) == ledger.RULES_VERSION and ledger.is_open(r) and r["as_of"] < as_of}
    for ticker, f in sorted(feats.items()):
        setup = ledger.control_setup(f, risk_on)
        nxt = (earnings.get(ticker) or {}).get("next")
        if not setup or ticker in held or (nxt and nxt["sessions_away"] < MIN_EARNINGS_SESSIONS):
            continue
        c = {"ticker": ticker, "setup": setup, "conviction": 0, "stop_atr": ledger.CONTROL_STOP_ATR,
             "max_chase_atr": ledger.CONTROL_CHASE_ATR, "horizon_sessions": max(ledger.HORIZONS)}
        sector = members.get(ticker, {}).get("sector", "Unknown")
        row = ledger.new_pick(as_of, c, analysis_mod.levels(c, f), f, sector, published_utc, scale)
        rows.setdefault(row["id"], row)
    for r in rows.values():
        if r["as_of"] == as_of:
            r["picked"] = r["ticker"] in picked
    return _evaluate_and_write(root, path, rows)


def _evaluate_and_write(root, path, rows):
    for r in rows.values():
        r.setdefault("rules_version", "v1")  # rows written before rules versioning
    tickers = sorted({r["ticker"] for r in rows.values()} | {"SPY", "RSP"})
    days, panel = history.load_panel(root, tickers)
    splits = history.split_factors(read_json(history._paths(root)["splits"], []), days[-1]) if days else {}
    for r in rows.values():
        if ledger.is_open(r) and panel.get(r["ticker"]):
            bars = to_pick_basis(panel[r["ticker"]], splits.get(r["ticker"]), r["as_of"])
            ledger.evaluate(r, days, bars, panel["SPY"], panel.get("RSP"))
    ordered = sorted(rows.values(), key=lambda r: (r["as_of"], r["ticker"]))
    write_json(path, ordered)
    return ordered


def to_pick_basis(bars, factors, as_of):
    """Split-adjusted bars (today's share basis) back into the basis of the pick date, so a split
    during the hold can't move the stored stop and entry limit."""
    f = 1.0
    for ex, factor in factors or []:
        if ex.isoformat() > as_of:
            f *= factor
    if f == 1.0:
        return bars
    return [None if b is None else (b[0] / f, b[1] / f, b[2] / f, b[3] / f, b[4] * f) for b in bars]


def node_ts_args(version):
    """Node flags to run a .ts file: none from 22.18 (types stripped by default),
    --experimental-strip-types on 22.6-22.17, and older Node can't run it."""
    major, minor = (int(x) for x in version.lstrip("v").split(".")[:2])
    if (major, minor) >= (22, 18) or major >= 23:
        return []
    if (major, minor) >= (22, 6):
        return ["--experimental-strip-types"]
    raise RuntimeError(f"Node {version} can't run tools/*.ts; need >= 22.6 (22.18+ preferred)")


def encrypt_dashboard(dash_dir):
    """Encrypt the plaintext payload into the public site (Node: stdlib has no AES-GCM)."""
    script = os.path.join(REPO_ROOT, "tools", "encrypt-dashboard.ts")
    version = subprocess.run(["node", "--version"], check=True, capture_output=True, text=True).stdout.strip()
    subprocess.run(["node", *node_ts_args(version), script, "--src", dash_dir, "--dst", SITE_DATA_DIR], check=True)
    log("publish.encrypted", dst=SITE_DATA_DIR)
