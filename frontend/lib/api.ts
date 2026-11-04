import type { FeatureCollection, Polygon } from "geojson";

/** Typed client for the Sylvan Watch FastAPI backend. */
export const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://sylvan-watch-api.onrender.com";

export type ModelChoice = "best" | "spectral_baseline" | "random_forest" | "siamese_unet";

export interface Health { status: string; models_available: string[]; models_known: string[]; evaluated: boolean }

export interface DetectionRequestBody {
  west: number; south: number; east: number; north: number;
  before_year: number; after_year: number;
  season_start_month: number; season_end_month: number; model: ModelChoice;
}

export interface RunStatus {
  id: string; state: "queued" | "running" | "done" | "failed"; stage: string; progress: number;
  created_at: string; updated_at: string; error?: string;
  result?: DetectionResult; detections?: FeatureCollection<Polygon, DetectionProps>;
  summary?: DetectionResult["summary"]; request?: DetectionResult["request"]; model?: string;
}

export interface DetectionProps {
  id: number; area_ha: number; confidence: number | null; landcover: string | null; lon: number; lat: number;
}

export interface DetectionResult {
  request: { bbox: [number, number, number, number]; before_year: number; after_year: number; season_months: [number, number]; model_requested: string };
  model: { name: string; calibrated_probability: boolean; evaluated: boolean; threshold?: number; test_f1?: number; test_precision?: number; test_recall?: number; test_iou?: number; note?: string };
  datasets: Record<string, string | number>;
  grid: { epsg: number; height: number; width: number; pixel_size_m: number; corners_lonlat: [number, number][] };
  summary: { detections: number; loss_area_ha: number; forest_area_ha: number; loss_percent_of_forest: number; loss_area_by_landcover_ha: Record<string, number> };
  data_quality: { cloud_free_coverage_percent: number; min_detection_ha: number; tiles: number };
  notes: string[]; runtime_seconds: number;
}

export interface Scores {
  precision: number; recall: number; f1: number; iou: number; mean_iou: number; accuracy: number;
  confusion_matrix: number[][]; support: { loss_pixels: number; stable_pixels: number };
  classwise: Record<"loss" | "stable", { precision: number; recall: number; iou: number }>;
  f1_ci95_tile_bootstrap?: [number | null, number | null];
}

export interface ModelReport {
  threshold: number; validation: Scores; test: Scores; per_site_test: Record<string, Scores>;
  calibration: { brier: number | null; ece: number | null } | null; independent_reference: Scores | null;
}

export interface SplitSummary { tiles: number; sites: string[]; forest_pixels: number; loss_pixels: number; loss_rate: number | null }

export interface MetricsReport {
  generated_at: string; label_source: string; datasets: Record<string, string | number>;
  splits: Record<"train" | "val" | "test", SplitSummary>; split_strategy: string;
  models: Record<string, ModelReport>; selected_model: string; selection_criterion: string;
  training_history: { history: { epoch: number; train_loss: number; val_f1: number }[]; best_val_f1: number; pos_weight: number; seed: number; device: string } | null;
  caveats: string[];
}

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError(`Cannot reach the API at ${API_URL}. Is the backend running?`, 0);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail ?? response.statusText), response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/api/health"),
  metrics: () => request<MetricsReport>("/api/metrics"),
  createDetection: (body: DetectionRequestBody) =>
    request<{ id: string }>("/api/detections", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  getDetection: (id: string) => request<RunStatus>(`/api/detections/${id}`),
  listDetections: () => request<RunStatus[]>("/api/detections"),
  imageUrl: (id: string, name: "before" | "after" | "change") => `${API_URL}/api/detections/${id}/images/${name}.png`,
reportUrl: (id: string, format: "md" | "geojson" | "pdf") => `${API_URL}/api/detections/${id}/report?format=${format}`,
};
