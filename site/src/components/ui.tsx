// Small presentational primitives shared by the views.
import { useEffect, useState, type ComponentPropsWithoutRef, type ReactNode } from "react";
import { fmtPct, safeUrl, signClass, type Sign } from "../lib/format.ts";
import type { Tone } from "../lib/types.ts";

export type PillTone = Tone | "accent";

const TONE_TEXT: Record<Tone, string> = { good: "text-good", warn: "text-warn", bad: "text-bad", muted: "text-muted" };
const TONE_PILL: Record<PillTone, string> = {
  good: "bg-good-bg text-good",
  warn: "bg-warn-bg text-warn",
  bad: "bg-bad-bg text-bad",
  accent: "bg-accent/15 text-accent",
  muted: "bg-surface-2 text-ink",
};
export const SIGN: Record<Sign, string> = { up: "text-good", down: "text-bad", flat: "" };

export const toneText = (tone: Tone): string => TONE_TEXT[tone];

export function Card({ className = "", children, ...rest }: ComponentPropsWithoutRef<"section">) {
  return <section className={`rounded-2xl border border-line bg-surface p-4 ${className}`} {...rest}>{children}</section>;
}

export function Pill({ tone = "muted", strong = false, children }: { tone?: PillTone; strong?: boolean; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs ${strong ? "font-semibold" : ""} ${TONE_PILL[tone]}`}>
      {children}
    </span>
  );
}

/** Signed number with up/down colour. */
export function Num({ value, fmt = fmtPct, className = "" }: { value: unknown; fmt?: (x: unknown) => string; className?: string }) {
  return <span className={`tabular ${SIGN[signClass(value)]} ${className}`}>{fmt(value)}</span>;
}

interface LinkProps {
  href: unknown;
  className?: string;
  children: ReactNode;
}

export function ExtLink({ href, className = "", children }: LinkProps) {
  const url = safeUrl(href);
  if (!url) return <span className={className}>{children}</span>;
  return <a href={url} target="_blank" rel="noopener noreferrer" className={className}>{children}</a>;
}

export function Button({ href, primary = false, className = "", children }: LinkProps & { primary?: boolean }) {
  const cls = `inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl px-4 text-sm font-semibold no-underline transition-colors ${
    primary ? "bg-accent text-on-accent hover:opacity-90" : "border border-line bg-surface text-ink hover:bg-surface-2"} ${className}`;
  return <ExtLink href={href} className={cls}>{children}</ExtLink>;
}

/** Collapsible card section with a count badge. */
export function Fold({ title, count, defaultOpen = false, children }: { title: string; count?: number; defaultOpen?: boolean; children: ReactNode }) {
  return (
    <details open={defaultOpen} className="group mb-3 rounded-2xl border border-line bg-surface">
      <summary className="flex min-h-13 items-center gap-2 rounded-2xl px-4 py-3.5 font-bold hover:bg-surface-2/60">
        <span>{title}</span>
        {count != null && <span className="rounded-full bg-surface-2 px-2 text-xs font-semibold text-muted">{count}</span>}
        <Icon name="chevron" className="ml-auto text-muted transition-transform group-open:rotate-180" />
      </summary>
      <div className="px-4 pb-4">{children}</div>
    </details>
  );
}

export function SubHead({ children }: { children: ReactNode }) {
  return <h4 className="mb-1.5 mt-4 text-[0.8rem] font-semibold text-muted first:mt-0">{children}</h4>;
}

/** Label/value rows: readable on a phone where tables overflow. */
export type RowItem = readonly [label: string, value: ReactNode];

export function Rows({ items }: { items: readonly RowItem[] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
      {items.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="text-muted">{label}</dt>
          <dd className="m-0 text-right tabular">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Bullets({ items, className = "" }: { items: string[]; className?: string }) {
  return <ul className={`m-0 space-y-1 pl-5 ${className}`}>{items.map((t, i) => <li key={i} className="list-disc">{t}</li>)}</ul>;
}

/** True while the media query matches (e.g. the desktop layout). */
export function useMedia(query: string): boolean {
  const [match, setMatch] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setMatch(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [query]);
  return match;
}

const ICONS = {
  today: "M12 3v2m0 14v2M3 12h2m14 0h2M6 6l1.5 1.5M16.5 16.5 18 18M6 18l1.5-1.5M16.5 7.5 18 6M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z",
  record: "M4 19h16M6 16l4-5 3 3 5-7",
  archive: "M4 6h16M4 12h16M4 18h10",
  chevron: "m6 9 6 6 6-6",
  external: "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
  lock: "M7 11V8a5 5 0 0 1 10 0v3M6 11h12v9H6z",
  sun: "M12 3v2m0 14v2M3 12h2m14 0h2M6 6l1.5 1.5M16.5 16.5 18 18M6 18l1.5-1.5M16.5 7.5 18 6M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z",
  moon: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z",
  auto: "M12 4a8 8 0 1 0 0 16V4Z M12 4a8 8 0 1 1 0 16",
} as const;

export type IconName = keyof typeof ICONS;

/** Stroke icon (decorative: the control carries the label). */
export function Icon({ name, className = "" }: { name: IconName; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true" className={`inline-block shrink-0 ${className}`}>
      <path d={ICONS[name]} />
    </svg>
  );
}

/** Label over a value: the compact stat used in strips (no box; strips divide them). */
export function Stat({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: Tone }) {
  return (
    <div className="flex min-w-0 flex-col">
      <span className="text-xs text-muted">{label}</span>
      <span className={`text-lg font-bold leading-tight tabular ${tone ? TONE_TEXT[tone] : ""}`}>{value}</span>
      {sub != null && <span className="text-xs text-muted">{sub}</span>}
    </div>
  );
}
