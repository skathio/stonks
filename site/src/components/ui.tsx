// Small presentational primitives shared by the views.
import type { ComponentPropsWithoutRef, ReactNode } from "react";
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
  return <span className={`font-mono tabular ${SIGN[signClass(value)]} ${className}`}>{fmt(value)}</span>;
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
  const cls = `inline-flex min-h-11 flex-1 items-center justify-center rounded-xl px-4 text-sm font-semibold no-underline ${
    primary ? "bg-accent text-on-accent" : "border border-line bg-surface text-ink"} ${className}`;
  return <ExtLink href={href} className={cls}>{children}</ExtLink>;
}

/** Collapsible card section with a count badge. */
export function Fold({ title, count, defaultOpen = false, children }: { title: string; count?: number; defaultOpen?: boolean; children: ReactNode }) {
  return (
    <details open={defaultOpen} className="group mb-3 rounded-2xl border border-line bg-surface">
      <summary className="flex min-h-13 items-center gap-2 px-4 py-3.5 font-bold">
        <span>{title}</span>
        {count != null && <span className="rounded-full bg-surface-2 px-2 text-xs font-semibold text-muted">{count}</span>}
        <span className="ml-auto inline-block text-muted transition-transform group-open:rotate-180" aria-hidden="true">▾</span>
      </summary>
      <div className="px-4 pb-4">{children}</div>
    </details>
  );
}

export function SubHead({ children }: { children: ReactNode }) {
  return <h4 className="mb-1.5 mt-4 text-[0.72rem] font-semibold uppercase tracking-wider text-muted first:mt-0">{children}</h4>;
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
