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
