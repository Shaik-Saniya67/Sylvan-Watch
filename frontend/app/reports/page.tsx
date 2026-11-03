"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type RunStatus } from "../../lib/api";

export default function Reports() {
  const [runs, setRuns] = useState<RunStatus[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listDetections()
      .then(setRuns)
      .catch((e: Error) => setError(e.message));
  }, []);

  return (
    <div className="mx-auto max-w-4xl px-5 py-8">
      <h1 className="font-display text-3xl">Reports</h1>

      <p className="mt-1 text-sm text-muted">
        Every completed run provides a Markdown report, a PDF report, and a
        GeoJSON file containing the spatial detections.
      </p>

      {error && (
        <p className="mt-6 rounded-xl bg-peach/70 p-4 text-sm" role="alert">
          {error}
        </p>
      )}

      {runs && runs.length === 0 && (
        <p className="mt-6 rounded-xl bg-butter/60 p-4 text-sm">
          No runs yet.{" "}
          <Link href="/workspace" className="underline">
            Start one in the workspace.
          </Link>
        </p>
      )}

      <ul className="mt-6 space-y-3">
        {runs?.map((r) => (
          <li
            key={r.id}
            className="card flex flex-wrap items-center justify-between gap-3 !p-4"
          >
            <div>
              <p className="font-medium">
                Run {r.id}
                <span
                  className={`ml-2 rounded-full px-2 py-0.5 text-xs ${
                    r.state === "done"
                      ? "bg-mint"
                      : r.state === "failed"
                        ? "bg-peach"
                        : "bg-butter"
                  }`}
                >
                  {r.state}
                </span>
              </p>

              <p className="text-xs text-muted">
                {r.created_at}
                {r.request
                  ? ` · ${r.request.before_year} → ${r.request.after_year} · ${r.model}`
                  : ""}
                {r.summary
                  ? ` · ${r.summary.loss_area_ha} ha lost in ${r.summary.detections} patches`
                  : ""}
                {r.error ? ` · ${r.error}` : ""}
              </p>
            </div>

            {r.state === "done" && (
              <div className="flex flex-wrap gap-2">
                <Link className="btn-soft" href={`/analysis/${r.id}`}>
                  Open
                </Link>

                <a
                  className="btn-soft"
                  href={api.reportUrl(r.id, "md")}
                >
                  Markdown
                </a>

                <a
                  className="btn-soft"
                  href={api.reportUrl(r.id, "pdf")}
                >
                  PDF Report
                </a>

                <a
                  className="btn-soft"
                  href={api.reportUrl(r.id, "geojson")}
                >
                  GeoJSON
                </a>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
