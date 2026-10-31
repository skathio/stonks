// Track record: headline stats vs RSP, then every position (expandable rows on a phone, a table on desktop).
import { useState } from "react";
import { convictionDots, fmtPct, fmtPrice, fmtR, setupLabel, shortDate, statusLabel, tradingViewUrl } from "../lib/format.ts";
import { HORIZONS, type Horizon, type Ledger, type LedgerStats, type Pick } from "../lib/types.ts";
import { Button, Card, ExtLink, Fold, Icon, Num, Rows, Stat, useMedia } from "./ui.tsx";

const STATUS_TONE: Partial<Record<Pick["status"], string>> = { open: "text-accent", stopped: "text-bad", complete: "text-good" };

/** Percent at a mark, or the live mark for an open position. */
function latest(p: Pick): { pct: number | null; exRsp: number | null; label: string } {
  for (const h of [...HORIZONS].reverse()) {
    const v = p.pct?.[h];
    if (v != null) {
      const rsp = p.rsp_pct?.[h];
      return { pct: v, exRsp: rsp != null ? v - rsp : null, label: `${h} sessions` };
    }
  }
  const m = p.mark;
  if (m) return { pct: m.pct, exRsp: m.rsp_pct != null ? m.pct - m.rsp_pct : null, label: `${m.sessions} sessions` };
  return { pct: null, exRsp: null, label: "" };
}

