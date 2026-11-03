"use client";
import { useEffect, useState } from "react";
import { ConfusionMatrix } from "@/components/ConfusionMatrix";
import { LineDraw } from "@/components/motion/LineDraw";
import { api, ApiError, type MetricsReport } from "@/lib/api";

const NAMES: Record<string, string> = { spectral_baseline: "Spectral baseline", random_forest: "Random Forest", siamese_unet: "Siamese U-Net" };
const pct = (v: number | null | undefined) => (v == null ? "—" : v.toFixed(3));

export default function Performance() {
  const [report, setReport] = useState<MetricsReport | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [focus, setFocus] = useState<string | null>(null);

  useEffect(() => {
    api.metrics().then((r) => { setReport(r); setFocus(r.selected_model); }).catch(setError);
  }, []);

  if (error) {
    return (
      <div className="mx-auto max-w-2xl px-5 py-12">
        <h1 className="font-display text-3xl">Model performance</h1>
        <p className="mt-4 rounded-2xl bg-butter/70 p-5" role="alert">
          {error.status === 404 ? "No evaluation has been run yet, so there are no metrics to show. " : ""}{error.message}
        </p>
      </div>
    );
  }
  if (!report) return <p className="mx-auto max-w-3xl p-8 text-muted">Loading…</p>;

  const names = Object.keys(report.models);
  const current = focus ? report.models[focus] : null;
  const history = report.training_history?.history ?? [];
  return (
    <div className="mx-auto max-w-6xl space-y-8 px-5 py-8">
      <div>
        <h1 className="font-display text-3xl">Model performance</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted">{report.label_source}. Generated {report.generated_at}. {report.selection_criterion}</p>
      </div>

      <section className="card overflow-x-auto p-0">
        <table className="w-full text-sm">
          <thead className="bg-butter/50 text-left text-xs uppercase tracking-wider text-muted">
            <tr><th className="p-3">Model</th><th>Precision</th><th>Recall</th><th>F1</th><th>F1 95% CI</th><th>IoU</th><th>Val F1</th><th>ECE</th><th /></tr>
          </thead>
          <tbody>
            {names.map((n) => {
              const m = report.models[n]; const ci = m.test.f1_ci95_tile_bootstrap;
              return (
                <tr key={n} className={`border-t border-line ${focus === n ? "bg-mint/40" : ""}`}>
                  <td className="p-3 font-medium">{NAMES[n] ?? n}{n === report.selected_model && <span className="ml-2 rounded-full bg-coral px-2 py-0.5 text-xs text-white">selected</span>}</td>
                  <td>{pct(m.test.precision)}</td><td>{pct(m.test.recall)}</td><td>{pct(m.test.f1)}</td>
                  <td>{ci && ci[0] != null ? `${pct(ci[0])}–${pct(ci[1])}` : "—"}</td><td>{pct(m.test.iou)}</td>
                  <td>{pct(m.validation.f1)}</td><td>{pct(m.calibration?.ece)}</td>
                  <td className="pr-3 text-right"><button className="btn-soft !px-3 !py-1" onClick={() => setFocus(n)}>Inspect</button></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="border-t border-line p-3 text-xs text-muted">Test metrics on held-out sites; thresholds chosen on validation sites. Pixels outside forest or under cloud are excluded.</p>
      </section>

      {current && focus && (
        <section className="grid gap-6 md:grid-cols-2">
          <div className="card">
            <h2 className="font-display text-xl">{NAMES[focus] ?? focus}: test confusion matrix</h2>
            <p className="mb-3 text-xs text-muted">Decision threshold {current.threshold}. Loss pixels: {current.test.support.loss_pixels.toLocaleString()}, stable: {current.test.support.stable_pixels.toLocaleString()}.</p>
            <ConfusionMatrix matrix={current.test.confusion_matrix} />
            <h3 className="mt-5 text-xs font-medium uppercase tracking-wider text-muted">Class-wise</h3>
            <table className="mt-1 w-full text-sm"><tbody>
              {(["loss", "stable"] as const).map((c) => (
                <tr key={c}><td className="py-1 capitalize">{c}</td><td>P {pct(current.test.classwise[c].precision)}</td><td>R {pct(current.test.classwise[c].recall)}</td><td>IoU {pct(current.test.classwise[c].iou)}</td></tr>
              ))}
            </tbody></table>
          </div>
          <div className="card">
            <h2 className="font-display text-xl">Per test site</h2>
            <table className="mt-3 w-full text-sm">
              <thead className="text-left text-xs uppercase tracking-wider text-muted"><tr><th>Site</th><th>P</th><th>R</th><th>F1</th><th>Loss px</th></tr></thead>
              <tbody>{Object.entries(current.per_site_test).map(([site, s]) => (
                <tr key={site} className="border-t border-line"><td className="py-1.5">{site}</td><td>{pct(s.precision)}</td><td>{pct(s.recall)}</td><td>{pct(s.f1)}</td><td>{s.support.loss_pixels.toLocaleString()}</td></tr>
              ))}</tbody>
            </table>
            {current.independent_reference
              ? <p className="mt-4 rounded-xl bg-lavender/60 p-3 text-sm">Independent reference polygons: F1 {pct(current.independent_reference.f1)}, precision {pct(current.independent_reference.precision)}, recall {pct(current.independent_reference.recall)}.</p>
              : <p className="mt-4 rounded-xl bg-peach/60 p-3 text-sm">No independent reference polygons were supplied, so all figures measure agreement with Hansen labels only.</p>}
          </div>
        </section>
      )}

      <section className="grid gap-6 md:grid-cols-2">
        <div className="card">
          <h2 className="font-display text-xl">Datasets and split</h2>
          <p className="mb-3 text-xs text-muted">{report.split_strategy}</p>
          <table className="w-full text-sm"><thead className="text-left text-xs uppercase tracking-wider text-muted"><tr><th>Split</th><th>Sites</th><th>Tiles</th><th>Loss rate</th></tr></thead>
            <tbody>{(["train", "val", "test"] as const).map((k) => { const s = report.splits[k]; return (
              <tr key={k} className="border-t border-line"><td className="py-1.5">{k}</td><td>{s.sites.join(", ")}</td><td>{s.tiles}</td><td>{s.loss_rate == null ? "—" : `${(100 * s.loss_rate).toFixed(2)}%`}</td></tr>); })}</tbody></table>
          <ul className="mt-3 space-y-0.5 text-xs text-muted">{Object.entries(report.datasets).map(([k, v]) => <li key={k}>{k}: {String(v)}</li>)}</ul>
        </div>
        <div className="card">
          <h2 className="font-display text-xl">Siamese U-Net training</h2>
          {history.length > 1 ? (
            <>
              <LineDraw yLabel="value" series={[
                { label: "validation F1", values: history.map((h) => h.val_f1), color: "#FF7B6B" },
                { label: "training loss", values: history.map((h) => h.train_loss), color: "#8E7CC3" },
              ]} />
              <p className="mt-2 text-xs text-muted">seed {report.training_history?.seed} · device {report.training_history?.device} · positive class weight {report.training_history?.pos_weight.toFixed(1)}</p>
            </>
          ) : <p className="text-sm text-muted">No Siamese U-Net training history was recorded.</p>}
        </div>
      </section>

      <section className="rounded-3xl bg-peach/60 p-6">
        <h2 className="font-display text-xl">Limitations</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{report.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
      </section>
    </div>
  );
}
