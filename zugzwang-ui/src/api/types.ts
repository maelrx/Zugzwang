import type { components } from "./schema";

export type BoardFrameResponse = components["schemas"]["BoardFrameResponse"];
export type CancelJobResponse = components["schemas"]["CancelJobResponse"];
export type ConfigListResponse = components["schemas"]["ConfigListResponse"];
export type ConfigPreviewResponse = components["schemas"]["ConfigPreviewResponse"];
export type ConfigValidateRequest = components["schemas"]["ConfigValidateRequest"];
export type ConfigValidateResponse = components["schemas"]["ConfigValidateResponse"];
export type DashboardKpisResponse = components["schemas"]["DashboardKpisResponse"];
export type EnvCheckResponse = components["schemas"]["EnvCheckResponse"];
export type GameDetailResponse = components["schemas"]["GameDetailResponse"];
export type GameListItem = components["schemas"]["GameListItem"];
export type JobResponse = components["schemas"]["JobResponse"];
export type RunListItem = components["schemas"]["RunListItem"];
export type RunProgressResponse = components["schemas"]["RunProgressResponse"];
export type RunSummaryResponse = components["schemas"]["RunSummaryResponse"];
export type StartEvalRequest = components["schemas"]["StartEvalRequest"];
export type StartJobRequest = components["schemas"]["StartJobRequest"];

export type ModelOptionResponse = {
  id: string;
  label: string;
  recommended?: boolean;
};

export type ModelProviderPresetResponse = {
  provider: string;
  provider_label: string;
  api_style: string;
  base_url: string;
  api_key_env: string;
  notes: string;
  models: ModelOptionResponse[];
};

export type AnalysisCompareRequest = {
  run_a: string;
  run_b: string;
  comparison_id?: string | null;
  confidence?: number;
  alpha?: number;
  bootstrap_iterations?: number;
  permutation_iterations?: number;
  seed?: number;
};

export type AnalysisRunSampleResponse = {
  run_id: string;
  run_dir: string;
  player_color: string;
  total_games: number;
  valid_games: number;
  sample_size_win: number;
  sample_size_acpl: number;
};

export type AnalysisMetricRunSideResponse = {
  mean: number;
  ci_low: number;
  ci_high: number;
  confidence: number;
  sample_size: number;
};

export type AnalysisMetricResponse = {
  name: string;
  run_a: AnalysisMetricRunSideResponse;
  run_b: AnalysisMetricRunSideResponse;
  delta: number;
  ci_low: number;
  ci_high: number;
  p_value: number;
  effect_size: number;
  effect_size_name: string;
  effect_size_magnitude: string;
  significant: boolean;
};

export type AnalysisCompareResponse = {
  comparison_id: string;
  created_at_utc: string;
  runs: {
    a: AnalysisRunSampleResponse;
    b: AnalysisRunSampleResponse;
  };
  metrics: {
    win_rate: AnalysisMetricResponse;
    acpl?: AnalysisMetricResponse | null;
  };
  recommendation: string;
  confidence_note: string;
  notes: string[];
  artifacts: {
    comparison_dir: string;
    json_path: string;
    markdown_path: string;
  };
};
