// Today / archive view: answer first (regime + picks), detail on demand.
import { useState } from "react";
import {
  convictionDots, earningsChip, firstSentence, fmtNum, fmtPct, fmtPrice, pctFrom, regimeInfo, setupLabel,
  shortDate, tradingViewUrl,
} from "../lib/format.js";
import { Bullets, Button, Card, ExtLink, Fold, Num, Pill, Rows, SubHead, toneText } from "./ui.jsx";

const BORDER = { good: "border-l-good", warn: "border-l-warn", bad: "border-l-bad", muted: "border-l-muted" };

function Gauge({ label, value, tone, sub }) {
  return (
    <div className="flex flex-col rounded-xl bg-surface-2 px-2.5 py-2">
      <span className="text-[0.7rem] text-muted">{label}</span>
      <span className={`font-bold tabular ${toneText(tone)}`}>{value}</span>
      {sub && <span className="text-[0.66rem] text-muted">{sub}</span>}
    </div>
  );
}

function Summary({ day, pickCount }) {
  const regime = day.analysis.regime;
  const info = regimeInfo(regime.label);
  const spy = day.market.benchmarks.SPY || {};
  const br = day.breadth.at(-1) || {};
  const vix = day.market.macro?.vix?.value;
  const base = day.market.baseline_regime;
  const breadthTone = br.pct_above_sma50 >= 55 ? "good" : br.pct_above_sma50 < 40 ? "bad" : "warn";
  return (
    <Card className={`mb-3 border-l-[5px] ${BORDER[info.tone]}`}>
      <div className="flex flex-wrap items-center gap-2.5">
        <Pill tone={info.tone} strong>{info.label}</Pill>
        <span className="text-sm text-muted">Exposure {regime.exposure} · {pickCount} pick{pickCount === 1 ? "" : "s"}</span>
      </div>
      <p className="mb-3.5 mt-2.5 text-[1.02rem] leading-snug">{firstSentence(regime.summary)}</p>
      <div className="grid grid-cols-2 gap-2 min-[360px]:grid-cols-4">
        <Gauge label="SPY" value={spy.risk_on_gate ? "Uptrend" : "No gate"} tone={spy.risk_on_gate ? "good" : "bad"} />
        <Gauge label="Breadth" value={fmtPct(br.pct_above_sma50, 0, false)} tone={breadthTone} sub="> 50-day" />
        <Gauge label="VIX" value={fmtNum(vix, 1)} tone={vix < 18 ? "good" : vix > 26 ? "bad" : "warn"} />
        <Gauge label="Hi / Lo" value={`${br.new_52w_highs ?? "—"} / ${br.new_52w_lows ?? "—"}`}
          tone={(br.new_52w_highs ?? 0) >= (br.new_52w_lows ?? 0) ? "good" : "bad"} />
      </div>
      <details className="group mt-3">
        <summary className="py-1.5 text-sm font-semibold text-accent">
          Why this regime <span className="inline-block transition-transform group-open:rotate-180">▾</span>
        </summary>
        <div className="mt-2 space-y-2.5 text-sm">
          <p>{regime.summary}</p>
          <Bullets items={regime.evidence} />
          <p className="text-xs text-muted">
            Rule-based baseline: {regimeInfo(base.label).label} (score {base.score})
            {regime.disagrees_with_baseline && " — the agent disagrees; see the evidence above."}
          </p>
        </div>
      </details>
    </Card>
  );
}

function Level({ label, price, pct, accent }) {
  return (
    <div className={`flex min-w-0 flex-col rounded-xl bg-surface-2 px-2.5 py-2 ${accent ?? ""}`}>
      <span className="text-[0.7rem] text-muted">{label}</span>
      <span className="font-mono text-[0.98rem] font-bold tabular">{fmtPrice(price)}</span>
      <Num value={pct} className="text-xs" />
    </div>
  );
}

