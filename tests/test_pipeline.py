"""Pipeline unit tests (stdlib unittest): python3 -m unittest discover -s tests -p 'test_*.py'"""
import datetime as dt
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import analysis, daily, features, history, ledger  # noqa: E402


def days_from(start, n):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


class SeriesMath(unittest.TestCase):
    def test_sma_and_ema(self):
        self.assertEqual(features.sma([1, 2, 3, 4], 2), [None, 1.5, 2.5, 3.5])
        e = features.ema([10.0] * 5, 3)
        self.assertTrue(all(abs(x - 10.0) < 1e-12 for x in e))

    def test_atr_constant_range(self):
        highs, lows, closes = [11.0] * 30, [9.0] * 30, [10.0] * 30
        atr = features.atr_wilder(highs, lows, closes, 14)
        self.assertIsNone(atr[12])
        self.assertAlmostEqual(atr[-1], 2.0)

    def test_percentile_ranks(self):
        ranks = features.percentile_ranks({"a": 1, "b": 3, "c": 2, "d": None})
        self.assertEqual(ranks, {"a": 0.0, "c": 50.0, "b": 100.0})


class TickerFeatures(unittest.TestCase):
    def _trend(self, n=260, drift=0.002):
        days = days_from(dt.date(2025, 1, 1), n)
        bars, price = [], 50.0
        for i in range(n):
            price *= 1 + drift + (0.004 if i % 2 else -0.003)
            bars.append((price * 0.995, price * 1.01, price * 0.99, price, 2_000_000))
        return days, bars

    def test_uptrend_is_stacked_and_eligible(self):
        days, bars = self._trend()
        spy = {d: 100.0 for d in days}
        f = features.ticker_features(bars, spy, days)
        self.assertTrue(f["trend_stack"])
        self.assertTrue(f["eligible"])
        self.assertGreater(f["ret_63d_pct"], 0)
        self.assertTrue(f["rs_rising"])

    def test_short_history_and_missing_last_bar(self):
        days, bars = self._trend(n=150)
        self.assertIsNone(features.ticker_features(bars, {}, days))
        days, bars = self._trend()
        bars[-1] = None
        self.assertIsNone(features.ticker_features(bars, {}, days))

    def test_illiquid_or_penny_is_ineligible(self):
        days, bars = self._trend()
        thin = [(o, h, l, c, 1000) for o, h, l, c, _ in bars]
        self.assertFalse(features.ticker_features(thin, {}, days)["eligible"])
        penny = [(o / 20, h / 20, l / 20, c / 20, v) for o, h, l, c, v in bars]
        self.assertFalse(features.ticker_features(penny, {}, days)["eligible"])


class SplitAdjustment(unittest.TestCase):
    def test_4_for_1_split_has_no_fake_crash(self):
        days = days_from(dt.date(2026, 1, 5), 4)
        raw = [(400, 404, 396, 400, 100), (400, 404, 396, 400, 100), (100, 101, 99, 100, 400), (101, 102, 100, 101, 400)]
        splits = [{"ticker": "X", "execution_date": days[2].isoformat(), "split_from": 1, "split_to": 4}]
        adj = history.adjust_series(days, raw, history.split_factors(splits, days[-1])["X"])
        self.assertAlmostEqual(adj[0][3], 100.0)
        self.assertAlmostEqual(adj[0][4], 400.0)
        self.assertEqual(adj[2], raw[2])

    def test_future_split_not_applied(self):
        days = days_from(dt.date(2026, 1, 5), 2)
        splits = [{"ticker": "X", "execution_date": "2027-01-13", "split_from": 1, "split_to": 2}]
        self.assertEqual(history.split_factors(splits, days[-1]), {})


FEATS = {"AAA": {"eligible": True, "close": 100.0, "atr": 2.0}, "BBB": {"eligible": False, "close": 4.0, "atr": 0.2},
         "WILD": {"eligible": True, "close": 100.0, "atr": 4.0}}


def good_analysis(**overrides):
    cand = {"ticker": "AAA", "setup": "breakout", "conviction": 4, "thesis": "Tight base under highs, RS leader.",
            "stop_atr": 4.5, "max_chase_atr": 0.5, "horizon_sessions": 84,
            "upside_case": "Two more beat-and-raise quarters re-rate it toward the sector multiple.",
            "earnings_plan": "Hold through the next report at full size; it is 40 sessions away.",
            "invalidation": "Close back inside the base.", "risks": ["Market reversal"],
            "catalysts": [{"date": "2026-10-28", "text": "Guidance raise", "source_url": "https://example.com/x"}]}
    cand.update(overrides)
    return {"as_of": "2026-10-29", "contract": "v2", "prompt_version": "v2.0",
            "regime": {"label": "risk_on", "exposure": "full", "summary": "Broad strength.", "evidence": ["SPY > EMA50"]},
            "candidates": [cand]}


