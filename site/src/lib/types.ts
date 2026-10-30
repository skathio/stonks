// =============================================================================
// Shapes of the decrypted dashboard payload, written by pipeline/daily.py
// (publish) and pipeline/ledger.py. Keep in step with those writers.
// =============================================================================

export type Tone = "good" | "warn" | "bad" | "muted";
export type Horizon = "5" | "10" | "20";

export interface DashboardIndex {
  days: string[];
  latest: string;
}

export interface Earnings {
  date: string;
  hour?: string | null;
  sessions_away: number;
  conflict?: boolean;
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
  targets: number[];
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
  earnings_inside_horizon: boolean;
  earnings_plan?: string | null;
  chart_checks: string[];
  features: Features;
  levels: Levels;
  horizon_sessions: number;
  max_chase_atr: number;
  stop_atr: number;
  targets_r: number[];
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

export interface Day {
  as_of: string;
  generated_utc: string;
  analysis: Analysis;
  market: Market;
  momentum?: Momentum | null;
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
  targets_r: number[];
  targets_hit?: (string | null)[];
  entry: number | null;
  entry_date: string | null;
  exit_date: string | null;
  exit_r: number | null;
  exit_reason: string | null;
  r: Partial<Record<Horizon, number>>;
  spy_pct: Partial<Record<Horizon, number>>;
  mfe_r: number | null;
  mae_r: number | null;
  size_scale?: number | null;
}

export interface LedgerStats {
  picks: number;
  filled: number;
  not_filled: number;
  stopped: number;
  low_sample: boolean;
  n_5: number;
  n_10: number;
  n_20: number;
  avg_r_5: number | null;
  avg_r_10: number | null;
  avg_r_20: number | null;
  win_rate_5: number | null;
  win_rate_10: number | null;
  win_rate_20: number | null;
  spy_avg_pct_5: number | null;
  spy_avg_pct_10: number | null;
  spy_avg_pct_20: number | null;
  avg_mfe_r: number | null;
}

export interface Ledger {
  updated: string;
  picks: Pick[];
  stats: {
    all: LedgerStats;
    by_conviction: Record<string, LedgerStats>;
    by_setup: Record<string, LedgerStats>;
    cost_assumption: string;
  };
  /** Control arm: every in-context mechanical signal at fixed levels (pipeline/ledger.py). */
  control?: {
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
