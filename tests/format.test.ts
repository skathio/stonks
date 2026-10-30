import { strict as assert } from "node:assert";
import { test } from "node:test";

import {
  convictionDots, earningsNote, fmtNum, fmtPct, fmtPrice, fmtR, isNum, regimeInfo, routeFromHash, safeUrl,
  setupLabel, signClass, statusLabel, tradingViewUrl,
} from "../site/src/lib/format.ts";

test("number formatting handles missing values", () => {
  assert.equal(isNum(NaN), false);
  assert.equal(fmtNum(null), "—");
  assert.equal(fmtNum(1234.5), "1,234.50");
  assert.equal(fmtPct(2.345), "+2.3%");
  assert.equal(fmtPct(-1.2), "-1.2%");
  assert.equal(fmtPct(55, 0, false), "55%");
  assert.equal(fmtPct(undefined), "—");
  assert.equal(fmtR(1.5), "+1.50R");
  assert.equal(fmtR(-1), "-1.00R");
  assert.equal(fmtR(null), "—");
  assert.equal(fmtPrice(12), "$12.00");
  assert.equal(fmtPrice(null), "—");
});

test("signClass", () => {
  assert.equal(signClass(1), "up");
  assert.equal(signClass(-1), "down");
  assert.equal(signClass(0), "flat");
  assert.equal(signClass(null), "flat");
});

test("labels fall back to the raw value", () => {
  assert.deepEqual(regimeInfo("risk_on"), { label: "Risk-on", tone: "good" });
  assert.equal(regimeInfo("weird").tone, "muted");
  assert.equal(statusLabel("stopped"), "Stopped out");
  assert.equal(statusLabel("x"), "x");
  assert.equal(setupLabel("pullback_reclaim"), "Pullback reclaim");
  assert.equal(setupLabel("x"), "x");
});

test("safeUrl only allows https", () => {
  assert.equal(safeUrl("https://example.com/a?b=1"), "https://example.com/a?b=1");
  assert.equal(safeUrl("http://example.com"), null);
  assert.equal(safeUrl("javascript:alert(1)"), null);
  assert.equal(safeUrl("not a url"), null);
  assert.equal(safeUrl(42), null);
});

test("tradingViewUrl encodes the ticker and normalizes class shares", () => {
  assert.equal(tradingViewUrl("AAPL"), "https://www.tradingview.com/chart/?symbol=AAPL");
  assert.equal(tradingViewUrl("BRK-B"), "https://www.tradingview.com/chart/?symbol=BRK.B");
});

test("convictionDots clamps to 0..5", () => {
  assert.equal(convictionDots(3), "●●●○○");
  assert.equal(convictionDots(9), "●●●●●");
  assert.equal(convictionDots("x"), "○○○○○");
});

test("earningsNote flags reports inside the holding horizon", () => {
  assert.equal(earningsNote(null, 20).tone, "muted");
  const inside = earningsNote({ date: "2026-11-05", hour: "amc", sessions_away: 5, conflict: true }, 20);
  assert.equal(inside.inside, true);
  assert.equal(inside.tone, "warn");
  assert.match(inside.text, /sources disagree/);
  assert.equal(earningsNote({ date: "2026-12-05", sessions_away: 26 }, 20).inside, false);
});

test("routeFromHash", () => {
  assert.deepEqual(routeFromHash("#/record"), { view: "record" });
  assert.deepEqual(routeFromHash("#/day/2026-10-29"), { view: "day", date: "2026-10-29" });
  assert.deepEqual(routeFromHash(""), { view: "day", date: null });
  assert.deepEqual(routeFromHash("#/day/../../etc"), { view: "day", date: null });
});

test("pctFrom, firstSentence, shortDate, earningsChip", async () => {
  const { pctFrom, firstSentence, shortDate, earningsChip } = await import("../site/src/lib/format.ts");
  assert.equal(pctFrom(100, 110), 10);
  assert.equal(pctFrom(0, 5), null);
  assert.equal(pctFrom(null, 5), null);
  assert.equal(firstSentence("SPY is up. Breadth is mixed."), "SPY is up.");
  assert.equal(firstSentence("No period here"), "No period here");
  assert.equal(firstSentence("x".repeat(300), 20).length, 20);
  assert.equal(shortDate("2026-10-28"), "Wed Oct 28");
  assert.equal(shortDate("bad"), "bad");
  assert.equal(earningsChip(null, 20).tone, "muted");
  const soon = earningsChip({ date: "2026-11-05", sessions_away: 5, conflict: true }, 20);
  assert.equal(soon.inside, true);
  assert.match(soon.text, /Thu Nov 5 · 5d ⚠/);
  assert.equal(earningsChip({ date: "2026-12-20", sessions_away: 36 }, 20).inside, false);
});