class AnalysisValidation(unittest.TestCase):
    def test_valid_and_levels(self):
        out = analysis.validate(good_analysis(), "2026-10-29", FEATS)
        c = out["candidates"][0]
        lv = analysis.levels(c, FEATS["AAA"])
        self.assertEqual(lv["stop"], 91.0)          # 4.5 ATR
        self.assertEqual(lv["entry_max"], 101.0)
        self.assertEqual(lv["targets"], [120.0])    # the +20% reference, not an exit
        self.assertEqual(lv["targets_r"], [2.22])

    def test_position_size(self):
        self.assertEqual(analysis.position_size(-9.0, 1.0, 40), 11.1)    # 1% risk / 9% stop
        self.assertEqual(analysis.position_size(-9.0, 0.23, 40), 2.6)    # x momentum scale
        self.assertEqual(analysis.position_size(-9.0, 0.23, 10), 1.3)    # report under 15 sessions: half
        self.assertEqual(analysis.position_size(-3.0, 1.0, None), 15.0)  # capped
        self.assertIsNone(analysis.position_size(0, 1.0, None))

    def test_rejections(self):
        cases = [
            (dict(ticker="ZZZ"), "not in today's feature table"),
            (dict(ticker="BBB"), "price/liquidity floor"),
            (dict(stop_atr=2), "outside"),
            (dict(horizon_sessions=20), "outside"),
            (dict(ticker="WILD", stop_atr=4.5), "max 15"),
            (dict(setup="moonshot"), "setup must be"),
            (dict(upside_case=""), "empty"),
            (dict(catalysts=[{"date": "soon", "text": "x"}]), "undated"),
            (dict(catalysts=[{"date": "2026-10-01", "text": "x", "source_url": "http://x"}]), "https"),
        ]
        for override, msg in cases:
            with self.subTest(msg=msg):
                with self.assertRaisesRegex(analysis.AnalysisError, msg):
                    analysis.validate(good_analysis(**override), "2026-10-29", FEATS)

    def test_contract_held_names_and_reviews(self):
        raw = good_analysis()
        del raw["contract"]
        with self.assertRaisesRegex(analysis.AnalysisError, "contract"):
            analysis.validate(raw, "2026-10-29", FEATS)
        with self.assertRaisesRegex(analysis.AnalysisError, "already held"):
            analysis.validate(good_analysis(), "2026-10-29", FEATS, held={"AAA"})
        raw = good_analysis()
        raw["candidates"] = raw["candidates"] * 3
        with self.assertRaisesRegex(analysis.AnalysisError, "duplicate|at most 2"):
            analysis.validate(raw, "2026-10-29", FEATS)
        raw = good_analysis(ticker="WILD", stop_atr=3)
        raw["reviews"] = [{"ticker": "AAA", "action": "trim", "note": "Lost the 50-day."}]
        out = analysis.validate(raw, "2026-10-29", FEATS, held={"AAA"})
        self.assertEqual(out["reviews"][0]["action"], "trim")
        raw["reviews"][0]["ticker"] = "ZZZ"
        with self.assertRaisesRegex(analysis.AnalysisError, "not an open position"):
            analysis.validate(raw, "2026-10-29", FEATS, held={"AAA"})

    def test_wrong_as_of_and_none_exposure(self):
        with self.assertRaisesRegex(analysis.AnalysisError, "as_of"):
            analysis.validate(good_analysis(), "2026-10-30", FEATS)
        raw = good_analysis()
        raw["regime"]["exposure"] = "none"
        with self.assertRaisesRegex(analysis.AnalysisError, "exposure is 'none'"):
            analysis.validate(raw, "2026-10-29", FEATS)


