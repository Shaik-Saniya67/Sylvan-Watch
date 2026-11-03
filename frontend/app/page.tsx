import Link from "next/link";
import { BlurReveal } from "@/components/motion/BlurReveal";
import { KineticHeadline } from "@/components/motion/KineticHeadline";
import { NodePipeline } from "@/components/motion/NodePipeline";
import { ModelSnapshot } from "@/components/ModelSnapshot";

const CAN = [
  ["Real imagery, no mock-ups", "Sentinel-2 surface reflectance fetched live from Earth Engine for the area you draw."],
  ["Three detectors, one test set", "A spectral rule, a Random Forest and a Siamese U-Net are scored on the same held-out sites."],
  ["Hectares and coordinates", "Each loss patch becomes a polygon with area, centroid, confidence and land-cover context."],
];

export default function Home() {
  return (
    <>
      <section className="relative overflow-hidden">
        <div aria-hidden className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-lavender/70 blur-3xl" />
        <div aria-hidden className="absolute -left-24 top-40 h-80 w-80 rounded-full bg-butter/70 blur-3xl" />
        <div className="relative mx-auto max-w-6xl px-5 pb-20 pt-20 sm:pt-28">
          <p className="mb-5 inline-block rounded-full bg-sky px-4 py-1 text-xs font-medium uppercase tracking-widest">Neural Storm 2026 · GP-04</p>
          <KineticHeadline left="Forest loss," pill="measured" right="from orbit." />
          <p className="mt-8 max-w-xl text-lg text-muted">
            Sylvan Watch compares real Sentinel-2 imagery across years, finds where canopy disappeared, measures how many hectares,
            and evaluates model predictions against Hansen reference labels.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/workspace" className="btn-primary">Open the workspace</Link>
            <Link href="/performance" className="btn-soft">See the validation</Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-5 py-12">
        <ModelSnapshot />
      </section>

      <section className="bg-mint/40 py-20">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-5 md:grid-cols-2">
          <BlurReveal>
            <h2 className="font-display text-4xl">From pixels to polygons</h2>
            <p className="mt-4 text-muted">Every stage runs on real data: cloud masking, seasonal composites, 27 spectral and temporal features, a trained detector, and georeferenced vectorisation.</p>
          </BlurReveal>
          <NodePipeline />
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-10 px-5 py-20 md:grid-cols-[1.1fr_1fr]">
        <div className="space-y-8">
          {CAN.map(([title, text], i) => (
            <BlurReveal key={title} delay={i * 0.1}>
              <h3 className="font-display text-2xl">{title}</h3><p className="mt-1 text-muted">{text}</p>
            </BlurReveal>
          ))}
        </div>
        <BlurReveal delay={0.2} className="rounded-3xl bg-peach/70 p-8">
          <h3 className="font-display text-2xl">What it does not claim</h3>
          <ul className="mt-3 list-disc space-y-2 pl-5 text-sm">
            <li>It cannot tell whether clearing was legal; imagery shows loss, not permits.</li>
            <li>Hansen labels are a reference product, not field truth, and every metric says so.</li>
            <li>Selective logging of single trees is below 10 m resolution.</li>
            <li>Accuracy is reported for the evaluated sites only, never worldwide.</li>
          </ul>
          <Link href="/about" className="mt-5 inline-block underline">Read the methodology</Link>
        </BlurReveal>
      </section>
    </>
  );
}
