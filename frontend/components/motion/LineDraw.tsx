"use client";
import { motion, useInView, useReducedMotion } from "framer-motion";
import { useRef } from "react";

export interface LineSeries { label: string; values: number[]; color: string }

/**
 * Adapted from NullMotion "16-line-growth" (MIT): axes grow in, the curve draws along its length and
 * end markers pop. Used only for REAL series (e.g. the training history from metrics.json).
 */
export function LineDraw({ series, yLabel, xLabel = "epoch" }: { series: LineSeries[]; yLabel: string; xLabel?: string }) {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const W = 520, H = 220, P = { l: 44, r: 12, t: 12, b: 28 };
  const all = series.flatMap((s) => s.values);
  const n = Math.max(...series.map((s) => s.values.length));
  if (!all.length || n < 2) return <p className="text-sm text-muted">Not enough points to plot.</p>;
  const lo = Math.min(0, ...all), hi = Math.max(...all) || 1;
  const x = (i: number) => P.l + (i / (n - 1)) * (W - P.l - P.r);
  const y = (v: number) => H - P.b - ((v - lo) / (hi - lo || 1)) * (H - P.t - P.b);
  const path = (v: number[]) => v.map((val, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(val).toFixed(1)}`).join(" ");
  return (
    <div>
      <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`${yLabel} by ${xLabel}`}>
        {[0, 0.5, 1].map((t) => {
          const v = lo + t * (hi - lo);
          return (
            <g key={t}>
              <line x1={P.l} x2={W - P.r} y1={y(v)} y2={y(v)} stroke="#E8DFCC" />
              <text x={P.l - 6} y={y(v) + 4} textAnchor="end" fontSize="10" fill="#6B766F">{v.toFixed(2)}</text>
            </g>
          );
        })}
        <motion.line x1={P.l} x2={P.l} y1={P.t} y2={H - P.b} stroke="#33403A" initial={reduce ? false : { pathLength: 0 }} animate={inView ? { pathLength: 1 } : undefined} transition={{ duration: 0.5 }} />
        <motion.line x1={P.l} x2={W - P.r} y1={H - P.b} y2={H - P.b} stroke="#33403A" initial={reduce ? false : { pathLength: 0 }} animate={inView ? { pathLength: 1 } : undefined} transition={{ duration: 0.6, delay: 0.2 }} />
        {series.map((s, k) => (
          <g key={s.label}>
            <motion.path d={path(s.values)} fill="none" stroke={s.color} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round"
              initial={reduce ? false : { pathLength: 0 }} animate={inView ? { pathLength: 1 } : undefined}
              transition={{ duration: 1.6, delay: 0.6 + k * 0.2, ease: "easeInOut" }} />
            <motion.circle cx={x(s.values.length - 1)} cy={y(s.values[s.values.length - 1])} r={4.5} fill={s.color}
              initial={reduce ? false : { scale: 0 }} animate={inView ? { scale: 1 } : undefined}
              transition={{ type: "spring", stiffness: 300, damping: 12, delay: 2.1 + k * 0.2 }} />
          </g>
        ))}
        <text x={W / 2} y={H - 6} textAnchor="middle" fontSize="10" fill="#6B766F">{xLabel}</text>
      </svg>
      <div className="mt-1 flex gap-4 text-xs text-muted">
        {series.map((s) => (<span key={s.label} className="flex items-center gap-1.5"><i className="inline-block h-2 w-4 rounded-full" style={{ background: s.color }} />{s.label}</span>))}
      </div>
    </div>
  );
}
