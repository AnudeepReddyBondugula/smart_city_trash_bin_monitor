
export interface WardRiskLatest {
  ward: number
  avg_fill_level: number
  max_fill_level: number
  min_fill_level: number
  total_bins: number
  bins_above_80: number
  pct_bins_above_80: number
  window_end: string
}

export type RiskWard = {
  ward: number;
  avg_fill_level: number;
  pct_bins_above_80: number;
};