function PickDetails({ c }) {
  const lv = c.levels;
  const f = c.features;
  return (
    <div className="pt-2 text-sm">
      {c.catalysts.length > 0 && (<>
        <SubHead>Catalysts</SubHead>
        <ul className="m-0 space-y-1.5 pl-0">
          {c.catalysts.map((k, i) => (
            <li key={i} className="list-none">
              <span className="text-muted">{shortDate(k.date)} · </span>
              {k.source_url ? <ExtLink href={k.source_url} className="text-accent">{k.text}</ExtLink> : k.text}
            </li>
          ))}
        </ul>
      </>)}
      <SubHead>Risks</SubHead>
      <Bullets items={c.risks} />
      <SubHead>Invalidation</SubHead>
      <p>{c.invalidation}</p>
      {c.earnings_plan && (<><SubHead>Earnings plan</SubHead><p>{c.earnings_plan}</p></>)}
      {c.chart_checks.length > 0 && (<><SubHead>Check on the chart</SubHead><Bullets items={c.chart_checks} /></>)}
      <SubHead>Levels</SubHead>
      <Rows items={[
        ["Last close", fmtPrice(lv.ref_close)],
        [`Stop (${c.stop_atr} ATR)`, `${fmtPrice(lv.stop)} (${fmtPct(lv.stop_pct)})`],
        ["Targets", lv.targets.map((t, i) => `${fmtPrice(t)} (${c.targets_r[i]}R)`).join(" · ")],
        ["ATR", `${fmtPrice(lv.atr)} (${fmtPct(f.atr_pct, 1, false)})`],
      ]} />
      <SubHead>Setup data</SubHead>
      <Rows items={[
        ["Extension vs EMA21", `${fmtNum(f.ext_ema21_atr, 1)} ATR`],
        ["Below 52-week high", `${fmtNum(f.dist_52wh_atr, 1)} ATR (${fmtPct(f.pct_off_52wh)})`],
        ["Return 21d / 63d", `${fmtPct(f.ret_21d_pct)} / ${fmtPct(f.ret_63d_pct)}`],
        ["Volume vs 20-day avg", `×${fmtNum(f.vol_ratio, 2)}`],
        ["Avg dollar volume", `$${fmtNum(f.adv20_usd_m, 0)}M/day`],
        ["Tags", (f.tags || []).join(", ") || "—"],
      ]} />
      {c.news?.length > 0 && (<>
        <SubHead>Recent news</SubHead>
        <ul className="m-0 space-y-1.5 pl-0">
          {c.news.map((n, i) => (
            <li key={i} className="list-none text-[0.85rem]">
              <span className="text-muted">{shortDate(n.date)} · {n.source} · </span>
              <ExtLink href={n.url} className="text-accent">{n.headline}</ExtLink>
            </li>
          ))}
        </ul>
      </>)}
    </div>
  );
}

function PickCard({ c }) {
  const [open, setOpen] = useState(false);
  const lv = c.levels;
  const f = c.features;
  const e = earningsChip(c.earnings, c.horizon_sessions);
  return (
    <Card className="mb-3 lg:mb-0">
      <header className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col">
          <span className="text-2xl font-extrabold leading-tight tracking-wide">{c.ticker}</span>
          <span className="truncate text-sm text-muted">{c.name}</span>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <span className="whitespace-nowrap tracking-[2px] text-accent" aria-label={`Conviction ${c.conviction} of 5`}>
            {convictionDots(c.conviction)}
          </span>
          <Pill tone="accent" strong>{setupLabel(c.setup)}</Pill>
        </div>
      </header>
      <div className="my-3 grid grid-cols-3 gap-2">
        <Level label="Buy up to" price={lv.entry_max} pct={pctFrom(lv.ref_close, lv.entry_max)} />
        <Level label="Stop" price={lv.stop} pct={pctFrom(lv.ref_close, lv.stop)} accent="shadow-[inset_0_-3px_0_var(--color-bad-bg)]" />
        <Level label={`Target ${c.targets_r[0]}R`} price={lv.targets[0]} pct={pctFrom(lv.ref_close, lv.targets[0])}
          accent="shadow-[inset_0_-3px_0_var(--color-good-bg)]" />
      </div>
      <div className="mb-2.5 flex flex-wrap gap-1.5">
        <Pill tone={e.inside ? "warn" : "muted"} strong={e.inside}>{e.text}</Pill>
        <Pill>Hold ≤ {c.horizon_sessions}d</Pill>
        <Pill>RS {fmtNum(f.rs_rank, 0)}{f.rs_rising ? "↑" : ""}</Pill>
        <Pill>{c.sector}</Pill>
      </div>
      <p className={`text-[0.93rem] ${open ? "" : "line-clamp-3"}`}>{c.thesis}</p>
      <div className="mt-3 flex gap-2">
        <Button href={tradingViewUrl(c.ticker)} primary>Open chart ↗</Button>
        <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
          className="inline-flex min-h-11 flex-1 items-center justify-center rounded-xl border border-line bg-surface text-sm font-semibold text-ink">
          {open ? "Hide details" : "Details"}
        </button>
      </div>
      {open && <PickDetails c={c} />}
    </Card>
  );
}

function TickerList({ items, line }) {
  return (
    <ul className="m-0 divide-y divide-line pl-0">
      {items.map((w) => (
        <li key={w.ticker} className="list-none py-2.5 first:pt-0">
          <div className="flex items-baseline gap-2">
            <ExtLink href={tradingViewUrl(w.ticker)} className="font-extrabold text-accent no-underline">{w.ticker}</ExtLink>
            <span className="truncate text-xs text-muted">{w.name}</span>
            {w.close != null && <span className="ml-auto font-mono text-xs tabular">{fmtPrice(w.close)}</span>}
          </div>
          <p className="text-sm">{line(w)}</p>
        </li>
      ))}
    </ul>
  );
}

