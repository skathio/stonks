// =============================================================================
// Pure formatting helpers for the dashboard (no DOM), unit-tested in tests/.
// =============================================================================
import type { BookFlag, Earnings, PickStatus, ReviewAction, Tone } from "./types.ts";

const DASH = "—";

export function isNum(x: unknown): x is number {
  return typeof x === "number" && Number.isFinite(x);
}

export function fmtNum(x: unknown, digits = 2): string {
  return isNum(x) ? x.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }) : DASH;
}

export function fmtPct(x: unknown, digits = 1, signed = true): string {
  if (!isNum(x)) return DASH;
  const s = x.toFixed(digits);
  return `${signed && x > 0 ? "+" : ""}${s}%`;
}

export function fmtR(x: unknown): string {
  return isNum(x) ? `${x > 0 ? "+" : ""}${x.toFixed(2)}R` : DASH;
}

export function fmtPrice(x: unknown): string {
  return isNum(x) ? `$${fmtNum(x, 2)}` : DASH;
}

export type Sign = "up" | "down" | "flat";

export function signClass(x: unknown): Sign {
  if (!isNum(x) || x === 0) return "flat";
  return x > 0 ? "up" : "down";
}

const REGIME: Record<string, { label: string; tone: Tone }> = {
  risk_on: { label: "Risk-on", tone: "good" },
  neutral: { label: "Neutral", tone: "warn" },
  risk_off: { label: "Risk-off", tone: "bad" },
};

export function regimeInfo(label: string | null | undefined): { label: string; tone: Tone } {
  return REGIME[label ?? ""] ?? { label: String(label ?? "unknown"), tone: "muted" };
}

const STATUS: Record<PickStatus, string> = {
  pending: "Awaiting entry",
  open: "Open",
  stopped: "Stopped out",
  complete: "Complete (126 sessions)",
  not_filled: "Not filled (opened above chase limit)",
  gap_below_stop: "Not filled (gapped below stop)",
};

export function statusLabel(status: string | null | undefined): string {
  return STATUS[status as PickStatus] ?? String(status ?? "");
}

const SETUP: Record<string, string> = {
  breakout: "Breakout",
  squeeze: "Squeeze",
  pullback_reclaim: "Pullback reclaim",
  base: "Base",
  other: "Other",
};

export function setupLabel(setup: string | null | undefined): string {
  return SETUP[setup ?? ""] ?? String(setup ?? "");
}

