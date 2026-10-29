// =============================================================================
// Dashboard app: unlock -> decrypt -> render. All text goes through
// textContent (never innerHTML); links only accept https (safeUrl).
// =============================================================================
import { decryptJson, deriveKey, exportKey, importKey, verifyKey } from "./crypto.js";
import {
  convictionDots, earningsNote, fmtNum, fmtPct, fmtPrice, fmtR, regimeInfo, routeFromHash, safeUrl,
  setupLabel, signClass, statusLabel, tradingViewUrl,
} from "./format.js";

const KEY_STORE = "stonks.dashboardKey";
const state = { key: null, keyinfo: null, index: null, cache: new Map() };
const $ = (sel) => document.querySelector(sel);

// =============================================================================
// DOM helper
// =============================================================================
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return el;
}

function link(text, url) {
  const href = safeUrl(url);
  return href ? h("a", { href, target: "_blank", rel: "noopener noreferrer" }, text) : h("span", {}, text);
}

function table(headers, rows, cls = "") {
  return h("div", { class: "table-wrap" },
    h("table", { class: cls },
      h("thead", {}, h("tr", {}, headers.map((x) => h("th", {}, x)))),
      h("tbody", {}, rows.map((r) => h("tr", {}, r.map((c) => (c instanceof Node ? h("td", {}, c) : h("td", {}, c ?? "—"))))))));
}

function num(x, fmt = fmtPct) {
  return h("span", { class: `num ${signClass(x)}` }, fmt(x));
}

