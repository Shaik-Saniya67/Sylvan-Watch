"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ResultMap } from "@/components/ResultMap";
import { StageProgress } from "@/components/StageProgress";
import { api, type RunStatus } from "@/lib/api";

export default function Analysis() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<RunStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [blend, setBlend] = useState(0);
  const [showChange, setShowChange] = useState(true);
  const [showOutlines, setShowOutlines] = useState(true);
  const [focusId, setFocusId] = useState<number | null>(null);

  useEffect(() => {
    let stop = false;
    const poll = async () => {
      try {
        const status = await api.getDetection(id);
        if (stop) return;
        setRun(status);
        if (status.state === "queued" || status.state === "running") setTimeout(poll, 2000);
      } catch (e) { if (!stop) setError((e as Error).message); }
    };
    poll();
    return () => { stop = true; };
  }, [id]);

  if (error) return <p className="mx-auto max-w-3xl p-8" role="alert">{error}</p>;
  if (!run) return <p className="mx-auto max-w-3xl p-8 text-muted">Loading…</p>;
  if (run.state === "failed") return <p className="mx-auto max-w-3xl p-8" role="alert"><strong>This run failed.</strong> {run.error}</p>;
  if (run.state !== "done" || !run.result || !run.detections) {
    return <div className="mx-auto max-w-xl p-8"><StageProgress stage={run.stage} progress={run.progress} /></div>;
  }

  const { result, detections } = run;
  const s = result.summary;
  return (
    <div className="mx-auto max-w-6xl space-y-6 px-5 py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl">Change analysis</h1>
          <p className="text-sm text-muted">{result.request.before_year} → {result.request.after_year} · model {result.model.name} · run {id}</p>
        </div>
        <div className="flex gap-2">
          <a className="btn-soft" href={api.reportUrl(id, "md")}>Report (.md)</a>
          <a className="btn-soft" href={api.reportUrl(id, "geojson")}>GeoJSON</a>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-3xl bg-coral/90 p-6 text-white"><p className="text-sm opacity-90">Estimated forest-cover loss</p><p className="font-display text-5xl">{s.loss_area_ha}<span className="text-xl"> ha</span></p></div>
        <div className="rounded-3xl bg-mint p-6"><p className="text-sm text-muted">Detected patches</p><p className="font-display text-5xl">{s.detections}</p><p className="text-xs text-muted">≥ {result.data_quality.min_detection_ha} ha each</p></div>
        <div className="rounded-3xl bg-sky p-6"><p className="text-sm text-muted">Share of scanned forest</p><p className="font-display text-5xl">{s.loss_percent_of_forest}<span className="text-xl">%</span></p><p className="text-xs text-muted">{s.forest_area_ha} ha scanned · {result.data_quality.cloud_free_coverage_percent}% cloud-free</p></div>
      </div>

      <ResultMap runId={id} result={result} detections={detections} blend={blend} showChange={showChange} showOutlines={showOutlines} focusId={focusId} />

      <div className="card flex flex-wrap items-center gap-x-8 gap-y-3">
        <label className="flex flex-1 items-center gap-3 text-sm">
          <span className="w-24 shrink-0">Before {result.request.before_year}</span>
          <input type="range" min={0} max={1} step={0.01} value={blend} onChange={(e) => setBlend(+e.target.value)} className="w-full accent-coral" aria-label="Blend between before and after imagery" />
          <span className="w-24 shrink-0 text-right">After {result.request.after_year}</span>
        </label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showChange} onChange={(e) => setShowChange(e.target.checked)} className="accent-coral" /> Loss pixels</label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={showOutlines} onChange={(e) => setShowOutlines(e.target.checked)} className="accent-coral" /> Outlines</label>
      </div>

      <section className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <div className="card overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="bg-butter/50 text-left text-xs uppercase tracking-wider text-muted">
              <tr><th className="p-3">#</th><th>Lat</th><th>Lon</th><th>Area (ha)</th><th>Confidence</th><th>Land cover 2021</th></tr>
            </thead>
            <tbody>
              {detections.features.slice(0, 50).map((f) => (
                <tr key={f.properties.id} onClick={() => setFocusId(f.properties.id)} className="cursor-pointer border-t border-line hover:bg-mint/40">
                  <td className="p-3">{f.properties.id}</td><td>{f.properties.lat.toFixed(5)}</td><td>{f.properties.lon.toFixed(5)}</td>
                  <td>{f.properties.area_ha}</td><td>{f.properties.confidence == null ? "n/a" : f.properties.confidence.toFixed(2)}</td><td>{f.properties.landcover}</td>
                </tr>
              ))}
              {detections.features.length === 0 && <tr><td colSpan={6} className="p-6 text-center text-muted">No loss patches above the size threshold were detected.</td></tr>}
            </tbody>
          </table>
        </div>
        <aside className="space-y-4 text-sm">
          <div className="rounded-3xl bg-lavender/70 p-5">
            <h2 className="font-display text-lg">How trustworthy is this model?</h2>
            {result.model.evaluated ? (
              <p className="mt-2">On held-out test sites: F1 {result.model.test_f1?.toFixed(2)}, precision {result.model.test_precision?.toFixed(2)}, recall {result.model.test_recall?.toFixed(2)}, IoU {result.model.test_iou?.toFixed(2)} — against Hansen reference labels, not field data. <Link href="/performance" className="underline">Details</Link></p>
            ) : <p className="mt-2">No evaluation is recorded for this model, so its accuracy is unknown.</p>}
          </div>
          <div className="rounded-3xl bg-peach/70 p-5">
            <h2 className="font-display text-lg">Read with care</h2>
            <ul className="mt-2 list-disc space-y-1 pl-4">{result.notes.map((n) => <li key={n}>{n}</li>)}</ul>
          </div>
        </aside>
      </section>
    </div>
  );
}
