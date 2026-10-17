// Mirrors app/server/src/svo_api/schemas.py. Keep field names identical.

export type Decision = 'high_risk' | 'review' | 'low_risk';
export type ReviewStatus = 'pending' | 'confirmed' | 'rejected';

export interface PredictionRequest {
  text: string;
  event_id: string;
}

export interface Prediction {
  event_id: string;
  scam_score: number;
  decision: Decision;
  needs_review: boolean;
  novelty_score: number;
  is_unknown: boolean;
  nearest_known_family_or_null: string | null;
  cluster_id_or_null: number | null;
  model_version: string;
  reference_version: string;
  scope: string;
  cluster_capacity_reached: boolean;
}

export interface ReviewRequest {
  review_id: string;
  status: ReviewStatus;
  actor?: string;
}

export interface ReviewResult {
  review_id: string;
  cluster_id: number;
  status: ReviewStatus;
  actor: string;
  actor_verified: boolean;
  automatic_retraining: false;
  model_version: string;
}

export interface Cluster {
  cluster_id: number;
  unique_text_count: number;
  report_count: number;
  first_seq: number;
  last_seq: number;
  status: ReviewStatus;
  mean_novelty: number;
  candidate_variant: boolean;
  model_version: string;
}

export interface ClusterDetail extends Cluster {
  representative_event_ids: string[];
}

export interface Page<T> {
  items: T[];
  next_after_id: number | null;
}

export interface ReviewAudit {
  id: number;
  cluster_id: number;
  status: ReviewStatus;
  actor: string;
  created: number;
  model_version: string;
  review_id: string | null;
  actor_verified: boolean;
}

export interface Window {
  end_seq: number;
  unknown_fraction: number;
  review_fraction: number;
  score_mean: number;
  alert: boolean;
}

export interface Monitoring {
  model_version: string;
  monitoring: string;
  latest_window: Window | null;
  event_count: number;
  cluster_count: number;
  pending_count: number;
  candidate_count: number;
  disk_free_bytes: number;
  schema_version: number;
}

export interface DecisionConfig {
  window_size: number;
  window_stride: number;
  consecutive_windows: number;
  min_cluster_unique: number;
  max_clusters: number;
  low_risk_threshold: number;
  high_risk_threshold: number;
  novelty_threshold: number;
  drift_unknown_threshold: number;
  cluster_similarity: number;
  scope: string;
  scores_calibrated: boolean;
  monitor_representation: string;
  window_mode: string;
  [key: string]: unknown;
}

export interface ModelInfo {
  model_version: string;
  reference_version: string;
  representation: string;
  scope: string;
  scores_calibrated: boolean;
  mode: 'local_demo' | 'authenticated';
  decision_config: DecisionConfig;
  limitations: string[];
}

export interface Ready {
  status: 'ready';
  model_version: string;
}

export interface ErrorEnvelope {
  error: { code: string; message: string; request_id: string };
}
