import { motion } from "framer-motion";

const LABELS: Record<string, string> = {
  queued: "Queued", loading_model: "Loading trained model", authenticating: "Connecting to Earth Engine",
  fetching_imagery: "Downloading Sentinel-2, Hansen and WorldCover tiles", predicting: "Running the detector",
  vectorising: "Building polygons and measuring area", writing_outputs: "Writing previews and results", done: "Complete",
};

/** Shows the backend's real pipeline stage and progress (no simulated progress). */
export function StageProgress({ stage, progress }: { stage: string; progress: number }) {
  return (
    <div role="status" aria-live="polite">
      <div className="mb-2 flex justify-between text-sm">
        <span>{LABELS[stage] ?? stage}</span><span className="text-muted">{Math.round(progress * 100)}%</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-sky/60">
        <motion.div className="h-full rounded-full bg-coral" animate={{ width: `${progress * 100}%` }} transition={{ ease: "easeOut", duration: 0.5 }} />
      </div>
    </div>
  );
}