function PickRow({ p }: { p: Pick }) {
  const [open, setOpen] = useState(false);
  const l = latest(p);
  return (
    <li className="list-none border-t border-line first:border-t-0">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
        className="flex min-h-14 w-full items-center gap-3 bg-transparent py-2 text-left text-ink">
        <span className="min-w-14 font-extrabold">{p.ticker}</span>
        <span className="flex min-w-0 flex-1 flex-col text-xs">
          <span>{shortDate(p.as_of)}, {setupLabel(p.setup)}</span>
          <span className={STATUS_TONE[p.status] ?? "text-muted"}>{statusLabel(p.status)}{l.label ? `, ${l.label}` : ""}</span>
        </span>
        <span className="text-right">
          {l.pct != null ? <Num value={l.pct} className="font-bold" /> : <span className="text-muted">—</span>}
          {l.exRsp != null && <span className="block text-xs text-muted">vs RSP <Num value={l.exRsp} /></span>}
        </span>
        <Icon name="chevron" className={`h-4 w-4 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="pb-3">
          <Rows items={[
            ["Conviction", convictionDots(p.conviction)],
            ["Entry", p.entry != null ? `${fmtPrice(p.entry)} on ${shortDate(p.entry_date)}` : "—"],
            ["Stop / max entry", `${fmtPrice(p.stop)} / ${fmtPrice(p.entry_max)}`],
            ...(p.position_pct != null ? [["Size", `${p.position_pct}% of the account`] as const] : []),
            ["Return at 21 / 42 / 63 / 126", HORIZONS.map((h) => fmtPct(p.pct?.[h])).join(", ")],
            ["RSP over the same", HORIZONS.map((h) => fmtPct(p.rsp_pct?.[h])).join(", ")],
            ["Best / worst", `${fmtR(p.mfe_r)} / ${fmtR(p.mae_r != null ? -p.mae_r : null)}`],
            ["+20% traded", p.targets_hit?.[0] ? shortDate(p.targets_hit[0]) : "not yet"],
          ]} />
          <div className="mt-3 flex"><Button href={tradingViewUrl(p.ticker)} className="flex-1">Chart <Icon name="external" className="h-4 w-4" /></Button></div>
        </div>
      )}
    </li>
  );
}

const TH = "px-3 py-2 text-left text-xs font-semibold text-muted";
const TD = "px-3 py-2.5";

function Cell({ p, h }: { p: Pick; h: Horizon }) {
  const v = p.pct?.[h];
  const rsp = p.rsp_pct?.[h];
  if (v == null) return <td className={`${TD} text-right text-muted`}>—</td>;
  return (
    <td className={`${TD} whitespace-nowrap text-right`}>
      <Num value={v} className="font-semibold" />
      {rsp != null && <span className="block text-xs text-muted">vs RSP <Num value={v - rsp} /></span>}
    </td>
  );
}

function PickTable({ picks }: { picks: Pick[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm tabular">
        <thead className="border-b border-line">
          <tr>
            <th className={TH}>Date</th><th className={TH}>Ticker</th><th className={TH}>Setup</th>
            <th className={TH}>Conviction</th><th className={TH}>Status</th>
            <th className={`${TH} text-right`}>Entry</th><th className={`${TH} text-right`}>Stop</th>
            <th className={`${TH} text-right`}>Now</th>
            {HORIZONS.map((h) => <th key={h} className={`${TH} text-right`}>{h} sessions</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {picks.map((p) => (
            <tr key={p.id} className="hover:bg-surface-2/60">
              <td className={`${TD} whitespace-nowrap text-muted`}>
                {shortDate(p.as_of)}
              </td>
              <td className={TD}>
                <ExtLink href={tradingViewUrl(p.ticker)} className="font-extrabold text-ink no-underline hover:text-accent hover:underline">{p.ticker}</ExtLink>
              </td>
              <td className={`${TD} whitespace-nowrap`}>{setupLabel(p.setup)}</td>
              <td className={`${TD} whitespace-nowrap tracking-[2px] text-accent`} aria-label={`Conviction ${p.conviction} of 5`}>{convictionDots(p.conviction)}</td>
              <td className={`${TD} whitespace-nowrap ${STATUS_TONE[p.status] ?? "text-muted"}`} title={statusLabel(p.status)}>
                {statusLabel(p.status).replace(/ \(.*\)$/, "")}
              </td>
              <td className={`${TD} text-right`}>{p.entry != null ? fmtPrice(p.entry) : "—"}</td>
              <td className={`${TD} text-right`}>{fmtPrice(p.stop)}</td>
              <td className={`${TD} text-right`}>{p.status === "open" && p.mark ? <Num value={p.mark.pct} /> : "—"}</td>
              {HORIZONS.map((h) => <Cell key={h} p={p} h={h} />)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const H: Horizon = "63";

function GroupList({ groups, label = (k) => k }: { groups: Record<string, LedgerStats>; label?: (key: string) => string }) {
  return (
    <ul className="m-0 divide-y divide-line pl-0 text-sm">
      {Object.entries(groups).map(([k, s]) => {
        const detail = `${s.picks} picks, ${s[`n_${H}`] ?? 0} at 63 sessions, beat RSP ${fmtPct(s[`beat_rsp_${H}`], 0, false)}`;
        return (
          <li key={k} className="grid list-none grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 py-2 first:pt-0
            lg:grid-cols-[minmax(0,1fr)_4.5rem_5.5rem_6.5rem_5rem]">
            <span className="font-semibold">{label(k)}</span>
            <span className="hidden text-right lg:inline">{s.picks} picks</span>
            <span className="hidden text-right lg:inline">{s[`n_${H}`] ?? 0} at 63d</span>
            <span className="hidden text-right lg:inline">beat RSP {fmtPct(s[`beat_rsp_${H}`], 0, false)}</span>
            <Num value={s[`avg_ex_rsp_${H}`]} className="text-right font-bold" />
            <span className="col-span-2 text-xs text-muted lg:hidden">{detail}</span>
          </li>
        );
      })}
    </ul>
  );
}

export default function Record({ ledger }: { ledger: Ledger }) {
  const desktop = useMedia("(min-width: 1024px)");
  const s = ledger.stats.all;
  const n = s[`n_${H}`] ?? 0;
  const picks = [...ledger.picks].reverse();
  return (
    <>
      <Card className="mb-5 lg:p-5">
        <div className="grid grid-cols-2 gap-y-3 lg:grid-cols-4 lg:divide-x lg:divide-line lg:[&>*]:px-4 lg:[&>*:first-child]:pl-0">
          <Stat label="Positions" value={s.picks} sub={`${s.open ?? 0} open, ${s.stopped} stopped`} />
          <Stat label="Avg vs RSP, 63 sessions" value={<Num value={s[`avg_ex_rsp_${H}`]} />} sub={`${n} done, ${s[`weeks_${H}`] ?? 0} entry weeks`} />
          <Stat label="Beat RSP, 63 sessions" value={fmtPct(s[`beat_rsp_${H}`], 0, false)} sub={`vs SPY ${fmtPct(s[`avg_ex_spy_${H}`])}`} />
          <Stat label="Open positions now" value={<Num value={s.avg_mark_pct} />} sub={`vs RSP ${fmtPct(s.avg_mark_ex_rsp)}`} />
        </div>
        {n === 0 ? (
          <p className="mt-4 rounded-xl bg-surface-2 px-3.5 py-2.5 text-sm text-muted">
            No position has reached 63 sessions yet. Marks appear at 21, 42, 63 and 126 sessions after each entry.
          </p>
        ) : s.low_sample && (
          <p className="mt-4 rounded-xl bg-warn-bg px-3.5 py-2.5 text-sm text-warn">
            Only {n} position{n === 1 ? "" : "s"} with a 63-session result, from {s[`weeks_${H}`] ?? 0} entry weeks. Under 30, treat
            these numbers as noise.
          </p>
        )}
        <p className="mt-3 text-xs text-muted">
          Entry at the first open after publishing; a wide stop is the only exit before 126 sessions. {ledger.stats.cost_assumption}.
          Every result is shown next to RSP (equal weight) and SPY held over the same window.
        </p>
      </Card>
      <h2 className="mx-0.5 mb-2.5 flex flex-wrap items-baseline gap-x-2 text-lg font-bold">
        All positions <span className="text-xs font-normal text-muted">{picks.length}</span>
      </h2>
      <Card className={`mb-5 ${desktop ? "p-2" : "py-1"}`}>
        {desktop ? <PickTable picks={picks} /> : <ul className="m-0 pl-0">{picks.map((p) => <PickRow key={p.id} p={p} />)}</ul>}
      </Card>
      <div className="xl:grid xl:grid-cols-2 xl:items-start xl:gap-x-3">
        {ledger.control && (
          <Fold title="Agent vs. the bare signal" defaultOpen={desktop}>
            <p className="mb-2 text-xs text-muted">Average return minus RSP at 63 sessions.</p>
            <GroupList groups={{ "Agent's picks": s, "All signals": ledger.control.all,
              "Signals it picked": ledger.control.picked, "Signals it passed on": ledger.control.unpicked }} />
            <p className="mb-1.5 mt-4 text-xs font-semibold text-muted">Same setup, picked vs. passed on</p>
            <GroupList groups={ledger.control.by_setup} />
            <p className="mb-0 mt-3 text-xs text-muted">
              {ledger.control.rule}. Picked vs. passed on, at the same levels and within one setup, isolates the
              agent's selection.
            </p>
          </Fold>
        )}
        <div>
          <Fold title="By conviction"><GroupList groups={ledger.stats.by_conviction} label={(k) => `Conviction ${k}`} /></Fold>
          <Fold title="By setup"><GroupList groups={ledger.stats.by_setup} label={setupLabel} /></Fold>
        </div>
      </div>
    </>
  );
}
