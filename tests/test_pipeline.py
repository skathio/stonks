"""Pipeline unit tests (stdlib unittest): python3 -m unittest discover -s tests -p 'test_*.py'"""
import datetime as dt
import os
import sys
import unittest

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


FEATS = {"AAA": {"eligible": True, "close": 100.0, "atr": 2.0}, "BBB": {"eligible": False, "close": 4.0, "atr": 0.2}}


def good_analysis(**overrides):
    cand = {"ticker": "AAA", "setup": "breakout", "conviction": 4, "thesis": "Tight base under highs, RS leader.",
            "stop_atr": 2, "max_chase_atr": 0.5, "targets_r": [3, 2], "horizon_sessions": 20,
            "invalidation": "Close back inside the base.", "risks": ["Market reversal"],
            "catalysts": [{"date": "2026-10-28", "text": "Guidance raise", "source_url": "https://example.com/x"}]}
    cand.update(overrides)
    return {"as_of": "2026-10-29",
            "regime": {"label": "risk_on", "exposure": "full", "summary": "Broad strength.", "evidence": ["SPY > EMA50"]},
            "candidates": [cand]}


class AnalysisValidation(unittest.TestCase):
    def test_valid_and_levels(self):
        out = analysis.validate(good_analysis(), "2026-10-29", FEATS)
        c = out["candidates"][0]
        self.assertEqual(c["targets_r"], [2.0, 3.0])
        lv = analysis.levels(c, FEATS["AAA"])
        self.assertEqual(lv["stop"], 96.0)
        self.assertEqual(lv["entry_max"], 101.0)
        self.assertEqual(lv["targets"], [108.0, 112.0])

    def test_rejections(self):
        cases = [
            (dict(ticker="ZZZ"), "not in today's feature table"),
            (dict(ticker="BBB"), "price/liquidity floor"),
            (dict(stop_atr=0.5), "outside"),
            (dict(setup="moonshot"), "setup must be"),
            (dict(targets_r=[0.5]), "R multiples"),
            (dict(catalysts=[{"date": "soon", "text": "x"}]), "undated"),
            (dict(catalysts=[{"date": "2026-10-01", "text": "x", "source_url": "http://x"}]), "https"),
        ]
        for override, msg in cases:
            with self.subTest(msg=msg):
                with self.assertRaisesRegex(analysis.AnalysisError, msg):
                    analysis.validate(good_analysis(**override), "2026-10-29", FEATS)

    def test_wrong_as_of_and_none_exposure(self):
        with self.assertRaisesRegex(analysis.AnalysisError, "as_of"):
            analysis.validate(good_analysis(), "2026-10-30", FEATS)
        raw = good_analysis()
        raw["regime"]["exposure"] = "none"
        with self.assertRaisesRegex(analysis.AnalysisError, "exposure is 'none'"):
            analysis.validate(raw, "2026-10-29", FEATS)


class LedgerFills(unittest.TestCase):
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
        p = ledger.evaluate(self._pick(), days, [None, (95, 96, 94, 95, 1)], [None, (1, 1, 1, 1, 1)])
        self.assertEqual(p["status"], "gap_below_stop")

    def test_stop_hit_exits_at_stop_minus_costs(self):
        days = self._days(3)
        bars = [None, (100, 101, 99, 100, 1), (99, 99.5, 95, 96, 1), (96, 97, 95, 96, 1)]
        p = ledger.evaluate(self._pick(), days, bars, bars)
        self.assertEqual(p["status"], "stopped")
        self.assertAlmostEqual(p["exit_r"], -1.0 - 0.002 * 100 / 4, places=2)

    def test_gap_through_stop_fills_at_open(self):
        days = self._days(2)
        bars = [None, (100, 101, 99, 100, 1), (90, 91, 89, 90, 1)]
        p = ledger.evaluate(self._pick(), days, bars, bars)
        self.assertAlmostEqual(p["exit_r"], (90 - 100) / 4 - 0.002 * 100 / 4, places=2)

    def test_horizons_targets_and_completion(self):
        days = self._days(20)
        bars = [None] + [(100 + i, 101 + i, 99.5 + i, 100.5 + i, 1) for i in range(20)]
        p = ledger.evaluate(self._pick(), days, bars, bars)
        self.assertEqual(p["status"], "complete")
        self.assertEqual(set(p["r"]), {"5", "10", "20"})
        self.assertTrue(all(p["targets_hit"]))
        self.assertEqual(p["spy_pct"]["20"], round(100 * (119.5 / 100 - 1), 2))
        s = ledger.stats([p])
        self.assertEqual(s["all"]["n_20"], 1)
        self.assertTrue(s["all"]["low_sample"])

    def test_pending_without_new_bars(self):
        days = self._days(0)
        p = ledger.evaluate(self._pick(), days, [None], [None])
        self.assertEqual(p["status"], "pending")


if __name__ == "__main__":
    unittest.main()


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


class LowVolumeBreakout(unittest.TestCase):
    def test_matches_chart_check_caution(self):
        self.assertTrue(daily.low_volume_breakout(["breakout", "post_squeeze"]))
        self.assertFalse(daily.low_volume_breakout(["breakout", "volume_surge"]))
        self.assertFalse(daily.low_volume_breakout(["breakout", "pullback_reclaim"]))
        self.assertFalse(daily.low_volume_breakout(["post_squeeze", "near_52w_high"]))


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