// =============================================================================
// Key handling
// =============================================================================
function storage(kind) {
  try {
    return kind === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

async function restoreKey() {
  for (const kind of ["session", "local"]) {
    const raw = storage(kind)?.getItem(KEY_STORE);
    if (!raw) continue;
    try {
      const key = await importKey(raw);
      if (await verifyKey(key, state.keyinfo)) return key;
    } catch { /* stale or corrupt entry */ }
    storage(kind)?.removeItem(KEY_STORE);
  }
  return null;
}

async function unlock(passphrase, remember) {
  const { salt, iterations } = state.keyinfo.kdf;
  const extractable = await deriveKey(passphrase, salt, iterations, true);
  if (!(await verifyKey(extractable, state.keyinfo))) return false;
  const raw = await exportKey(extractable);
  try {
    storage("session")?.setItem(KEY_STORE, raw);
    if (remember) storage("local")?.setItem(KEY_STORE, raw);
  } catch { /* storage unavailable: unlock just lasts this page view */ }
  state.key = await importKey(raw);
  return true;
}

function lock() {
  for (const kind of ["session", "local"]) storage(kind)?.removeItem(KEY_STORE);
  state.key = null;
  state.cache.clear();
  showLogin();
}

async function load(rel) {
  if (state.cache.has(rel)) return state.cache.get(rel);
  const res = await fetch(`data/${rel}`, { cache: "no-cache" });
  if (!res.ok) throw new Error(`${rel}: HTTP ${res.status}`);
  const value = await decryptJson(state.key, await res.json(), rel);
  state.cache.set(rel, value);
  return value;
}

// =============================================================================
// Views
// =============================================================================
function showLogin(message = "") {
  $("#nav").hidden = true;
  const input = h("input", { type: "password", id: "pass", autocomplete: "current-password", required: true, "aria-label": "Passphrase" });
  const remember = h("input", { type: "checkbox", id: "remember" });
  const status = h("p", { class: "login-status", role: "status" }, message);
  const form = h("form", {
    class: "login card",
    onsubmit: async (ev) => {
      ev.preventDefault();
      status.textContent = "Deriving key…";
      form.querySelector("button").disabled = true;
      const ok = await unlock(input.value, remember.checked);
      input.value = "";
      if (ok) return route();
      form.querySelector("button").disabled = false;
      status.textContent = "Wrong passphrase.";
    },
  },
  h("h2", {}, "Unlock dashboard"),
  h("p", { class: "muted" }, "The analysis is encrypted. Decryption happens in this browser; the passphrase never leaves it."),
  input,
  h("label", { class: "check" }, remember, " Remember on this device"),
  h("button", { type: "submit" }, "Unlock"),
  status);
  $("#main").replaceChildren(form);
  input.focus();
}

function renderNav(active, date) {
  const nav = $("#nav");
  nav.hidden = false;
  const select = h("select", { "aria-label": "Archive date", onchange: (ev) => { location.hash = `#/day/${ev.target.value}`; } },
    [...state.index.days].reverse().map((d) => h("option", { value: d, selected: d === date }, d)));
  nav.replaceChildren(
    h("a", { href: `#/day/${state.index.latest}`, class: active === "today" ? "active" : "" }, "Latest"),
    h("a", { href: "#/record", class: active === "record" ? "active" : "" }, "Track record"),
    select,
    h("button", { class: "ghost", onclick: lock }, "Lock"));
}

function regimeCard(day) {
  const a = day.analysis.regime;
  const info = regimeInfo(a.label);
  const base = day.market.baseline_regime;
  return h("section", { class: `card regime tone-${info.tone}` },
    h("div", { class: "regime-head" },
      h("span", { class: `badge tone-${info.tone}` }, info.label),
      h("span", { class: "muted" }, `Exposure: ${a.exposure}`),
      h("span", { class: "muted" }, `Rule-based baseline: ${regimeInfo(base.label).label} (score ${base.score})`),
      a.disagrees_with_baseline ? h("span", { class: "badge tone-warn" }, "Agent disagrees with baseline") : null),
    h("p", {}, a.summary),
    h("ul", {}, a.evidence.map((e) => h("li", {}, e))));
}

function marketStrip(day) {
  const b = day.market.benchmarks;
  const latest = day.breadth.at(-1) || {};
  const first = day.breadth[0] || {};
  const macro = day.market.macro || {};
  const benchRows = ["SPY", "QQQ", "IWM", "RSP", "SMH"].filter((k) => b[k]).map((k) => [
    k, fmtPrice(b[k].close), num(b[k].ret_5d_pct), num(b[k].ret_21d_pct), num(b[k].drawdown_from_52wh_pct),
    b[k].risk_on_gate ? "✓ above rising EMA50" : "✗"]);
  const macroRows = [["VIX", "vix"], ["HY OAS", "hy_oas"], ["10y yield", "ust10y"], ["10y−2y", "curve_10y2y"]]
    .filter(([, k]) => macro[k]).map(([label, k]) => [label, fmtNum(macro[k].value, 2), num(macro[k].chg_20obs, (x) => fmtNum(x, 2)), macro[k].date]);
  return h("section", { class: "grid-2" },
    h("div", { class: "card" }, h("h3", {}, "Benchmarks"),
      table(["", "Close", "5d", "21d", "Off high", "Gate"], benchRows)),
    h("div", { class: "card" }, h("h3", {}, "Breadth (S&P 500 + 400)"),
      table(["", "Now", "20 sessions ago"], [
        ["% above SMA50", fmtPct(latest.pct_above_sma50, 1, false), fmtPct(first.pct_above_sma50, 1, false)],
        ["% above SMA200", fmtPct(latest.pct_above_sma200, 1, false), fmtPct(first.pct_above_sma200, 1, false)],
        ["New 52w highs / lows", `${latest.new_52w_highs ?? "—"} / ${latest.new_52w_lows ?? "—"}`, `${first.new_52w_highs ?? "—"} / ${first.new_52w_lows ?? "—"}`],
        ["Advancers / decliners", `${latest.advancers ?? "—"} / ${latest.decliners ?? "—"}`, ""],
      ]),
      h("h3", {}, "Macro (FRED)"),
      table(["", "Last", "Δ 20 obs", "Date"], macroRows)));
}

function candidateCard(c) {
  const lv = c.levels;
  const f = c.features;
  const e = earningsNote(c.earnings, c.horizon_sessions);
  return h("article", { class: "card candidate" },
    h("header", {},
      h("div", {},
        h("h3", {}, link(c.ticker, tradingViewUrl(c.ticker)), " ", h("span", { class: "muted name" }, c.name)),
        h("div", { class: "muted" }, `${c.sector} · ${setupLabel(c.setup)} · ${c.horizon_sessions} sessions`)),
      h("div", { class: "conviction", title: `Conviction ${c.conviction}/5` }, convictionDots(c.conviction))),
    h("div", { class: "levels" },
      h("div", {}, h("span", { class: "label" }, "Ref close"), fmtPrice(lv.ref_close)),
      h("div", {}, h("span", { class: "label" }, "Max entry"), fmtPrice(lv.entry_max)),
      h("div", {}, h("span", { class: "label" }, `Stop (${c.stop_atr} ATR)`), `${fmtPrice(lv.stop)} `, h("span", { class: "num down" }, fmtPct(lv.stop_pct))),
      h("div", {}, h("span", { class: "label" }, "Targets"), lv.targets.map((t, i) => `${fmtPrice(t)} (${c.targets_r[i]}R)`).join(" · "))),
    h("p", { class: `earnings tone-${e.tone}` }, `Earnings: ${e.text}`, e.inside ? " — inside the holding horizon" : ""),
    c.earnings_plan ? h("p", { class: "muted" }, c.earnings_plan) : null,
    h("p", {}, c.thesis),
    c.catalysts.length ? h("div", {}, h("h4", {}, "Catalysts"),
      h("ul", {}, c.catalysts.map((k) => h("li", {}, `${k.date} — `, k.source_url ? link(k.text, k.source_url) : k.text)))) : null,
    h("div", { class: "grid-2 tight" },
      h("div", {}, h("h4", {}, "Risks"), h("ul", {}, c.risks.map((r) => h("li", {}, r)))),
      h("div", {}, h("h4", {}, "Invalidation"), h("p", {}, c.invalidation),
        c.chart_checks.length ? [h("h4", {}, "Check on the chart"), h("ul", {}, c.chart_checks.map((r) => h("li", {}, r)))] : null)),
    h("div", { class: "chips" },
      h("span", { class: "chip" }, `RS rank ${fmtNum(f.rs_rank, 0)}${f.rs_rising ? " ↑" : ""}`),
      h("span", { class: "chip" }, `Ext ${fmtNum(f.ext_ema21_atr, 1)} ATR vs EMA21`),
      h("span", { class: "chip" }, `${fmtNum(f.dist_52wh_atr, 1)} ATR below 52w high`),
      h("span", { class: "chip" }, `ATR ${fmtPct(f.atr_pct, 1, false)}`),
      h("span", { class: "chip" }, `Vol ×${fmtNum(f.vol_ratio, 2)}`),
      h("span", { class: "chip" }, `$${fmtNum(f.adv20_usd_m, 0)}M/day`),
      (f.tags || []).map((t) => h("span", { class: "chip tag" }, t))),
    c.news?.length ? h("details", {}, h("summary", {}, `Recent news (${c.news.length})`),
      h("ul", {}, c.news.map((n) => h("li", {}, `${n.date} · ${n.source}: `, link(n.headline, n.url))))) : null);
}

async function renderDay(date) {
  const target = date || state.index.latest;
  if (!state.index.days.includes(target)) {
    $("#main").replaceChildren(h("p", { class: "card" }, `No analysis for ${target}.`));
    return;
  }
  renderNav(target === state.index.latest ? "today" : "archive", target);
  const day = await load(`days/${target}.json`);
  const a = day.analysis;
  const candidates = [...a.candidates].sort((x, y) => y.conviction - x.conviction);
  $("#asof").textContent = `Last closed session ${day.as_of} · generated ${day.generated_utc.replace("T", " ").slice(0, 16)} UTC`;
  $("#main").replaceChildren(
    regimeCard(day),
    marketStrip(day),
    h("section", {}, h("h2", {}, `Candidates (${candidates.length})`),
      candidates.length ? candidates.map(candidateCard) : h("p", { class: "card muted" }, "No candidates today.")),
    a.watchlist.length ? h("section", { class: "card" }, h("h2", {}, "Watchlist"),
      table(["Ticker", "Close", "Trigger", "Note"], a.watchlist.map((w) => [link(w.ticker, tradingViewUrl(w.ticker)), fmtPrice(w.close), w.trigger, w.note]))) : null,
    a.avoid.length ? h("section", { class: "card" }, h("h2", {}, "Avoid"),
      table(["Ticker", "Reason"], a.avoid.map((w) => [link(w.ticker, tradingViewUrl(w.ticker)), w.reason]))) : null,
    h("section", { class: "card" }, h("h2", {}, "Sectors"),
      table(["Sector", "ETF", "21d", "63d", "RS vs SPY (63d)", "Gate", "% members in trend"],
        [...day.market.sectors].sort((x, y) => (y.rs_63d_vs_spy ?? -99) - (x.rs_63d_vs_spy ?? -99)).map((s) => [
          s.sector, s.etf, num(s.ret_21d_pct), num(s.ret_63d_pct), num(s.rs_63d_vs_spy), s.risk_on_gate ? "✓" : "✗",
          fmtPct(s.pct_trend_stack, 0, false)]))),
    (a.market_notes.length || a.data_issues.length) ? h("section", { class: "card" },
      a.market_notes.length ? [h("h2", {}, "Market notes"), h("ul", {}, a.market_notes.map((n) => h("li", {}, n)))] : null,
      a.data_issues.length ? [h("h2", {}, "Data issues"), h("ul", {}, a.data_issues.map((n) => h("li", {}, n)))] : null) : null);
}

function statsRows(groups) {
  return Object.entries(groups).map(([k, s]) => [
    k, s.picks, s.filled, s.not_filled, s.stopped, s.n_20, fmtR(s.avg_r_5), fmtR(s.avg_r_10), fmtR(s.avg_r_20),
    fmtPct(s.win_rate_20, 0, false), fmtPct(s.spy_avg_pct_20), fmtR(s.avg_mfe_r)]);
}

async function renderRecord() {
  renderNav("record", null);
  const led = await load("ledger.json");
  const s = led.stats;
  const head = ["", "Picks", "Filled", "Not filled", "Stopped", "n@20", "Avg R@5", "Avg R@10", "Avg R@20", "Win@20", "SPY@20", "Avg MFE"];
  $("#asof").textContent = `Ledger updated through ${led.updated}`;
  $("#main").replaceChildren(
    h("section", { class: "card" },
      h("h2", {}, "Track record"),
      s.all.low_sample ? h("p", { class: "badge tone-warn" }, `Low sample: ${s.all.n_20} picks with a 20-session outcome (<30). Treat as noise.`) : null,
      h("p", { class: "muted" }, `Entry at the next session's open; ${s.cost_assumption}. R = (exit − entry) / (entry − stop). Outcomes are marked to market, not exited at targets.`),
      table(head, statsRows({ All: s.all })),
      h("h3", {}, "By conviction"), table(head, statsRows(s.by_conviction)),
      h("h3", {}, "By setup"), table(head, statsRows(s.by_setup))),
    h("section", { class: "card" }, h("h2", {}, "All picks"),
      table(["Date", "Ticker", "Setup", "Conv.", "Entry", "Stop", "Status", "R@5", "R@10", "R@20", "MFE", "Targets hit"],
        [...led.picks].reverse().map((p) => [
          p.as_of, link(p.ticker, tradingViewUrl(p.ticker)), setupLabel(p.setup), p.conviction,
          p.entry != null ? fmtPrice(p.entry) : "—", fmtPrice(p.stop), statusLabel(p.status),
          num(p.r?.["5"], fmtR), num(p.r?.["10"], fmtR), num(p.r?.["20"], fmtR), fmtR(p.mfe_r),
          (p.targets_hit || []).filter(Boolean).length]), "dense")));
}

async function route() {
  if (!state.key) return showLogin();
  try {
    state.index = await load("index.json");
    const r = routeFromHash(location.hash);
    if (r.view === "record") await renderRecord();
    else await renderDay(r.date);
  } catch (err) {
    console.error(err);
    $("#main").replaceChildren(h("p", { class: "card tone-bad" }, `Could not load data: ${err.message}`));
  }
}

async function init() {
  try {
    const res = await fetch("data/keyinfo.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(String(res.status));
    state.keyinfo = await res.json();
  } catch {
    $("#main").replaceChildren(h("p", { class: "card muted" }, "No analysis has been published yet."));
    return;
  }
  state.key = await restoreKey();
  window.addEventListener("hashchange", route);
  await route();
}

init();
