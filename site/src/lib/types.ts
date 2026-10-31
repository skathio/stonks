// =============================================================================
// Shapes of the decrypted dashboard payload, written by pipeline/daily.py
// (publish) and pipeline/ledger.py. Keep in step with those writers.
// =============================================================================

export type Tone = "good" | "warn" | "bad" | "muted";
/** Ledger marks in sessions (rules v2: position trades). */
export type Horizon = "21" | "42" | "63" | "126";
export const HORIZONS: Horizon[] = ["21", "42", "63", "126"];

export interface DashboardIndex {
  days: string[];
  latest: string;
}

export interface Earnings {
  date: string;
  hour?: string | null;
  sessions_away: number;
  conflict?: boolean;
  /** One quarter after the last report: no date published yet. */
  estimated?: boolean;
}

export interface Catalyst {
  date: string;
  text: string;
  source_url?: string | null;
}

export interface NewsItem {
  date: string;
  headline: string;
  source: string;
  summary?: string;
  url: string;
}

export interface Features {
  adv20_usd_m: number;
  atr_pct: number;
  bars_since_squeeze?: number | null;
  dist_52wh_atr: number;
  ext_ema21_atr: number;
  pct_off_52wh: number;
  ret_21d_pct: number;
  ret_63d_pct: number;
  ret_126d_pct?: number | null;
  rs_rank: number;
  rs_rising: boolean;
  tags: string[];
  trend_stack: boolean;
  vol_ratio: number;
}

export interface Levels {
  atr: number;
  entry_max: number;
  ref_close: number;
  stop: number;
  stop_pct: number;
  /** The +20% reference level (never an exit). */
  targets: number[];
  targets_r: number[];
  /** Account % for the position: 1% risk at the stop x momentum size scale. */
  position_pct?: number | null;
}

export interface Candidate {
  ticker: string;
  name: string;
  sector: string;
  setup: string;
  conviction: number;
  thesis: string;
  catalysts: Catalyst[];
  risks: string[];
  invalidation: string;
  earnings: Earnings | null;
  /** Reports expected inside the planned hold. */
  reports_in_hold: number;
  earnings_plan: string;
  upside_case: string;
  chart_checks: string[];
  features: Features;
  levels: Levels;
  horizon_sessions: number;
  max_chase_atr: number;
  stop_atr: number;
  news?: NewsItem[];
}

export interface WatchItem {
  ticker: string;
  name: string;
  close?: number | null;
  trigger: string;
  note?: string | null;
}

export interface AvoidItem {
  ticker: string;
  name: string;
  close?: number | null;
  reason: string;
}

export interface Regime {
  label: string;
  exposure: string;
  summary: string;
  evidence: string[];
  disagrees_with_baseline: boolean;
}

export interface Analysis {
  as_of: string;
  regime: Regime;
  candidates: Candidate[];
  /** The agent's calls on open positions. */
  reviews: Review[];
  prompt_version?: string;
  watchlist: WatchItem[];
  avoid: AvoidItem[];
  market_notes: string[];
  data_issues: string[];
}

export interface Benchmark {
  close: number;
  above_ema50: boolean;
  ema50_rising: boolean;
  risk_on_gate: boolean;
  atr_pct: number;
  close_vs_sma200_pct: number;
  drawdown_from_52wh_pct: number;
  ret_5d_pct: number;
  ret_21d_pct: number;
  ret_63d_pct: number;
}

export interface MacroSeries {
  series: string;
  date: string;
  value: number;
  chg_20obs: number;
}

export interface Sector {
  etf: string;
  sector: string;
  members: number;
  pct_trend_stack: number;
  ret_21d_pct: number;
  ret_63d_pct: number;
  risk_on_gate: boolean;
  rs_63d_vs_spy: number | null;
}

export interface Market {
  baseline_regime: { label: string; rule: string; score: number };
  benchmarks: Partial<Record<string, Benchmark>>;
  macro?: Partial<Record<"vix" | "hy_oas" | "ust10y" | "curve_10y2y", MacroSeries>>;
  sectors: Sector[];
  tag_counts: Record<string, number>;
  universe: { eligible: number; scan_members: number; with_features: number };
}

export interface BreadthDay {
  date: string;
  n: number;
  advancers: number;
  decliners: number;
  new_52w_highs: number;
  new_52w_lows: number;
  pct_above_sma50: number;
  pct_above_sma200: number;
}

