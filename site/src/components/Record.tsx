// Track record: headline tiles, then every pick as an expandable row.
import { useState, type ReactNode } from "react";
import { convictionDots, fmtPct, fmtPrice, fmtR, setupLabel, shortDate, signClass, statusLabel, tradingViewUrl } from "../lib/format.ts";
import type { Horizon, Ledger, LedgerStats, Pick } from "../lib/types.ts";
import { Button, Card, Fold, Num, Rows, SIGN } from "./ui.tsx";

const STATUS_TONE: Partial<Record<Pick["status"], string>> = { open: "text-accent", stopped: "text-bad", complete: "text-good" };
const HORIZONS: Horizon[] = ["5", "10", "20"];

function Tile({ label, value, sub, valueClass = "" }: { label: string; value: ReactNode; sub?: string; valueClass?: string }) {
  return (
    <div className="flex flex-col rounded-xl bg-surface-2 px-3 py-2.5">
      <span className="text-xs text-muted">{label}</span>
      <span className={`text-2xl font-extrabold tabular ${valueClass}`}>{value}</span>
      {sub && <span className="text-[0.7rem] text-muted">{sub}</span>}
    </div>
  );
}

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
          <span>{shortDate(p.as_of)} · {setupLabel(p.setup)}</span>
          <span className={STATUS_TONE[p.status] ?? "text-muted"}>{statusLabel(p.status)}</span>
        </span>
        {r != null ? <Num value={r} fmt={fmtR} className="font-bold" /> : <span className="text-muted">—</span>}
      </button>
      {open && (
        <div className="pb-3">
          <Rows items={[
            ["Conviction", convictionDots(p.conviction)],
            ["Entry", p.entry != null ? `${fmtPrice(p.entry)} on ${shortDate(p.entry_date)}` : "—"],
            ["Stop / max entry", `${fmtPrice(p.stop)} / ${fmtPrice(p.entry_max)}`],
            ["R at 5 / 10 / 20", HORIZONS.map((k) => fmtR(p.r[k])).join(" · ")],
            ["Best / worst", `${fmtR(p.mfe_r)} / ${fmtR(p.mae_r != null ? -p.mae_r : null)}`],
            ["Targets hit", `${(p.targets_hit || []).filter(Boolean).length} of ${p.targets.length}`],
          ]} />
          <div className="mt-3 flex"><Button href={tradingViewUrl(p.ticker)}>Open chart ↗</Button></div>
        </div>
      )}
    </li>
  );
}

function GroupList({ groups }: { groups: Record<string, LedgerStats> }) {
  return (
    <ul className="m-0 divide-y divide-line pl-0 text-sm">
      {Object.entries(groups).map(([k, s]) => (
        <li key={k} className="flex list-none items-baseline gap-2.5 py-2 first:pt-0">
          <span className="min-w-12 font-bold">{k}</span>
          <span className="flex-1">{s.picks} picks · {s.n_20} done · win {fmtPct(s.win_rate_20, 0, false)}</span>
          <Num value={s.avg_r_20} fmt={fmtR} className="font-bold" />
        </li>
      ))}
    </ul>
  );
}

export default function Record({ ledger }: { ledger: Ledger }) {
  const s = ledger.stats.all;
  const picks = [...ledger.picks].reverse();
  return (
    <>
      <Card className="mb-3">
        <div className="mb-2.5 grid grid-cols-2 gap-2 lg:grid-cols-4">
          <Tile label="Picks" value={s.picks} sub={`${s.filled} filled · ${s.not_filled} not filled`} />
          <Tile label="Win rate" value={fmtPct(s.win_rate_20, 0, false)} sub={`at 20 sessions · n=${s.n_20}`} />
          <Tile label="Avg R" value={fmtR(s.avg_r_20)} sub="at 20 sessions" valueClass={SIGN[signClass(s.avg_r_20)]} />
          <Tile label="SPY" value={fmtPct(s.spy_avg_pct_20)} sub="same windows" />
        </div>
        {s.n_20 === 0 ? (
          <p className="my-2 rounded-xl bg-surface-2 px-3 py-2.5 text-sm text-muted">
            No completed picks yet. Outcomes appear 5, 10 and 20 sessions after each entry.
          </p>
        ) : s.low_sample && (
          <p className="my-2 rounded-xl bg-warn-bg px-3 py-2.5 text-sm text-warn">
            Only {s.n_20} pick{s.n_20 === 1 ? "" : "s"} with a 20-session outcome. Under 30, treat these numbers as noise.
          </p>
        )}
        <p className="text-xs text-muted">
          Entry at the first open after publishing. {ledger.stats.cost_assumption}. Marked to market at 5/10/20 sessions;
          targets aren't exits.
        </p>
      </Card>
      <h2 className="mx-0.5 mb-2.5 mt-5 flex items-baseline gap-2 text-lg font-bold">
        All picks <span className="text-xs font-normal text-muted">{picks.length}</span>
      </h2>
      <Card className="mb-3 py-1"><ul className="m-0 pl-0">{picks.map((p) => <PickRow key={p.id} p={p} />)}</ul></Card>
      {ledger.control && (
        <Fold title="Agent vs. the bare signal">
          <GroupList groups={{ "Agent's picks": s, "All signals": ledger.control.all,
            "Signals it picked": ledger.control.picked, "Signals it passed on": ledger.control.unpicked }} />
          <p className="mb-1 mt-3 text-xs font-semibold text-muted">Same setup, picked vs. passed on</p>
          <GroupList groups={ledger.control.by_setup} />
          <p className="mb-0 mt-2 text-xs text-muted">
            {ledger.control.rule}. Picked vs. passed on, at the same levels and within one setup, isolates the
            agent's selection.
          </p>
        </Fold>
      )}
      <Fold title="By conviction"><GroupList groups={ledger.stats.by_conviction} /></Fold>
      <Fold title="By setup"><GroupList groups={ledger.stats.by_setup} /></Fold>
    </>
  );
}