function MiniList({ items }) {
  return (
    <ul className="m-0 divide-y divide-line pl-0 text-sm">
      {items.map(([key, mid, end]) => (
        <li key={key} className="flex list-none items-baseline gap-2.5 py-2 first:pt-0">
          <span className="min-w-12 font-bold">{key}</span>
          <span className="min-w-0 flex-1">{mid}</span>
          <span className="font-bold">{end}</span>
        </li>
      ))}
    </ul>
  );
}

function Market({ day }) {
  const b = day.market.benchmarks;
  const latest = day.breadth.at(-1) || {};
  const first = day.breadth[0] || {};
  const macro = day.market.macro || {};
  const sectors = [...day.market.sectors].sort((x, y) => (y.rs_63d_vs_spy ?? -99) - (x.rs_63d_vs_spy ?? -99));
  return (
    <Fold title="Market">
      <SubHead>Benchmarks</SubHead>
      <MiniList items={["SPY", "QQQ", "IWM", "RSP", "SMH"].filter((k) => b[k]).map((k) => [k,
        <span key={k}>21d <Num value={b[k].ret_21d_pct} /> · off high <Num value={b[k].drawdown_from_52wh_pct} /></span>,
        <span key="g" className={b[k].risk_on_gate ? "text-good" : "text-bad"}>{b[k].risk_on_gate ? "✓" : "✗"}</span>])} />
      <SubHead>Breadth (S&amp;P 500 + 400)</SubHead>
      <Rows items={[
        ["Above SMA50", `${fmtPct(latest.pct_above_sma50, 1, false)} (20 sessions ago ${fmtPct(first.pct_above_sma50, 1, false)})`],
        ["Above SMA200", `${fmtPct(latest.pct_above_sma200, 1, false)} (${fmtPct(first.pct_above_sma200, 1, false)})`],
        ["New highs / lows", `${latest.new_52w_highs ?? "—"} / ${latest.new_52w_lows ?? "—"}`],
        ["Advancers / decliners", `${latest.advancers ?? "—"} / ${latest.decliners ?? "—"}`],
      ]} />
      <SubHead>Macro</SubHead>
      <Rows items={[["VIX", "vix"], ["HY credit spread", "hy_oas"], ["10y yield", "ust10y"], ["10y − 2y", "curve_10y2y"]]
        .filter(([, k]) => macro[k])
        .map(([label, k]) => [label, <span key={k}>{fmtNum(macro[k].value, 2)} <span className="text-muted">Δ20 </span>
          <Num value={macro[k].chg_20obs} fmt={(x) => fmtNum(x, 2)} /></span>])} />
      <SubHead>Sectors by 63-day strength vs SPY</SubHead>
      <MiniList items={sectors.map((s) => [s.etf,
        <span key={s.etf}>{s.sector}<span className="text-muted"> · {fmtPct(s.pct_trend_stack, 0, false)} in trend</span></span>,
        <Num key="rs" value={s.rs_63d_vs_spy} />])} />
    </Fold>
  );
}

export default function Today({ day }) {
  const a = day.analysis;
  const picks = [...a.candidates].sort((x, y) => y.conviction - x.conviction);
  const notes = a.market_notes.length + a.data_issues.length;
  return (
    <>
      <Summary day={day} pickCount={picks.length} />
      <h2 className="mx-0.5 mb-2.5 mt-5 flex items-baseline gap-2 text-lg font-bold">
        Picks <span className="text-xs font-normal text-muted">by conviction</span>
      </h2>
      {picks.length ? (
        <div className="lg:grid lg:grid-cols-2 lg:items-start lg:gap-3">
          {picks.map((c) => <PickCard key={c.ticker} c={c} />)}
        </div>
      ) : (
        <Card className="mb-3 text-muted">No picks today. That's a valid answer: nothing met the bar.</Card>
      )}
      <div className="mt-3 lg:grid lg:grid-cols-2 lg:items-start lg:gap-3">
        {a.watchlist.length > 0 && (
          <Fold title="Watchlist" count={a.watchlist.length}>
            <TickerList items={a.watchlist} line={(w) => `${w.trigger}${w.note ? ` — ${w.note}` : ""}`} />
          </Fold>
        )}
        {a.avoid.length > 0 && (
          <Fold title="Avoid" count={a.avoid.length}><TickerList items={a.avoid} line={(w) => w.reason} /></Fold>
        )}
        <Market day={day} />
        {notes > 0 && (
          <Fold title="Notes & data issues" count={notes}>
            {a.market_notes.length > 0 && (<><SubHead>Market notes</SubHead><Bullets items={a.market_notes} className="text-sm" /></>)}
            {a.data_issues.length > 0 && (<><SubHead>Data issues</SubHead><Bullets items={a.data_issues} className="text-sm" /></>)}
          </Fold>
        )}
      </div>
      <p className="mx-0.5 my-2 text-xs text-muted">Generated {day.generated_utc.replace("T", " ").slice(0, 16)} UTC</p>
    </>
  );
}
