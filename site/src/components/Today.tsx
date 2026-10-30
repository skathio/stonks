// Today / archive view: the brief first (regime, size, picks), market context in a side rail.
import { useState, type ReactNode } from "react";
import {
  actionTone, axisPos, convictionDots, earningsChip, firstSentence, flagInfo, fmtNum, fmtPct, fmtPrice, fmtScale,
  ladderAxis, nextReport, pctFrom, regimeInfo, scaleTone, sessionsToMonths, setupLabel, shortDate, tradingViewUrl,
} from "../lib/format.ts";
import type { BookLimits, Candidate, Day, Momentum, Position, Tone } from "../lib/types.ts";
import { Bullets, Button, Card, ExtLink, Fold, Icon, Num, Pill, Rows, Stat, SubHead, toneText, useMedia } from "./ui.tsx";

const BAND: Record<Tone, string> = { good: "border-l-good", warn: "border-l-warn", bad: "border-l-bad", muted: "border-l-line" };

function SizeBand({ m }: { m: Momentum }) {
  const tone = scaleTone(m.size_scale);
  const ratio = m.target_vol_ann_pct ? m.spread_vol_ann_pct / m.target_vol_ann_pct : null;
  return (
    <div className={`mt-4 rounded-xl border-l-4 bg-surface-2 px-3.5 py-2.5 ${BAND[tone]}`}>
      <p className="font-semibold">
        Size positions at <span className={`tabular ${toneText(tone)}`}>{Math.round(100 * m.size_scale)}%</span> of normal
      </p>
      <p className="text-sm text-muted">
        {ratio != null && ratio > 1
          ? `Momentum stocks are swinging ${fmtNum(ratio, 1)}× harder than their long-run norm.`
          : "Momentum stocks are as calm as their long-run norm."}
        {" "}MTUM vs SPY, 21 days: <Num value={m.mtum_vs_spy_21d_pct} />.
      </p>
    </div>
  );
}

function Brief({ day, pickCount }: { day: Day; pickCount: number }) {
  const held = day.book?.length;
  const limits = day.limits;
  const regime = day.analysis.regime;
  const info = regimeInfo(regime.label);
  const spy = day.market.benchmarks["SPY"];
  const br = day.breadth.at(-1);
  const vix = day.market.macro?.vix?.value;
  const base = day.market.baseline_regime;
  const above50 = br?.pct_above_sma50;
  const breadthTone: Tone = above50 == null ? "muted" : above50 >= 55 ? "good" : above50 < 40 ? "bad" : "warn";
  const vixTone: Tone = vix == null ? "muted" : vix < 18 ? "good" : vix > 26 ? "bad" : "warn";
  const highs = br?.new_52w_highs;
  const lows = br?.new_52w_lows;
  return (
    <Card className="mb-5 lg:p-5">
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <Pill tone={info.tone} strong>{info.label}</Pill>
        <span className="text-sm text-muted">
          Exposure {regime.exposure}, {limits ? `${pickCount} new position${pickCount === 1 ? "" : "s"}, ${held ?? 0} of ${limits.max_open} open`
            : `${pickCount} pick${pickCount === 1 ? "" : "s"}`}
        </span>
      </div>
      <p className="mt-2.5 text-lg font-semibold leading-snug lg:text-xl">{firstSentence(regime.summary)}</p>
      {day.momentum && <SizeBand m={day.momentum} />}
      <div className="mt-4 grid grid-cols-4 divide-x divide-line border-y border-line py-2.5 [&>*]:px-2.5 [&>*:first-child]:pl-0">
        <Stat label="SPY" value={spy?.risk_on_gate ? "Uptrend" : "No gate"} tone={spy?.risk_on_gate ? "good" : "bad"} />
        <Stat label="Breadth" value={fmtPct(above50, 0, false)} tone={breadthTone} sub="> 50-day" />
        <Stat label="VIX" value={fmtNum(vix, 1)} tone={vixTone} />
        <Stat label="Hi / lo" value={`${highs ?? "—"}/${lows ?? "—"}`} tone={(highs ?? 0) >= (lows ?? 0) ? "good" : "bad"} />
      </div>
      <details className="group mt-2">
        <summary className="inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-accent">
          Why this regime <Icon name="chevron" className="h-4 w-4 transition-transform group-open:rotate-180" />
        </summary>
        <div className="mt-1 max-w-prose space-y-2.5 text-sm">
          <p>{regime.summary}</p>
          <Bullets items={regime.evidence} />
          <p className="text-xs text-muted">
            Rule-based baseline: {regimeInfo(base.label).label} (score {base.score})
            {regime.disagrees_with_baseline && ". The agent disagrees; the evidence above says why."}
          </p>
        </div>
      </details>
    </Card>
  );
}

