// =============================================================================
// Pure formatting helpers for the dashboard (no DOM), unit-tested in tests/.
// =============================================================================
const DASH = "—";

export function isNum(x) {
  return typeof x === "number" && Number.isFinite(x);
}

export function fmtNum(x, digits = 2) {
  return isNum(x) ? x.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits }) : DASH;
}

export function fmtPct(x, digits = 1, signed = true) {
  if (!isNum(x)) return DASH;
  const s = x.toFixed(digits);
  return `${signed && x > 0 ? "+" : ""}${s}%`;
}

export function fmtR(x) {
  return isNum(x) ? `${x > 0 ? "+" : ""}${x.toFixed(2)}R` : DASH;
}

export function fmtPrice(x) {
  return isNum(x) ? `$${fmtNum(x, 2)}` : DASH;
}

export function signClass(x) {
  if (!isNum(x) || x === 0) return "flat";
  return x > 0 ? "up" : "down";
}

const REGIME = {
  risk_on: { label: "Risk-on", tone: "good" },
  neutral: { label: "Neutral", tone: "warn" },
  risk_off: { label: "Risk-off", tone: "bad" },
};

export function regimeInfo(label) {
  return REGIME[label] ?? { label: String(label ?? "unknown"), tone: "muted" };
}

const STATUS = {
  pending: "Awaiting entry",
  open: "Open",
  stopped: "Stopped out",
  complete: "Complete (20 sessions)",
  not_filled: "Not filled (opened above chase limit)",
  gap_below_stop: "Not filled (gapped below stop)",
};

export function statusLabel(status) {
  return STATUS[status] ?? String(status ?? "");
}

const SETUP = {
  breakout: "Breakout",
  squeeze: "Squeeze",
  pullback_reclaim: "Pullback reclaim",
  base: "Base",
  other: "Other",
};

export function setupLabel(setup) {
  return SETUP[setup] ?? String(setup ?? "");
}

/** Only https URLs reach an href; anything else renders as plain text. */
export function safeUrl(url) {
  if (typeof url !== "string") return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

export function tradingViewUrl(ticker) {
  return `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(String(ticker).replace("-", "."))}`;
}

export function convictionDots(n) {
  const k = Math.max(0, Math.min(5, Math.round(Number(n) || 0)));
  return "●".repeat(k) + "○".repeat(5 - k);
}

export function earningsNote(earnings, horizon) {
  if (!earnings) return { text: "No date found", tone: "muted" };
  const when = `${earnings.date}${earnings.hour ? ` (${earnings.hour})` : ""}, ${earnings.sessions_away} sessions`;
  const conflict = earnings.conflict ? " · sources disagree" : "";
  const inside = isNum(earnings.sessions_away) && isNum(horizon) && earnings.sessions_away <= horizon;
  return { text: `${when}${conflict}`, tone: inside ? "warn" : "muted", inside };
}

export function routeFromHash(hash) {
  const h = String(hash || "").replace(/^#\/?/, "");
  if (h === "record") return { view: "record" };
  const m = h.match(/^day\/(\d{4}-\d{2}-\d{2})$/);
  if (m) return { view: "day", date: m[1] };
  return { view: "day", date: null };
}

/** Percent change from `from` to `to`, or null. */
export function pctFrom(from, to) {
  return isNum(from) && isNum(to) && from !== 0 ? (100 * (to - from)) / from : null;
}

/** First sentence of a paragraph, for a one-line headline. */
export function firstSentence(text, max = 180) {
  const s = String(text ?? "").trim();
  const m = s.match(/^.+?[.!?](?=\s|$)/);
  const out = m ? m[0] : s;
  return out.length > max ? `${out.slice(0, max - 1).trimEnd()}…` : out;
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-10-28" -> "Wed Oct 28" (date-only, no timezone shift). */
export function shortDate(iso) {
  const m = String(iso ?? "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return String(iso ?? "");
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  return `${WEEKDAYS[d.getUTCDay()]} ${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
}

/** Compact earnings chip text + tone. */
export function earningsChip(earnings, horizon) {
  if (!earnings) return { text: "Earnings: none scheduled", tone: "muted" };
  const n = earnings.sessions_away;
  const inside = isNum(n) && isNum(horizon) && n <= horizon;
  return { text: `Earnings ${shortDate(earnings.date)} · ${n}d${earnings.conflict ? " ⚠" : ""}`, tone: inside ? "warn" : "muted", inside };
}