/** Momentum health (pipeline features.momentum_health): MTUM vs SPY / RSP and the size scale. */
export interface Momentum {
  mtum_vs_spy_21d_pct: number | null;
  mtum_vs_spy_63d_pct: number | null;
  mtum_vs_rsp_21d_pct: number | null;
  mtum_vs_rsp_63d_pct: number | null;
  spread_vol_ann_pct: number;
  target_vol_ann_pct: number;
  size_scale: number;
}

export type ReviewAction = "hold" | "trim" | "exit" | "add";

export interface Review {
  ticker: string;
  action: ReviewAction;
  note: string;
}

/** Benchmark-relative mark of an open position (ledger.evaluate). */
export interface Mark {
  date: string;
  sessions: number;
  pct: number;
  spy_pct?: number;
  rsp_pct?: number;
}

export type BookFlag = "near_stop" | "below_ema50" | "rs_faded" | "earnings_soon" | "review_due" | "upside_reached";

/** One open position (daily.book_view). */
export interface Position {
  ticker: string;
  sector: string;
  as_of: string;
  status: PickStatus;
  entry: number | null;
  entry_date: string | null;
  stop: number;
  close: number | null;
  stop_dist_pct: number | null;
  position_pct?: number | null;
  horizon_sessions?: number | null;
  mark: Mark | null;
  next_earnings: Earnings | null;
  flags: BookFlag[];
  review: Review | null;
}

export interface BookLimits {
  max_open: number;
  max_per_sector: number;
  max_new: number;
  risk_per_trade_pct: number;
}

export interface Day {
  as_of: string;
  generated_utc: string;
  analysis: Analysis;
  market: Market;
  momentum?: Momentum | null;
  /** Open positions and the book limits. */
  book: Position[];
  limits: BookLimits;
  breadth: BreadthDay[];
}

export type PickStatus = "pending" | "open" | "stopped" | "complete" | "not_filled" | "gap_below_stop";

export interface Pick {
  id: string;
  ticker: string;
  as_of: string;
  published_utc: string;
  sector: string;
  setup: string;
  conviction: number;
  tags: string[];
  status: PickStatus;
  atr: number;
  ref_close: number;
  entry_max: number;
  stop: number;
  stop_atr: number;
  targets: number[];
  targets_r?: number[];
  targets_hit?: (string | null)[];
  entry: number | null;
  entry_date: string | null;
  exit_date: string | null;
  exit_r: number | null;
  exit_pct?: number | null;
  exit_reason: string | null;
  r: Partial<Record<Horizon, number>>;
  pct?: Partial<Record<Horizon, number>>;
  spy_pct: Partial<Record<Horizon, number>>;
  rsp_pct?: Partial<Record<Horizon, number>>;
  mark?: Mark | null;
  mfe_r: number | null;
  mae_r: number | null;
  size_scale?: number | null;
  position_pct?: number | null;
  horizon_sessions?: number | null;
  rules_version?: string;
}

type PerHorizon<P extends string, T> = { [K in `${P}_${Horizon}`]?: T };

/** ledger.summarize: per-horizon keys like n_63, avg_pct_63, avg_ex_rsp_63. */
export type LedgerStats = {
  picks: number;
  filled: number;
  not_filled: number;
  stopped: number;
  open?: number;
  reached_upside?: number;
  low_sample: boolean;
  avg_mark_pct?: number | null;
  avg_mark_ex_rsp?: number | null;
  avg_mfe_r: number | null;
} & PerHorizon<"n" | "weeks", number>
  & PerHorizon<"avg_pct" | "avg_r" | "win_rate" | "avg_ex_rsp" | "avg_ex_spy" | "beat_rsp", number | null>;

export interface Ledger {
  updated: string;
  picks: Pick[];
  stats: {
    version?: string;
    headline?: number;
    all: LedgerStats;
    by_conviction: Record<string, LedgerStats>;
    by_setup: Record<string, LedgerStats>;
    cost_assumption: string;
  };
  /** Control arm: every in-context mechanical signal at fixed levels (pipeline/ledger.py). */
  control?: {
    version?: string;
    all: LedgerStats; picked: LedgerStats; unpicked: LedgerStats;
    by_setup: Record<string, LedgerStats>; rule: string;
  };
}

/** AES-GCM file envelope (see crypto.ts). */
export interface Envelope {
  v: number;
  iv: string;
  ct: string;
}

export interface KeyInfo {
  v: number;
  cipher: string;
  check: Envelope;
}