/** Only https URLs reach an href; anything else renders as plain text. */
export function safeUrl(url: unknown): string | null {
  if (typeof url !== "string") return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

export function tradingViewUrl(ticker: string): string {
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(String(ticker).replace("-", "."))}`;
}

export function convictionDots(n: unknown): string {
  const k = Math.max(0, Math.min(5, Math.round(Number(n) || 0)));
  return "●".repeat(k) + "○".repeat(5 - k);
}

export interface Note {
  text: string;
  tone: Tone;
  inside?: boolean;
}

export function earningsNote(earnings: Earnings | null | undefined, horizon: unknown): Note {
  if (!earnings) return { text: "No date found", tone: "muted" };
  const when = `${earnings.date}${earnings.hour ? ` (${earnings.hour})` : ""}, ${earnings.sessions_away} sessions`;
  const conflict = earnings.conflict ? " · sources disagree" : "";
  const inside = isNum(earnings.sessions_away) && isNum(horizon) && earnings.sessions_away <= horizon;
  return { text: `${when}${conflict}`, tone: inside ? "warn" : "muted", inside };
}

export type Route = { view: "record" } | { view: "day"; date: string | null };

export function routeFromHash(hash: unknown): Route {
  const h = String(hash || "").replace(/^#\/?/, "");
  if (h === "record") return { view: "record" };
  const m = h.match(/^day\/(\d{4}-\d{2}-\d{2})$/);
  if (m?.[1]) return { view: "day", date: m[1] };
  return { view: "day", date: null };
}

/** Percent change from `from` to `to`, or null. */
export function pctFrom(from: unknown, to: unknown): number | null {
  return isNum(from) && isNum(to) && from !== 0 ? (100 * (to - from)) / from : null;
}

/** First sentence of a paragraph, for a one-line headline. */
export function firstSentence(text: unknown, max = 180): string {
  const s = String(text ?? "").trim();
  const m = s.match(/^.+?[.!?](?=\s|$)/);
  const out = m?.[0] ?? s;
  return out.length > max ? `${out.slice(0, max - 1).trimEnd()}…` : out;
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-10-28" -> "Wed Oct 28" (date-only, no timezone shift). */
export function shortDate(iso: unknown): string {
  const m = String(iso ?? "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return String(iso ?? "");
  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
  return `${WEEKDAYS[d.getUTCDay()]} ${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
}

/** Compact earnings chip text + tone. */
export function earningsChip(earnings: Earnings | null | undefined, horizon: unknown): Note {
  if (!earnings) return { text: "Earnings: none scheduled", tone: "muted" };
  const n = earnings.sessions_away;
  const inside = isNum(n) && isNum(horizon) && n <= horizon;
  return { text: `Earnings ${shortDate(earnings.date)} · ${n}d${earnings.conflict ? " ⚠" : ""}`, tone: inside ? "warn" : "muted", inside };
}

/** v2 earnings line: next report (or its estimate) and how many fall inside the hold. */
export function nextReport(earnings: Earnings | null | undefined, inHold: unknown): Note {
  if (!earnings) return { text: "Next report: no date", tone: "muted" };
  const when = `${shortDate(earnings.date)}${earnings.estimated ? " (est.)" : ""}, ${earnings.sessions_away} sessions`;
  const count = isNum(inHold) && inHold > 0 ? `; ${inHold} report${inHold === 1 ? "" : "s"} in the hold` : "";
  const soon = isNum(earnings.sessions_away) && earnings.sessions_away < 15;
  return { text: `Next report ${when}${count}`, tone: soon ? "warn" : "muted", inside: soon };
}

/** 84 sessions -> "about 4 months" (21 sessions a month). */
export function sessionsToMonths(n: unknown): string {
  if (!isNum(n)) return DASH;
  const m = Math.round(n / 21);
  return m <= 1 ? "about 1 month" : `about ${m} months`;
}

const FLAG: Record<BookFlag, { text: string; tone: Tone }> = {
  near_stop: { text: "Within 1 ATR of the stop", tone: "bad" },
  below_ema50: { text: "Below the 50-day trend", tone: "warn" },
  rs_faded: { text: "RS rank under 60", tone: "warn" },
  earnings_soon: { text: "Report within 5 sessions", tone: "warn" },
  review_due: { text: "Planned hold reached: review", tone: "warn" },
  upside_reached: { text: "+20% traded", tone: "good" },
};

export function flagInfo(flag: string): { text: string; tone: Tone } {
  return FLAG[flag as BookFlag] ?? { text: flag, tone: "muted" };
}

const ACTION_TONE: Record<ReviewAction, Tone> = { hold: "muted", add: "good", trim: "warn", exit: "bad" };

export function actionTone(action: string): Tone {
  return ACTION_TONE[action as ReviewAction] ?? "muted";
}

/** Size multiplier text: 0.23 -> "×0.23". */
export function fmtScale(x: unknown): string {
  return isNum(x) ? `×${x.toFixed(2)}` : DASH;
}

/** Tone for the momentum size scale: full size is good, under half is bad. */
export function scaleTone(x: unknown): Tone {
  if (!isNum(x)) return "muted";
  return x >= 0.8 ? "good" : x >= 0.5 ? "warn" : "bad";
}

/** Shared axis [min, max] (percent from close) for the pick ladders, always spanning 0. */
export function ladderAxis(values: number[]): [number, number] {
  const finite = values.filter(isNum);
  const lo = Math.min(0, ...finite);
  const hi = Math.max(0, ...finite);
  const pad = (hi - lo || 1) * 0.04;
  return [lo - pad, hi + pad];
}

/** Position of `x` on an axis as 0..100 (clamped). */
export function axisPos(x: number, [lo, hi]: [number, number]): number {
  return hi === lo ? 50 : Math.min(100, Math.max(0, (100 * (x - lo)) / (hi - lo)));
}