class LedgerFills(unittest.TestCase):
    """Pick AAA: close 100, ATR 2, stop 4.5 ATR = 91, buy up to 101, +20% reference 120."""

    def _pick(self):
        c = analysis.validate(good_analysis(), "2026-10-29", FEATS)["candidates"][0]
        return ledger.new_pick("2026-10-29", c, analysis.levels(c, FEATS["AAA"]), FEATS["AAA"], "Tech",
                               "2026-10-30T06:05:00+00:00")  # 07:05 CET, before the 10-30 open

    def _days(self, n):
        return days_from(dt.date(2026, 10, 29), n + 1)

    def test_not_filled_when_open_above_chase_limit(self):
        days = self._days(1)
        bars = [None, (102, 103, 101, 102, 1)]
        p = ledger.evaluate(self._pick(), days, bars, bars)
        self.assertEqual(p["status"], "not_filled")

    def test_gap_below_stop(self):
        days = self._days(1)
        p = ledger.evaluate(self._pick(), days, [None, (90, 91, 89, 90, 1)], [None, (1, 1, 1, 1, 1)])
        self.assertEqual(p["status"], "gap_below_stop")

    def test_stop_hit_exits_at_stop_minus_costs(self):
        days = self._days(3)
        bars = [None, (100, 101, 99, 100, 1), (99, 99.5, 90, 92, 1), (92, 93, 91.5, 92, 1)]
        p = ledger.evaluate(self._pick(), days, bars, bars)
        self.assertEqual(p["status"], "stopped")
        self.assertAlmostEqual(p["exit_r"], -1.0 - 0.002 * 100 / 9, places=2)
        self.assertAlmostEqual(p["exit_pct"], -9.0 - 0.2, places=2)

    def test_gap_through_stop_fills_at_open(self):
        days = self._days(2)
        bars = [None, (100, 101, 99, 100, 1), (85, 86, 84, 85, 1)]
        p = ledger.evaluate(self._pick(), days, bars, bars)
        self.assertAlmostEqual(p["exit_r"], (85 - 100) / 9 - 0.002 * 100 / 9, places=2)

    def test_horizons_benchmarks_and_completion(self):
        n = max(ledger.HORIZONS)
        days = self._days(n)
        bars = [None] + [(100 + i * 0.2, 101 + i * 0.2, 99.5 + i * 0.2, 100.5 + i * 0.2, 1) for i in range(n)]
        flat = [None] + [(100, 100, 100, 100, 1)] * n
        p = ledger.evaluate(self._pick(), days, bars, flat, flat)
        self.assertEqual(p["status"], "complete")
        self.assertEqual(set(p["pct"]), {"21", "42", "63", "126"})
        self.assertEqual(p["pct"]["126"], round(100 * (125.5 / 100 - 1) - 0.2, 2))
        self.assertEqual((p["spy_pct"]["126"], p["rsp_pct"]["126"]), (0.0, 0.0))
        self.assertTrue(p["targets_hit"][0])  # +20% traded
        s = ledger.stats([p])
        self.assertEqual(s["all"]["n_126"], 1)
        self.assertEqual(s["all"]["avg_ex_rsp_126"], p["pct"]["126"])
        self.assertEqual(s["all"]["reached_upside"], 1)
        self.assertTrue(s["all"]["low_sample"])

    def test_open_position_has_a_mark(self):
        days = self._days(5)
        bars = [None] + [(100, 102, 99, 101, 1)] * 5
        p = ledger.evaluate(self._pick(), days, bars, bars, bars)
        self.assertEqual(p["status"], "open")
        self.assertEqual(p["mark"]["sessions"], 5)
        self.assertEqual(p["mark"]["pct"], 0.8)
        self.assertEqual(p["mark"]["rsp_pct"], 1.0)

    def test_entry_bar_outside_window_is_left_alone(self):
        days = days_from(dt.date(2026, 11, 2), 3)  # the window starts after the pick date
        bars = [(130, 131, 129, 130, 1)] * 3
        p = ledger.evaluate(self._pick(), days, bars, bars)
        self.assertEqual(p["status"], "pending")

    def test_pending_without_new_bars(self):
        days = self._days(0)
        p = ledger.evaluate(self._pick(), days, [None], [None])
        self.assertEqual(p["status"], "pending")

    def test_split_during_hold_keeps_the_trade(self):
        # 4:1 split two sessions after entry. load_panel adjusts all bars to the new basis;
        # to_pick_basis must put them back in the pick's basis.
        days = self._days(4)
        raw = [(100, 100, 100, 100, 1), (100, 101, 99, 100, 1), (100, 102, 99.5, 101, 1),
               (25.5, 25.8, 25.2, 25.6, 4), (25.6, 26, 25.4, 25.9, 4)]
        splits = [{"ticker": "AAA", "execution_date": days[3].isoformat(), "split_from": 1, "split_to": 4}]
        factors = history.split_factors(splits, days[-1])["AAA"]
        adjusted = history.adjust_series(days, raw, factors)
        p = ledger.evaluate(self._pick(), days, daily.to_pick_basis(adjusted, factors, "2026-10-29"), raw)
        self.assertEqual(p["status"], "open")
        self.assertEqual(p["entry"], 100.0)
        self.assertEqual(p["mark"]["pct"], round(100 * (25.9 * 4 / 100 - 1) - 0.2, 2))