/** Stop → close → buy-up-to → targets on an axis shared by every pick today, in % from the close,
    so a wide trade (fewer shares for the same risk) looks wide. */
function Ladder({ c, axis }: { c: Candidate; axis: [number, number] }) {
  const lv = c.levels;
  const stop = pctFrom(lv.ref_close, lv.stop) ?? 0;
  const entry = pctFrom(lv.ref_close, lv.entry_max) ?? 0;
  const t = lv.targets.map((x) => pctFrom(lv.ref_close, x) ?? 0);
  const seg = (from: number, to: number, color: string, extra = "") => (
    <span className={`absolute inset-y-0 ${extra}`}
      style={{ left: `${axisPos(from, axis)}%`, width: `${axisPos(to, axis) - axisPos(from, axis)}%`, background: color }} />
  );
  return (
    <div className="relative my-3 h-2.5 rounded-full bg-surface-2" role="img"
      aria-label={`Stop ${fmtPct(stop)}, buy up to ${fmtPct(entry)}, targets ${t.map((x) => fmtPct(x)).join(" and ")} from the close`}>
      {seg(stop, 0, "var(--color-risk)", "rounded-l-full")}
      {seg(0, entry, "var(--color-chase)")}
      {t[0] != null && seg(entry, t[0], "var(--color-reward)", t.length === 1 ? "rounded-r-full" : "")}
      {t.length > 1 && seg(t[0] ?? entry, t.at(-1) ?? entry, "color-mix(in srgb, var(--color-reward) 45%, transparent)", "rounded-r-full")}
      <span className="absolute -inset-y-1 w-0.5 rounded bg-ink" style={{ left: `calc(${axisPos(0, axis)}% - 1px)` }} />
    </div>
  );
}

function Level({ label, color, price, pct }: { label: string; color: string; price: number | undefined; pct: number | null }) {
  return (
    <div className="flex min-w-0 flex-col">
      <span className="flex items-center gap-1.5 text-xs text-muted">
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} aria-hidden="true" />{label}
      </span>
      <span className="font-bold tabular">{fmtPrice(price)}</span>
      <Num value={pct} className="text-xs" />
    </div>
  );
}

