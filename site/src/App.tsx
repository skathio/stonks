// App shell: unlock, hash routing, header + tab bar.
import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import { routeFromHash, shortDate, type Route } from "./lib/format.ts";
import { applyTheme, loadTheme, nextTheme, type Theme } from "./lib/theme.ts";
import type { Day, DashboardIndex, KeyInfo, Ledger } from "./lib/types.ts";
import { acceptKey, fetchKeyInfo, forgetKey, hashHasKey, makeLoader, restoreKey, type Loader } from "./lib/vault.ts";
import Record from "./components/Record.tsx";
import Today from "./components/Today.tsx";
import { Card } from "./components/ui.tsx";

type Phase = "loading" | "empty" | "locked" | "ready" | "error";
type View = { kind: "record"; ledger: Ledger } | { kind: "day"; date: string; day: Day; missing: boolean };
type Section = "today" | "record" | "archive";

const errorText = (err: unknown): string => (err instanceof Error ? err.message : String(err));

function useHashRoute(): Route {
  const [route, setRoute] = useState<Route>(() => routeFromHash(location.hash));
  useEffect(() => {
    const onHash = () => setRoute(routeFromHash(location.hash));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  return route;
}

function Lock({ keyinfo, onUnlock }: { keyinfo: KeyInfo; onUnlock: (key: CryptoKey) => void }) {
  const [value, setValue] = useState("");
  const [status, setStatus] = useState("");
  async function submit(ev: FormEvent<HTMLFormElement>) {
    ev.preventDefault();
    const key = await acceptKey(value, keyinfo);
    setValue("");
    if (key) onUnlock(key);
    else setStatus("That link or key doesn't open the current dashboard.");
  }
  return (
    <form onSubmit={(ev) => void submit(ev)} className="mx-auto mt-10 flex max-w-md flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
      <h2 className="text-lg font-bold">Dashboard locked</h2>
      <p className="text-sm text-muted">
        Open your unlock link once on this device, or paste it here. The data is encrypted and decrypted in this
        browser; the key never leaves it.
      </p>
      <input type="password" autoComplete="off" required aria-label="Unlock link or key" placeholder="Paste your unlock link"
        value={value} onChange={(e) => setValue(e.target.value)}
        className="rounded-xl border border-line bg-bg px-3 py-3 text-base text-ink" />
      <button type="submit" className="min-h-12 rounded-xl bg-accent font-bold text-on-accent">Unlock</button>
      <p role="status" className="min-h-5 text-sm text-bad">{status}</p>
    </form>
  );
}

const THEME_ICON: Record<Theme, string> = { auto: "◐", light: "☀", dark: "☾" };
const THEME_LABEL: Record<Theme, string> = { auto: "Theme: auto (follows system)", light: "Theme: light", dark: "Theme: dark" };

function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(loadTheme);
  function cycle() {
    const next = nextTheme(theme);
    applyTheme(next);
    setTheme(next);
  }
  return (
    <button type="button" onClick={cycle} aria-label={`${THEME_LABEL[theme]}. Tap to change.`} title={THEME_LABEL[theme]}
      className="h-11 w-11 rounded-xl border border-line bg-surface text-lg text-ink">{THEME_ICON[theme]}</button>
  );
}

function Tab({ href, active, icon, children }: { href: string; active: boolean; icon: string; children: ReactNode }) {
  return (
    <a href={href} aria-current={active ? "page" : undefined}
      className={`flex flex-1 flex-col items-center justify-center gap-0.5 text-xs no-underline lg:flex-none lg:flex-row lg:gap-1.5 lg:rounded-lg lg:px-3.5 lg:py-2 lg:text-sm ${
        active ? "font-semibold text-accent lg:bg-surface-2" : "text-muted"}`}>
      <span aria-hidden="true" className="text-lg leading-none lg:text-base">{icon}</span>
      <span>{children}</span>
    </a>
  );
}

function TabBar({ index, active, date }: { index: DashboardIndex; active: Section; date: string | undefined }) {
  return (
    <nav aria-label="Sections"
      className="fixed inset-x-0 bottom-0 z-10 flex h-[calc(4rem+env(safe-area-inset-bottom))] border-t border-line bg-surface pb-safe
        lg:sticky lg:top-[4.25rem] lg:mb-4 lg:inline-flex lg:h-auto lg:gap-1 lg:rounded-xl lg:border lg:p-1">
      <Tab href={`#/day/${index.latest}`} active={active === "today"} icon="◎">Today</Tab>
      <Tab href="#/record" active={active === "record"} icon="↗">Record</Tab>
      {/* Styled like a tab; an invisible native select covers it, so the picker is still the
          OS one (good on phones). Until a past day is open it reads "Archive", not the latest
          date, which would just repeat the Today tab. */}
      <div className={`relative flex flex-1 flex-col items-center justify-center gap-0.5 text-xs focus-within:ring-2 focus-within:ring-accent lg:flex-none lg:flex-row lg:gap-1.5 lg:rounded-lg lg:px-3.5 lg:py-2 lg:text-sm lg:hover:bg-surface-2 ${
        active === "archive" ? "font-semibold text-accent lg:bg-surface-2" : "text-muted"}`}>
        <span aria-hidden="true" className="text-lg leading-none lg:text-base">☰</span>
        <span aria-hidden="true" className="flex items-center gap-1">
          {active === "archive" && date ? shortDate(date) : "Archive"}
          <span className="text-[0.7em] opacity-70">▾</span>
        </span>
        <select aria-label="Archive date" value={active === "archive" ? date : ""}
          onChange={(e) => { if (e.target.value) location.hash = `#/day/${e.target.value}`; }}
          className="absolute inset-0 h-full w-full cursor-pointer appearance-none opacity-0">
          {active !== "archive" && <option value="" disabled>Archive</option>}
          {[...index.days].reverse().map((d) => (
            <option key={d} value={d}>{d === index.latest ? `${shortDate(d)} (today)` : shortDate(d)}</option>))}
        </select>
      </div>
    </nav>
  );
}

export default function App() {
  const route = useHashRoute();
  const [phase, setPhase] = useState<Phase>("loading");
  const [keyinfo, setKeyinfo] = useState<KeyInfo | null>(null);
  const [load, setLoad] = useState<Loader | null>(null);
  const [index, setIndex] = useState<DashboardIndex | null>(null);
  const [view, setView] = useState<View | null>(null);
  const [error, setError] = useState("");

  const unlock = useCallback(async (key: CryptoKey) => {
    const loader = makeLoader(key);
    try {
      setIndex(await loader<DashboardIndex>("index.json"));
      setLoad(() => loader);
      setPhase("ready");
    } catch (err) {
      setError(errorText(err));
      setPhase("error");
    }
  }, []);

  useEffect(() => {
    void (async () => {
      const info = await fetchKeyInfo().catch(() => null);
      if (!info) return setPhase("empty");
      setKeyinfo(info);
      const key = await restoreKey(info);
      if (key) await unlock(key);
      else setPhase("locked");
    })();
  }, [unlock]);

  // An unlock link opened in an already-open tab.
  useEffect(() => {
    if (keyinfo && hashHasKey()) void restoreKey(keyinfo).then((key) => key && unlock(key));
  }, [route, keyinfo, unlock]);

  useEffect(() => {
    if (phase !== "ready" || !load || !index) return;
    let cancelled = false;
    void (async () => {
      try {
        if (route.view === "record") {
          const ledger = await load<Ledger>("ledger.json");
          if (!cancelled) setView({ kind: "record", ledger });
        } else {
          const date = route.date && index.days.includes(route.date) ? route.date : index.latest;
          const day = await load<Day>(`days/${date}.json`);
          if (!cancelled) setView({ kind: "day", date, day, missing: route.date != null && route.date !== date });
        }
        window.scrollTo(0, 0);
      } catch (err) {
        if (!cancelled) { setError(errorText(err)); setPhase("error"); }
      }
    })();
    return () => { cancelled = true; };
  }, [phase, route, load, index]);

  function lock() {
    forgetKey();
    setLoad(null);
    setView(null);
    setPhase("locked");
  }

  const dayDate = view?.kind === "day" ? view.date : undefined;
  const active: Section = view?.kind === "record" ? "record" : dayDate && index && dayDate !== index.latest ? "archive" : "today";
  const subtitle = view?.kind === "record" ? "Track record"
    : dayDate ? `${shortDate(dayDate)} close${active === "archive" ? " · archive" : ""}` : "";

  return (
    <div className="mx-auto max-w-6xl px-4 pb-[calc(5.5rem+env(safe-area-inset-bottom))] lg:px-6 lg:pb-8">
      <header className="sticky top-0 z-20 -mx-4 mb-3 flex items-center justify-between gap-3 border-b border-line bg-bg/90 px-4 py-2.5 backdrop-blur lg:-mx-6 lg:px-6">
        <div>
          <h1 className="text-base font-bold">Stonks</h1>
          {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
        </div>
        <div className="flex gap-2">
          <ThemeToggle />
        {phase === "ready" && (
          <button type="button" onClick={lock} aria-label="Lock dashboard" title="Lock"
            className="h-11 w-11 rounded-xl border border-line bg-surface text-lg">🔒</button>
        )}
        </div>
      </header>

      {phase === "ready" && index && <TabBar index={index} active={active} date={dayDate} />}

      <main>
        {phase === "loading" && <p className="text-muted">Loading…</p>}
        {phase === "empty" && <Card className="text-muted">No analysis has been published yet.</Card>}
        {phase === "locked" && keyinfo && <Lock keyinfo={keyinfo} onUnlock={(key) => void unlock(key)} />}
        {phase === "error" && <Card className="bg-bad-bg text-bad">Could not load data: {error}</Card>}
        {phase === "ready" && view?.kind === "day" && (<>
          {view.missing && <Card className="mb-3 text-sm text-muted">No analysis for that date; showing the latest.</Card>}
          <Today day={view.day} />
        </>)}
        {phase === "ready" && view?.kind === "record" && <Record ledger={view.ledger} />}
      </main>

      <footer className="mx-0.5 mt-5 text-xs text-muted">
        Personal research notes produced by an automated agent. Not investment advice. Levels come from the last
        closed session; check the chart before acting.
      </footer>
    </div>
  );
}