class EarningsInHold(unittest.TestCase):
    def test_reports_counted_per_quarter(self):
        self.assertEqual(daily.reports_in_hold(None, 126), 0)
        self.assertEqual(daily.reports_in_hold({"sessions_away": 130}, 126), 0)
        self.assertEqual(daily.reports_in_hold({"sessions_away": 10}, 42), 1)
        self.assertEqual(daily.reports_in_hold({"sessions_away": 10}, 126), 2)


if __name__ == "__main__":
    unittest.main()


class MomentumHealth(unittest.TestCase):
    @staticmethod
    def _bars(closes):
        return [(c, c, c, c, 1e6) for c in closes]

    def test_calm_spread_caps_scale_at_one(self):
        spy = [100 * 1.001 ** i for i in range(200)]
        mtum = [100 * 1.0012 ** i for i in range(200)]  # constant spread: ~zero spread vol
        out = features.momentum_health(self._bars(mtum), self._bars(spy), self._bars(spy))
        self.assertEqual(out["size_scale"], 1.0)
        self.assertGreater(out["mtum_vs_spy_63d_pct"], 0)

    def test_volatile_spread_sizes_down(self):
        spy = [100.0] * 200
        mtum = [100 * (1.02 if i % 2 else 0.98) for i in range(200)]  # 2% daily swings vs flat SPY
        out = features.momentum_health(self._bars(mtum), self._bars(spy), self._bars(spy))
        self.assertLess(out["size_scale"], 0.2)

    def test_short_history_is_none(self):
        bars = self._bars([100.0] * features.MOM_VOL_LEN)
        self.assertIsNone(features.momentum_health(bars, bars, bars))


class HistoryBreak(unittest.TestCase):
    def test_ticker_reuse_is_cut(self):
        bars = [(10, 10, 10, 10, 1)] * 5 + [None] + [(150, 151, 149, 150, 1)] * 3
        self.assertEqual(features.history_break(bars), 6)

    def test_continuous_series_is_untouched(self):
        bars = [(100, 101, 99, 100 + i, 1) for i in range(10)]
        self.assertEqual(features.history_break(bars), 0)

    def test_short_history_after_break_is_excluded(self):
        days = days_from(dt.date(2025, 1, 1), 260)
        bars = [(10.0, 10.1, 9.9, 10.0, 5e6)] * 100 + [(150.0, 151.0, 149.0, 150.0, 5e6)] * 160
        self.assertIsNone(features.ticker_features(bars, {}, days))


class LedgerPublishTime(unittest.TestCase):
    def test_publish_during_us_hours_skips_that_days_open(self):
        c = analysis.validate(good_analysis(), "2026-10-29", FEATS)["candidates"][0]
        # Published 2026-10-30 15:00 ET: the 10-30 open already printed.
        pick = ledger.new_pick("2026-10-29", c, analysis.levels(c, FEATS["AAA"]), FEATS["AAA"], "Tech",
                               "2026-10-30T19:00:00+00:00")
        days = days_from(dt.date(2026, 10, 29), 3)  # 10-29, 10-30, 11-02
        bars = [None, (100, 101, 99, 100, 1), (100.5, 102, 100, 101, 1)]
        p = ledger.evaluate(pick, days, bars, bars)
        self.assertEqual(p["entry_date"], "2026-11-02")
        self.assertEqual(p["entry"], 100.5)

    def test_publish_before_open_fills_that_day(self):
        c = analysis.validate(good_analysis(), "2026-10-29", FEATS)["candidates"][0]
        pick = ledger.new_pick("2026-10-29", c, analysis.levels(c, FEATS["AAA"]), FEATS["AAA"], "Tech",
                               "2026-10-30T06:05:00+00:00")
        days = days_from(dt.date(2026, 10, 29), 2)
        p = ledger.evaluate(pick, days, [None, (100, 101, 99, 100, 1)], [None, (1, 1, 1, 1, 1)])
        self.assertEqual(p["entry_date"], "2026-10-30")


