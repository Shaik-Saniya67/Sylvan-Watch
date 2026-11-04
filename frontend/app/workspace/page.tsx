"use client";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { MapPicker } from "@/components/MapPicker";
import { bboxSizeKm, type BBox } from "@/components/map";
import { StageProgress } from "@/components/StageProgress";
import { api, ApiError, type Health, type ModelChoice, type RunStatus } from "../../lib/api";

const YEARS = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MAX_SIDE_KM = 15;
const MODEL_LABELS: Record<string, string> = { spectral_baseline: "Spectral index baseline", random_forest: "Random Forest", siamese_unet: "Siamese U-Net" };

export default function Workspace() {
  const router = useRouter();
  const [bbox, setBbox] = useState<BBox | null>(null);
  const [beforeYear, setBeforeYear] = useState(2019);
  const [afterYear, setAfterYear] = useState(2023);
  const [startMonth, setStartMonth] = useState(1);
  const [endMonth, setEndMonth] = useState(4);
  const [model, setModel] = useState<ModelChoice>("best");
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [run, setRun] = useState<RunStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch((e: ApiError) => setHealthError(e.message));
    return () => { if (timer.current) clearInterval(timer.current); };
  }, []);

  const size = bbox ? bboxSizeKm(bbox) : null;
  const tooBig = size ? Math.max(...size) > MAX_SIDE_KM : false;
  const invalidYears = afterYear <= beforeYear;
  const invalidSeason = endMonth < startMonth;
  const running = run?.state === "queued" || run?.state === "running";
  const canRun = !!bbox && !tooBig && !invalidYears && !invalidSeason && !running;

  function setCoord(index: number, raw: string) {
    const next = (bbox ?? [0, 0, 0, 0]).slice() as BBox;
    next[index] = Number(raw);
    setBbox(next);
  }

  async function start() {
    if (!bbox) return;
    if (timer.current) clearInterval(timer.current);
    setError(null);
    try {
      const { id } = await api.createDetection({
        west: bbox[0], south: bbox[1], east: bbox[2], north: bbox[3], before_year: beforeYear, after_year: afterYear,
        season_start_month: startMonth, season_end_month: endMonth, model,
      });
      setRun({ id, state: "queued", stage: "queued", progress: 0, created_at: "", updated_at: "" });
      timer.current = setInterval(async () => {
        try {
          const status = await api.getDetection(id);
          setRun(status);
          if (status.state === "done") { clearInterval(timer.current!); router.push(`/analysis/${id}`); }
          if (status.state === "failed") clearInterval(timer.current!);
        } catch (e) { clearInterval(timer.current!); setError((e as Error).message); }
      }, 2000);
    } catch (e) { setError((e as Error).message); }
  }

  const available = new Set(health?.models_available ?? []);
  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-5 py-8 lg:grid-cols-[380px_1fr]">
      <section className="space-y-5">
        <div>
          <h1 className="font-display text-3xl">Detection workspace</h1>
          <p className="mt-1 text-sm text-muted">Draw an area (up to {MAX_SIDE_KM} km per side), choose two periods, and run a trained model on real Sentinel-2 imagery.</p>
        </div>

        {healthError && <p className="rounded-xl bg-peach/60 p-3 text-sm" role="alert">{healthError}</p>}
        {health && health.models_available.length === 0 && (
          <p className="rounded-xl bg-butter/70 p-3 text-sm" role="alert">
            No trained model exists on the backend yet, so detection will fail. Fetch chips and run <code>scripts/train.py</code> first (see README).
          </p>
        )}

        <div className="card space-y-4">
          <div className="grid grid-cols-2 gap-3">
            {(["West", "South", "East", "North"] as const).map((name, i) => (
              <label key={name}><span className="label">{name}</span>
                <input className="field" type="number" step="0.0001" value={bbox ? Number(bbox[i].toFixed(5)) : ""} onChange={(e) => setCoord(i, e.target.value)} placeholder="draw on map" />
              </label>
            ))}
          </div>
          {size && <p className={`text-xs ${tooBig ? "text-coral" : "text-muted"}`}>Area ≈ {size[0].toFixed(1)} × {size[1].toFixed(1)} km{tooBig ? ` — exceeds the ${MAX_SIDE_KM} km limit` : ""}</p>}

          <div className="grid grid-cols-2 gap-3">
            <label><span className="label">Before (year)</span>
              <select className="field" value={beforeYear} onChange={(e) => setBeforeYear(+e.target.value)}>{YEARS.map((y) => <option key={y}>{y}</option>)}</select></label>
            <label><span className="label">After (year)</span>
              <select className="field" value={afterYear} onChange={(e) => setAfterYear(+e.target.value)}>{YEARS.map((y) => <option key={y}>{y}</option>)}</select></label>
            <label><span className="label">Season from</span>
              <select className="field" value={startMonth} onChange={(e) => setStartMonth(+e.target.value)}>{MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
            <label><span className="label">Season to</span>
              <select className="field" value={endMonth} onChange={(e) => setEndMonth(+e.target.value)}>{MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}</select></label>
          </div>
          {invalidYears && <p className="text-xs text-coral">The after-year must be later than the before-year.</p>}
          {invalidSeason && <p className="text-xs text-coral">The season must stay within one calendar year.</p>}
          <p className="text-xs text-muted">Use the same months for both periods and a cloud-poor season; mismatched seasons cause false positives.</p>

          <label><span className="label">Model</span>
            <select className="field" value={model} onChange={(e) => setModel(e.target.value as ModelChoice)}>
              <option value="best" disabled={!health?.evaluated}>Best on validation data{health?.evaluated ? "" : " (not evaluated yet)"}</option>
              {Object.entries(MODEL_LABELS).map(([key, label]) => (
                <option key={key} value={key} disabled={!available.has(key)}>{label}{available.has(key) ? "" : " (not trained)"}</option>
              ))}
            </select>
          </label>

          <button className="btn-primary w-full" disabled={!canRun} onClick={start}>{running ? "Running…" : "Run detection"}</button>
        </div>

        {run && running && <div className="card"><StageProgress stage={run.stage} progress={run.progress} /></div>}
        {run?.state === "failed" && <p className="rounded-xl bg-peach/70 p-4 text-sm" role="alert"><strong>Run failed.</strong> {run.error}</p>}
        {error && <p className="rounded-xl bg-peach/70 p-4 text-sm" role="alert">{error}</p>}
      </section>

      <MapPicker bbox={bbox} onChange={setBbox} />
    </div>
  );
}
