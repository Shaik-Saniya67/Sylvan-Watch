import { BlurReveal } from "@/components/motion/BlurReveal";

const SOURCES = [
  ["Sentinel-2 Level-2A", "Copernicus surface reflectance, accessed via Google Earth Engine (COPERNICUS/S2_SR_HARMONIZED).", "https://dataspace.copernicus.eu/"],
  ["Hansen Global Forest Change", "Landsat-derived tree cover (2000) and annual loss year, University of Maryland / GLAD.", "https://glad.earthengine.app/view/global-forest-change"],
  ["ESA WorldCover", "10 m land-cover map; used for context, never as the loss label.", "https://worldcover2021.esa.int/"],
];

const STEPS = [
  ["1. Acquire", "For each tile of the chosen area, Earth Engine builds a median of cloud-masked Sentinel-2 scenes for the before season and the after season. Clouds, shadows, cirrus, saturation and snow are removed using the scene classification layer (SCL); every pixel keeps a count of clear observations."],
  ["2. Define forest", "Only pixels that were forest at the before date are scanned: canopy ≥ 30% in 2000 and no Hansen loss up to the before year."],
  ["3. Features", "Six reflectance bands per date, their differences, and NDVI, NBR and NDMI at both dates with their differences (27 features per pixel)."],
  ["4. Three detectors", "A spectral-index rule (dNBR and dNDVI thresholds fitted on training sites), a Random Forest on the 27 features, and a Siamese U-Net whose weight-shared encoder compares before and after at every scale. Loss: weighted cross-entropy plus Dice, computed over forest pixels only."],
  ["5. Validate", "Whole sites are assigned to train, validation or test, so no test pixel neighbours a training pixel. Thresholds are chosen on validation sites. Precision, recall, F1, IoU, confusion matrices, a tile-bootstrap interval for F1 and calibration error are reported on test sites. The shown model is chosen by validation F1."],
  ["6. Vectorise", "Predicted loss pixels become 8-connected polygons; area is computed in a projected UTM grid at 10 m; each polygon gets a mean model probability and the dominant land-cover class."],
];

const LIMITS = [
  "Hansen labels are a satellite-derived reference, not field truth. Reported accuracy is agreement with that product unless independent reference polygons were supplied.",
  "Optical imagery shows that canopy disappeared, not whether the clearing was legal. Any 'illegal' claim needs boundary and permit data that this system does not hold.",
  "Plantation harvest, fire and flooding can look like deforestation; WorldCover context helps triage but does not remove them.",
  "Selective logging and poaching of individual trees are below 10 m resolution and are not detected.",
  "Results hold for the evaluated sites, seasons and years. No worldwide generalisation is claimed.",
];

export default function About() {
  return (
    <div className="mx-auto max-w-4xl space-y-12 px-5 py-10">
      <BlurReveal><h1 className="font-display text-4xl">Methodology</h1>
        <p className="mt-2 text-muted">Where the data comes from, how detections are produced, and what they cannot tell you.</p></BlurReveal>
      <section>
        <h2 className="font-display text-2xl">Data sources</h2>
        <ul className="mt-3 space-y-3">{SOURCES.map(([name, text, href]) => (
          <li key={name} className="rounded-2xl bg-sky/50 p-4"><a className="font-medium underline" href={href} target="_blank" rel="noreferrer">{name}</a><p className="text-sm">{text}</p></li>))}</ul>
      </section>
      <section>
        <h2 className="font-display text-2xl">Processing</h2>
        <ol className="mt-3 space-y-3">{STEPS.map(([t, d]) => <li key={t} className="rounded-2xl bg-mint/50 p-4"><strong>{t}</strong> <span className="text-sm">{d}</span></li>)}</ol>
      </section>
      <section className="rounded-3xl bg-peach/60 p-6">
        <h2 className="font-display text-2xl">Scientific limitations</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm">{LIMITS.map((l) => <li key={l}>{l}</li>)}</ul>
      </section>
      <section className="text-sm text-muted">
        <h2 className="font-display text-xl text-ink">Credits</h2>
        <p className="mt-2">Motion patterns (blur reveal, kinetic headline, line draw, node network) are adapted from the MIT-licensed NullMotion project by blixvip and contributors, re-implemented with Framer Motion.</p>
      </section>
    </div>
  );
}