class NodeTsFlags(unittest.TestCase):
    def test_flags_by_node_version(self):
        self.assertEqual(daily.node_ts_args("v26.2.0"), [])
        self.assertEqual(daily.node_ts_args("v22.18.0"), [])
        self.assertEqual(daily.node_ts_args("v22.12.0"), ["--experimental-strip-types"])
        with self.assertRaises(RuntimeError):
            daily.node_ts_args("v20.11.1")


class RepoHygiene(unittest.TestCase):
    """`ship` commits site/data; an ignore rule matching it silently breaks every publish."""

    def _ignored(self, path):
        import subprocess
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return subprocess.run(["git", "-C", root, "check-ignore", "-q", path]).returncode == 0

    def test_encrypted_site_data_is_trackable(self):
        self.assertFalse(self._ignored("site/data/index.json"))
        self.assertFalse(self._ignored("site/data/days/2026-10-28.json"))

    def test_local_research_data_stays_ignored(self):
        self.assertTrue(self._ignored("data/AAPL.csv"))
        self.assertTrue(self._ignored(".env"))


def control_feat(**overrides):
    f = {"eligible": True, "close": 100.0, "atr": 2.0, "trend_stack": True, "rs_rising": True,
         "ext_ema21_atr": 1.5, "tags": ["breakout", "volume_surge"]}
    f.update(overrides)
    return f


class ControlArm(unittest.TestCase):
    def test_signal_mirrors_chart_check(self):
        self.assertEqual(ledger.control_setup(control_feat(), True), "breakout")
        self.assertEqual(ledger.control_setup(control_feat(tags=["pullback_reclaim"]), True), "pullback_reclaim")
        self.assertIsNone(ledger.control_setup(control_feat(tags=["breakout"]), True))  # low volume
        self.assertIsNone(ledger.control_setup(control_feat(), False))  # SPY gate off
        self.assertIsNone(ledger.control_setup(control_feat(ext_ema21_atr=4.5), True))
        self.assertIsNone(ledger.control_setup(control_feat(rs_rising=False), True))
        self.assertIsNone(ledger.control_setup(control_feat(eligible=False), True))

    def _run(self, root, picks, earnings=None):
        feats = {"AAA": control_feat(), "BBB": control_feat(tags=["pullback_reclaim"]),
                 "CCC": control_feat(), "DDD": control_feat(tags=[])}
        days = days_from(dt.date(2026, 10, 29), 1)
        panel = {t: [(100, 101, 99, 100, 1)] for t in ("AAA", "BBB", "CCC", "SPY")}
        with mock.patch.object(history, "load_panel", return_value=(days, panel)):
            return daily._update_control(root, "2026-10-29", feats, True, earnings or {}, {}, picks,
                                         "2026-10-30T06:05:00+00:00")

    def test_tracks_signals_with_fixed_levels_and_picked_flag(self):
        with tempfile.TemporaryDirectory() as root:
            rows = self._run(root, [{"as_of": "2026-10-29", "ticker": "AAA"}],
                             earnings={"CCC": {"next": {"sessions_away": 2}}})
            self.assertEqual([(r["ticker"], r["setup"], r["picked"]) for r in rows],
                             [("AAA", "breakout", True), ("BBB", "pullback_reclaim", False)])
            self.assertEqual(rows[0]["stop"], 91.0)  # 4.5 ATR
            self.assertEqual(rows[0]["entry_max"], 101.0)  # +0.5 ATR
            # A re-publish with a different pick moves the flag but keeps the rows.
            rows = self._run(root, [{"as_of": "2026-10-29", "ticker": "BBB"}])
            self.assertEqual({r["ticker"]: r["picked"] for r in rows}, {"AAA": False, "BBB": True, "CCC": False})
            s = ledger.control_stats(rows)
            self.assertEqual((s["all"]["picks"], s["picked"]["picks"], s["unpicked"]["picks"]), (3, 1, 2))

    def test_one_open_row_per_ticker(self):
        with tempfile.TemporaryDirectory() as root:
            old = ledger.new_pick("2026-10-28", {"ticker": "BBB", "setup": "breakout", "conviction": 0, "stop_atr": 2.0},
                                  {"ref_close": 100, "atr": 2, "stop": 96, "entry_max": 101, "targets": [108]},
                                  {}, "Tech", "2026-10-29T06:05:00+00:00")
            daily.write_json(os.path.join(root, "control.json"), [old])
            rows = self._run(root, [])
            ids = {r["id"] for r in rows}
            self.assertNotIn("2026-10-29:BBB", ids)        # BBB is still open: no second row
            self.assertIn("2026-10-29:AAA", ids)
