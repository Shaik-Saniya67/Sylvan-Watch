"use client";
import { motion, useInView, useReducedMotion } from "framer-motion";
import { useRef } from "react";

const STAGES = [
  "Sentinel-2 L2A", "Cloud & shadow mask", "Seasonal composites", "Spectral features", "Trained detector", "Polygons & area",
];

/**
 * Adapted from NullMotion "09-grid-network" (MIT): a hub with nodes on a ring; links fade in staggered,
 * nodes pop with a spring and the hub pulses. Nodes here are the real processing stages of the pipeline.
 */
export function NodePipeline() {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true, margin: "-10% 0px" });
  const reduce = useReducedMotion();
  const cx = 260, cy = 220, R = 150;
  const nodes = STAGES.map((label, i) => {
    const a = ((-90 + i * (360 / STAGES.length)) * Math.PI) / 180;
    return { label, x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
  });
  const fills = ["#CFE5F5", "#DCD3F2", "#CDEBDD", "#FBE9A6", "#FFD9C2", "#CDEBDD"];
  return (
    <svg ref={ref} viewBox="0 0 520 440" className="mx-auto w-full max-w-xl" role="img" aria-label="Processing pipeline">
      {nodes.map((n, i) => (
        <motion.line key={`l${i}`} x1={cx} y1={cy} x2={n.x} y2={n.y} stroke="#33403A" strokeOpacity={0.35} strokeDasharray="3 5"
          initial={reduce ? false : { opacity: 0 }} animate={inView ? { opacity: 1 } : undefined} transition={{ delay: 0.7 + i * 0.12, duration: 0.5 }} />
      ))}
      <motion.circle cx={cx} cy={cy} r={42} fill="#FF7B6B"
        initial={reduce ? false : { scale: 0 }} animate={inView ? { scale: [0, 1, 1.07, 1] } : undefined}
        transition={{ duration: 1.6, delay: 0.3, times: [0, 0.4, 0.7, 1] }} style={{ transformOrigin: `${cx}px ${cy}px` }} />
      <text x={cx} y={cy - 2} textAnchor="middle" fontSize="12" fontWeight="600" fill="#fff">Forest-loss</text>
      <text x={cx} y={cy + 14} textAnchor="middle" fontSize="12" fontWeight="600" fill="#fff">detection</text>
      {nodes.map((n, i) => (
        <motion.g key={n.label} initial={reduce ? false : { scale: 0, opacity: 0 }} animate={inView ? { scale: 1, opacity: 1 } : undefined}
          transition={{ type: "spring", stiffness: 240, damping: 14, delay: 0.7 + i * 0.12 }} style={{ transformOrigin: `${n.x}px ${n.y}px` }}>
          <rect x={n.x - 58} y={n.y - 17} width={116} height={34} rx={17} fill={fills[i]} stroke="#E8DFCC" />
          <text x={n.x} y={n.y + 4} textAnchor="middle" fontSize="11" fontWeight="500" fill="#33403A">{n.label}</text>
        </motion.g>
      ))}
    </svg>
  );
}