function PickDetails({ c }: { c: Candidate }) {
  const lv = c.levels;
  const f = c.features;
  return (
    <div className="mt-3 border-t border-line pt-1 text-sm lg:grid lg:grid-cols-2 lg:gap-x-8">
      <div>
        {c.catalysts.length > 0 && (<>
          <SubHead>Catalysts</SubHead>
          <ul className="m-0 space-y-1.5 pl-0">
            {c.catalysts.map((k, i) => (
              <li key={i} className="list-none">
                <span className="text-muted">{shortDate(k.date)}: </span>
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
      </div>
      <div>
        <SubHead>Levels</SubHead>
        <Rows items={[
          ["Last close", fmtPrice(lv.ref_close)],
          [`Stop (${c.stop_atr} ATR)`, `${fmtPrice(lv.stop)} (${fmtPct(lv.stop_pct)})`],
          [c.upside_case != null ? "+20% reference" : "Targets",
            lv.targets.map((t, i) => `${fmtPrice(t)} (${fmtNum(lv.targets_r?.[i] ?? c.targets_r?.[i], 1)}R)`).join(", ")],
          ...(lv.position_pct != null ? [["Position size", `${fmtNum(lv.position_pct, 1)}% of the account`] as const] : []),
          ["ATR", `${fmtPrice(lv.atr)} (${fmtPct(f.atr_pct, 1, false)})`],
        ]} />
        <SubHead>Setup data</SubHead>
        <Rows items={[
          ["Extension vs EMA21", `${fmtNum(f.ext_ema21_atr, 1)} ATR`],
          ["Below 52-week high", `${fmtNum(f.dist_52wh_atr, 1)} ATR (${fmtPct(f.pct_off_52wh)})`],
          ["Return 21d / 63d", `${fmtPct(f.ret_21d_pct)} / ${fmtPct(f.ret_63d_pct)}`],
          ["Volume vs 20-day avg", `×${fmtNum(f.vol_ratio, 2)}`],
          ["Avg dollar volume", `$${fmtNum(f.adv20_usd_m, 0)}M/day`],
          ["Tags", f.tags.join(", ") || "—"],
        ]} />
        {c.news && c.news.length > 0 && (<>
          <SubHead>Recent news</SubHead>
          <ul className="m-0 space-y-1.5 pl-0">
            {c.news.map((n, i) => (
              <li key={i} className="list-none text-[0.85rem]">
                <span className="text-muted">{shortDate(n.date)}, {n.source}: </span>
                <ExtLink href={n.url} className="text-accent">{n.headline}</ExtLink>
              </li>
            ))}
          </ul>
        </>)}
      </div>
    </div>
  );
}

function PickCard({ c, axis }: { c: Candidate; axis: [number, number] }) {
  const [open, setOpen] = useState(false);
  const lv = c.levels;
  const f = c.features;
  const v2 = c.upside_case != null;
  const e = v2 ? nextReport(c.earnings, c.reports_in_hold) : earningsChip(c.earnings, c.horizon_sessions);
  const cols = 2 + lv.targets.length + (lv.position_pct != null ? 1 : 0);
  return (
    <Card className="lg:p-5">
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-baseline gap-2.5">
            <h3 className="text-2xl font-extrabold leading-none tracking-wide">{c.ticker}</h3>
            <span className="truncate text-sm text-muted">{c.name}</span>
          </div>
          <p className="mt-1 text-xs text-muted">{setupLabel(c.setup)} in {c.sector}</p>
        </div>
        <span className="whitespace-nowrap pt-1 text-sm tracking-[2px] text-accent" role="img" aria-label={`Conviction ${c.conviction} of 5`}>
          {convictionDots(c.conviction)}
        </span>
      </header>
      <Ladder c={c} axis={axis} />
      <div className={`grid gap-2 ${cols >= 4 ? "grid-cols-4" : "grid-cols-3"}`}>
        <Level label="Stop" color="var(--color-risk)" price={lv.stop} pct={pctFrom(lv.ref_close, lv.stop)} />
        <Level label="Buy up to" color="var(--color-chase)" price={lv.entry_max} pct={pctFrom(lv.ref_close, lv.entry_max)} />
        {lv.targets.map((t, i) => (
          <Level key={i} label={v2 ? "+20%" : `Target ${c.targets_r?.[i] ?? ""}R`} color="var(--color-reward)" price={t}
            pct={pctFrom(lv.ref_close, t)} />
        ))}
        {lv.position_pct != null && (
          <div className="flex min-w-0 flex-col">
            <span className="text-xs text-muted">Size</span>
            <span className="font-bold tabular">{fmtNum(lv.position_pct, 1)}%</span>
            <span className="text-xs text-muted">of account</span>
          </div>
        )}
      </div>
      <p className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        {e.inside ? <Pill tone="warn" strong>{e.text}</Pill> : <span>{e.text}</span>}
        <span>{v2 ? `Plan ${sessionsToMonths(c.horizon_sessions)}` : `Hold up to ${c.horizon_sessions} sessions`}</span>
        <span>RS rank {fmtNum(f.rs_rank, 0)}{f.rs_rising ? ", rising" : ""}</span>
      </p>
      <p className={`mt-2.5 max-w-prose text-[0.95rem] ${open ? "" : "line-clamp-2"}`}>{c.thesis}</p>
      {v2 && open && <p className="mt-2 max-w-prose text-sm"><span className="font-semibold">What 20%+ needs: </span>{c.upside_case}</p>}
      <div className="mt-3 flex gap-2">
        <Button href={tradingViewUrl(c.ticker)} className="flex-1 lg:flex-none">Chart <Icon name="external" className="h-4 w-4" /></Button>
        <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
          className="inline-flex min-h-11 flex-1 items-center justify-center gap-1 rounded-xl px-4 text-sm font-semibold text-accent hover:bg-surface-2 lg:flex-none">
          {open ? "Hide details" : "Details"}
          <Icon name="chevron" className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
      </div>
      {open && <PickDetails c={c} />}
    </Card>
  );
}

function PositionRow({ p }: { p: Position }) {
  const m = p.mark;
  const exRsp = m && m.rsp_pct != null ? m.pct - m.rsp_pct : null;
  const report = p.next_earnings ? nextReport(p.next_earnings, null) : null;
  return (
    <li className="list-none py-3 first:pt-0 last:pb-0">
      <div className="flex items-baseline gap-2.5">
        <ExtLink href={tradingViewUrl(p.ticker)} className="text-lg font-extrabold text-ink no-underline hover:text-accent">{p.ticker}</ExtLink>
        <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap text-xs text-muted">
          {p.sector}, since {shortDate(p.entry_date ?? p.as_of)}{m ? `, ${m.sessions} sessions` : ", awaiting entry"}
        </span>
        <span className="ml-auto text-right">
          <Num value={m?.pct} className="font-bold" />
          {exRsp != null && <span className="block text-xs text-muted">vs RSP <Num value={exRsp} /></span>}
        </span>
      </div>
      <p className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
        <span>Stop {fmtPrice(p.stop)} ({fmtPct(p.stop_dist_pct)})</span>
        {p.position_pct != null && <span>Size {fmtNum(p.position_pct, 1)}%</span>}
        {report && <span>{report.text}</span>}
      </p>
      {(p.flags.length > 0 || p.review) && (
        <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
          {p.review && <Pill tone={actionTone(p.review.action) === "muted" ? "accent" : actionTone(p.review.action)} strong>
            {p.review.action[0]?.toUpperCase()}{p.review.action.slice(1)}</Pill>}
          {p.flags.map((f) => { const info = flagInfo(f); return <Pill key={f} tone={info.tone}>{info.text}</Pill>; })}
        </div>
      )}
      {p.review && <p className="mt-1.5 max-w-prose text-sm">{p.review.note}</p>}
    </li>
  );
}

function Book({ book, limits }: { book: Position[]; limits: BookLimits }) {
  const sorted = [...book].sort((a, b) => (b.mark?.pct ?? -999) - (a.mark?.pct ?? -999));
  return (<>
    <h2 className="mx-0.5 mb-2.5 flex flex-wrap items-baseline gap-x-2 text-lg font-bold">
      Open positions <span className="text-xs font-normal text-muted">{book.length} of {limits.max_open}, at most {limits.max_per_sector} per sector</span>
    </h2>
    <Card className="mb-5">
      {sorted.length ? <ul className="m-0 divide-y divide-line pl-0">{sorted.map((p) => <PositionRow key={p.ticker} p={p} />)}</ul>
        : <p className="text-sm text-muted">No open positions yet. New positions appear here from the first open after they're published.</p>}
    </Card>
  </>);
}

interface TickerItem {
  ticker: string;
  name: string;
  close?: number | null;
}

function TickerList<T extends TickerItem>({ items, line }: { items: T[]; line: (item: T) => string }) {
  return (
    <ul className="m-0 divide-y divide-line pl-0">
      {items.map((w) => (
        <li key={w.ticker} className="list-none py-2.5 first:pt-0">
          <div className="flex items-baseline gap-2">
            <ExtLink href={tradingViewUrl(w.ticker)} className="font-extrabold text-accent no-underline hover:underline">{w.ticker}</ExtLink>
            <span className="min-w-0 truncate text-xs text-muted">{w.name}</span>
            {w.close != null && <span className="ml-auto text-xs tabular">{fmtPrice(w.close)}</span>}
          </div>
          <p className="text-sm">{line(w)}</p>
        </li>
      ))}
    </ul>
  );
}

function Panel({ title, desktop, children }: { title: string; desktop: boolean; children: ReactNode }) {
  // A plain card in the desktop rail; a fold on a phone, where it would push the lists far down.
  if (!desktop) return <Fold title={title}>{children}</Fold>;
  return (
    <Card className="mb-3">
      <h2 className="mb-3 font-bold">{title}</h2>
      {children}
    </Card>
  );
}

function MomentumPanel({ m }: { m: Momentum }) {
  return (<>
    <Rows items={[
      ["MTUM vs SPY, 21 / 63 days", <span key="s"><Num value={m.mtum_vs_spy_21d_pct} /> / <Num value={m.mtum_vs_spy_63d_pct} /></span>],
      ["vs equal weight (RSP)", <span key="r"><Num value={m.mtum_vs_rsp_21d_pct} /> / <Num value={m.mtum_vs_rsp_63d_pct} /></span>],
      ["Spread volatility", `${fmtNum(m.spread_vol_ann_pct, 1)}% (norm ${fmtNum(m.target_vol_ann_pct, 1)}%)`],
      ["Size scale", <span key="k" className={`font-bold ${toneText(scaleTone(m.size_scale))}`}>{fmtScale(m.size_scale)}</span>],
    ]} />
    <p className="mt-3 text-xs text-muted">
      Momentum crashes tend to come when this spread is volatile, so the size scale is the norm ÷ current volatility,
      capped at full size. Full size means momentum is as calm as its long-run median.
    </p>
  </>);
}

const MACRO = [["VIX", "vix"], ["HY credit spread", "hy_oas"], ["10y yield", "ust10y"], ["10y − 2y", "curve_10y2y"]] as const;

function SectorBars({ day }: { day: Day }) {
  const sectors = [...day.market.sectors].sort((x, y) => (y.rs_63d_vs_spy ?? -99) - (x.rs_63d_vs_spy ?? -99));
  const max = Math.max(1, ...sectors.map((s) => Math.abs(s.rs_63d_vs_spy ?? 0)));
  return (
    <ul className="m-0 space-y-1.5 pl-0 text-sm">
      {sectors.map((s) => {
        const v = s.rs_63d_vs_spy ?? 0;
        const w = (50 * Math.abs(v)) / max;
        return (
          <li key={s.etf} className="grid list-none grid-cols-[2.75rem_minmax(0,1fr)_3.5rem] items-center gap-2">
            <span className="font-bold" title={s.sector}>{s.etf}</span>
            <span className="relative h-2 rounded-full bg-surface-2" aria-hidden="true">
              <span className={`absolute inset-y-0 rounded-full ${v >= 0 ? "bg-good" : "bg-bad"}`}
                style={v >= 0 ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }} />
            </span>
            <Num value={s.rs_63d_vs_spy} className="text-right text-xs" />
          </li>
        );
      })}
    </ul>
  );
}

function MarketPanel({ day }: { day: Day }) {
  const b = day.market.benchmarks;
  const latest = day.breadth.at(-1);
  const first = day.breadth[0];
  const macro = day.market.macro ?? {};
  return (<>
    <SubHead>Benchmarks, 21 days and off the high</SubHead>
    <Rows items={["SPY", "QQQ", "IWM", "RSP", "SMH"].flatMap((k) => {
      const bm = b[k];
      return bm ? [[k, <span key={k}><Num value={bm.ret_21d_pct} /> <span className="text-muted">/</span> <Num value={bm.drawdown_from_52wh_pct} />
        <span className={`ml-2 ${bm.risk_on_gate ? "text-good" : "text-bad"}`} title={bm.risk_on_gate ? "Uptrend" : "No uptrend"}>
          {bm.risk_on_gate ? "↑" : "↓"}</span></span>] as const] : [];
    })} />
    <SubHead>Breadth (S&amp;P 500 + 400), now vs 20 sessions ago</SubHead>
    <Rows items={[
      ["Above SMA50", `${fmtPct(latest?.pct_above_sma50, 1, false)} vs ${fmtPct(first?.pct_above_sma50, 1, false)}`],
      ["Above SMA200", `${fmtPct(latest?.pct_above_sma200, 1, false)} vs ${fmtPct(first?.pct_above_sma200, 1, false)}`],
      ["New highs / lows", `${latest?.new_52w_highs ?? "—"} / ${latest?.new_52w_lows ?? "—"}`],
      ["Advancers / decliners", `${latest?.advancers ?? "—"} / ${latest?.decliners ?? "—"}`],
    ]} />
    <SubHead>Macro, with 20-observation change</SubHead>
    <Rows items={MACRO.flatMap(([label, k]) => {
      const m = macro[k];
      return m ? [[label, <span key={k}>{fmtNum(m.value, 2)} <Num value={m.chg_20obs} fmt={(x) => fmtNum(x, 2)} className="text-xs" /></span>] as const] : [];
    })} />
    <SubHead>Sectors by 63-day strength vs SPY</SubHead>
    <SectorBars day={day} />
  </>);
}

export default function Today({ day }: { day: Day }) {
  const desktop = useMedia("(min-width: 1024px)");
  const a = day.analysis;
  const picks = [...a.candidates].sort((x, y) => y.conviction - x.conviction);
  const axis = ladderAxis(picks.flatMap((c) => [c.levels.stop, ...c.levels.targets].map((x) => pctFrom(c.levels.ref_close, x) ?? 0)));
  const notes = a.market_notes.length + a.data_issues.length;
  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start lg:gap-6">
      <div>
        <Brief day={day} pickCount={picks.length} />
        {day.book && day.limits && <Book book={day.book} limits={day.limits} />}
        <h2 className="mx-0.5 mb-2.5 flex flex-wrap items-baseline gap-x-2 text-lg font-bold">
          {day.limits ? "New positions" : "Picks"}
          <span className="text-xs font-normal text-muted">by conviction, levels from the {shortDate(day.as_of)} close</span>
        </h2>
        {picks.length ? (
          <div className="space-y-3">{picks.map((c) => <PickCard key={c.ticker} c={c} axis={axis} />)}</div>
        ) : (
          <Card className="text-muted">
            {day.limits ? "No new position today. That's the default: nothing beat what the book already holds."
              : "No picks today. That's a valid answer: nothing met the bar."}
          </Card>
        )}
      </div>
      <aside className="mt-5 lg:mt-0" aria-label="Market context">
        {day.momentum && <Panel title="Momentum stocks" desktop={desktop}><MomentumPanel m={day.momentum} /></Panel>}
        <Panel title="Market" desktop={desktop}><MarketPanel day={day} /></Panel>
        {a.watchlist.length > 0 && (
          <Fold title="Watchlist" count={a.watchlist.length}>
            <TickerList items={a.watchlist} line={(w) => `${w.trigger}${w.note ? `. ${w.note}` : ""}`} />
          </Fold>
        )}
        {a.avoid.length > 0 && (
          <Fold title="Avoid" count={a.avoid.length}><TickerList items={a.avoid} line={(w) => w.reason} /></Fold>
        )}
        {notes > 0 && (
          <Fold title="Notes and data issues" count={notes}>
            {a.market_notes.length > 0 && (<><SubHead>Market notes</SubHead><Bullets items={a.market_notes} className="text-sm" /></>)}
            {a.data_issues.length > 0 && (<><SubHead>Data issues</SubHead><Bullets items={a.data_issues} className="text-sm" /></>)}
          </Fold>
        )}
        <p className="mx-0.5 my-2 text-xs text-muted">Generated {day.generated_utc.replace("T", " ").slice(0, 16)} UTC</p>
      </aside>
    </div>
  );
}
