"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type MetricsReport } from "../lib/api";

const MODEL_NAMES: Record<string, string> = {
  spectral_baseline: "Spectral baseline",
  random_forest: "Random Forest",
  siamese_unet: "Siamese U-Net",
};

export function ModelSnapshot() {
  const [report, setReport] = useState<MetricsReport | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    api.metrics()
      .then(setReport)
      .catch(() => setError(true));
  }, []);

  if (error) return null;
  if (!report) {
    return <p className="text-sm text-muted">Loading model evaluation…</p>;
  }

  const model = report.models[report.selected_model];
  if (!model) return null;

  const metrics: [string, number][] = [
    ["Test F1", model.test.f1],
    ["Precision", model.test.precision],
    ["Recall", model.test.recall],
    ["IoU", model.test.iou],
  ];

  return (
    <section className="rounded-3xl bg-sky/50 p-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-medium uppercase tracking-widest text-muted">
            Latest held-out evaluation
          </p>
          <h2 className="mt-2 font-display text-3xl">
            {MODEL_NAMES[report.selected_model] ?? report.selected_model}
          </h2>
          <p className="mt-1 text-sm text-muted">
            Selected using validation F1 · Evaluated {report.generated_at.slice(0, 10)}
          </p>
        </div>
        <Link href="/performance" className="btn-soft">
          Full evaluation →
        </Link>
      </div>

      <div className="mt-7 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {metrics.map(([label, value]) => (
          <div key={label} className="rounded-2xl bg-white/70 p-4">
            <p className="text-xs text-muted">{label}</p>
            <p className="mt-1 font-display text-3xl">
              {value.toFixed(3)}
            </p>
          </div>
        ))}
      </div>

      <p className="mt-5 text-xs text-muted">
        Scores measure agreement with Hansen reference labels on held-out sites,
        not field-verified accuracy. Results vary by location; see the limitations
        and per-site scores in the full evaluation.
      </p>
    </section>
  );
}
