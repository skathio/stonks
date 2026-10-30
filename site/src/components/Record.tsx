// Track record: headline stats, then every pick (expandable rows on a phone, a table on desktop).
import { useState } from "react";
import { convictionDots, fmtPct, fmtPrice, fmtR, setupLabel, shortDate, signClass, statusLabel, tradingViewUrl } from "../lib/format.ts";
import type { Horizon, Ledger, LedgerStats, Pick } from "../lib/types.ts";
import { Button, Card, ExtLink, Fold, Icon, Num, Rows, SIGN, Stat, useMedia } from "./ui.tsx";

const STATUS_TONE: Partial<Record<Pick["status"], string>> = { open: "text-accent", stopped: "text-bad", complete: "text-good" };
const HORIZONS: Horizon[] = ["5", "10", "20"];

function latestR(p: Pick): number | null {
  for (const k of [...HORIZONS].reverse()) {
    const r = p.r[k];
    if (r != null) return r;
  }
  return null;
}

function PickRow({ p }: { p: Pick }) {
  const [open, setOpen] = useState(false);
  const r = latestR(p);
  return (
    <li className="list-none border-t border-line first:border-t-0">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
        className="flex min-h-14 w-full items-center gap-3 bg-transparent py-2 text-left text-ink">
        <span className="min-w-14 font-extrabold">{p.ticker}</span>
        <span className="flex min-w-0 flex-1 flex-col text-xs">
          <span>{shortDate(p.as_of)}, {setupLabel(p.setup)}</span>
          <span className={STATUS_TONE[p.status] ?? "text-muted"}>{statusLabel(p.status)}</span>
        </span>
        {r != null ? <Num value={r} fmt={fmtR} className="font-bold" /> : <span className="text-muted">—</span>}
        <Icon name="chevron" className={`h-4 w-4 text-muted transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="pb-3">
          <Rows items={[
            ["Conviction", convictionDots(p.conviction)],
            ["Entry", p.entry != null ? `${fmtPrice(p.entry)} on ${shortDate(p.entry_date)}` : "—"],
            ["Stop / max entry", `${fmtPrice(p.stop)} / ${fmtPrice(p.entry_max)}`],
            ["R at 5 / 10 / 20", HORIZONS.map((k) => fmtR(p.r[k])).join(", ")],
            ["Best / worst", `${fmtR(p.mfe_r)} / ${fmtR(p.mae_r != null ? -p.mae_r : null)}`],
            ["Targets hit", `${(p.targets_hit || []).filter(Boolean).length} of ${p.targets.length}`],
          ]} />
          <div className="mt-3 flex"><Button href={tradingViewUrl(p.ticker)} className="flex-1">Chart <Icon name="external" className="h-4 w-4" /></Button></div>
        </div>
      )}
    </li>
  );
}

const TH = "px-3 py-2 text-left text-xs font-semibold text-muted";
const TD = "px-3 py-2.5";

function PickTable({ picks }: { picks: Pick[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm tabular">
        <thead className="border-b border-line">
          <tr>
            <th className={TH}>Date</th><th className={TH}>Ticker</th><th className={TH}>Setup</th>
            <th className={TH}>Conviction</th><th className={TH}>Status</th>
            <th className={`${TH} text-right`}>Entry</th><th className={`${TH} text-right`}>Stop</th>
            {HORIZONS.map((h) => <th key={h} className={`${TH} text-right`}>R {h}d</th>)}
            <th className={`${TH} hidden text-right xl:table-cell`}>Best / worst</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {picks.map((p) => (
            <tr key={p.id} className="hover:bg-surface-2/60">
              <td className={`${TD} whitespace-nowrap text-muted`}>{shortDate(p.as_of)}</td>
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
              {HORIZONS.map((h) => <td key={h} className={`${TD} text-right font-semibold`}><Num value={p.r[h]} fmt={fmtR} /></td>)}
              <td className={`${TD} hidden whitespace-nowrap text-right text-muted xl:table-cell`}>{fmtR(p.mfe_r)} / {fmtR(p.mae_r != null ? -p.mae_r : null)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GroupList({ groups, label = (k) => k }: { groups: Record<string, LedgerStats>; label?: (key: string) => string }) {
  return (
    <ul className="m-0 divide-y divide-line pl-0 text-sm">
      {Object.entries(groups).map(([k, s]) => {
        const detail = `${s.picks} picks, ${s.n_20} done, win ${fmtPct(s.win_rate_20, 0, false)}`;
        return (
          <li key={k} className="grid list-none grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 py-2 first:pt-0
            lg:grid-cols-[minmax(0,1fr)_4.5rem_4.5rem_4.5rem_4.5rem]">
            <span className="font-semibold">{label(k)}</span>
            <span className="hidden text-right lg:inline">{s.picks} picks</span>
            <span className="hidden text-right lg:inline">{s.n_20} done</span>
            <span className="hidden text-right lg:inline">win {fmtPct(s.win_rate_20, 0, false)}</span>
            <Num value={s.avg_r_20} fmt={fmtR} className="text-right font-bold" />
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
  const picks = [...ledger.picks].reverse();
  return (
    <>
      <Card className="mb-5 lg:p-5">
        <div className="grid grid-cols-2 gap-y-3 lg:grid-cols-4 lg:divide-x lg:divide-line lg:[&>*]:px-4 lg:[&>*:first-child]:pl-0">
          <Stat label="Picks" value={s.picks} sub={`${s.filled} filled, ${s.not_filled} not filled`} />
          <Stat label="Win rate, 20 sessions" value={fmtPct(s.win_rate_20, 0, false)} sub={`${s.n_20} done`} />
          <Stat label="Avg result, 20 sessions" value={<span className={SIGN[signClass(s.avg_r_20)]}>{fmtR(s.avg_r_20)}</span>} sub="in units of risk (R)" />
          <Stat label="SPY, same windows" value={fmtPct(s.spy_avg_pct_20)} />
        </div>
        {s.n_20 === 0 ? (
          <p className="mt-4 rounded-xl bg-surface-2 px-3.5 py-2.5 text-sm text-muted">
            No completed picks yet. Outcomes appear 5, 10 and 20 sessions after each entry.
          </p>
        ) : s.low_sample && (
          <p className="mt-4 rounded-xl bg-warn-bg px-3.5 py-2.5 text-sm text-warn">
            Only {s.n_20} pick{s.n_20 === 1 ? "" : "s"} with a 20-session outcome. Under 30, treat these numbers as noise.
          </p>
        )}
        <p className="mt-3 text-xs text-muted">
          Entry at the first open after publishing. {ledger.stats.cost_assumption}. Marked to market at 5, 10 and 20
          sessions; targets aren't exits.
        </p>
      </Card>
      <h2 className="mx-0.5 mb-2.5 flex items-baseline gap-2 text-lg font-bold">
        All picks <span className="text-xs font-normal text-muted">{picks.length}</span>
      </h2>
      <Card className={`mb-5 ${desktop ? "p-2" : "py-1"}`}>
        {desktop ? <PickTable picks={picks} /> : <ul className="m-0 pl-0">{picks.map((p) => <PickRow key={p.id} p={p} />)}</ul>}
      </Card>
      <div className="xl:grid xl:grid-cols-2 xl:items-start xl:gap-x-3">
        {ledger.control && (
          <Fold title="Agent vs. the bare signal" defaultOpen={desktop}>
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
