# Sylvan Watch: satellite forest-loss detection

**Neural Storm 2026 · Problem statement GP-04 (Green Planet): Illegal Deforestation Detection**
Team: `<team name>` · Members: Shaik Saniya, `<add others>`

Sylvan Watch compares real Sentinel-2 imagery from two periods, detects where forest canopy disappeared,
measures the affected area in hectares, georeferences each loss patch, and reports how well each of three
models agrees with Hansen forest-loss reference data on **held-out sites**.

## Honest status (read first)

| Item | State |
|---|---|
| Backend logic: indices, labels, features, metrics, area, polygons, tiling, baseline, Random Forest, evaluation, reference-polygon validation, FastAPI, job runner | Implemented, **37 automated tests pass** (`pytest`) |
| Full pipeline `run_detection` (chip reading, Hansen forest domain, inference, tile stitching, polygons, area, PNG previews, report) | Tested end to end with a **stubbed download** that feeds synthetic tiles. Verifies wiring, not accuracy |
| Train → evaluate path (site-level split, validation-chosen threshold, bootstrap CI, calibration, reference polygons) | Tested on synthetic chips. Verifies protocol and JSON output, not accuracy |
| Frontend (6 pages) | `tsc` clean, `next build` succeeds, all pages return 200, API CORS and error paths checked with curl. **Not clicked through in a browser** |
| Earth Engine download (`sylvan/data/gee_client.py`) | **Not executed.** Needs your credentials. The tile-download parameters (`crs_transform` + `region`) follow the documented API but are unverified live |
| Siamese U-Net training and inference | Code written and shape-reviewed; its tests (`tests/test_siamese.py`) **have not run** because PyTorch could not be installed in the build sandbox. Run them first on your machine |
| Real training, real metrics | **Not done.** No real data was downloaded, so `storage/results/metrics.json` does not exist and the Performance page shows an explicit "not evaluated" state. No accuracy number is claimed anywhere |
| `configs/sites.json` | Candidate bounding boxes from memory, **unverified**. `scripts/fetch_chips.py` prints a loss-rate audit; adjust sites until each split has meaningful Hansen loss |
| PostgreSQL/PostGIS | **Not implemented.** Runs are persisted as files under `storage/runs/<id>/` |
| Deployment (`render.yaml`, Dockerfile, Vercel) | Written, **untested** |

## Architecture

```
frontend/ (Next.js 15, TypeScript, Tailwind 3, Framer Motion, MapLibre GL)
   └── REST ──> backend/sylvan/api (FastAPI)
                  ├── api/jobs.py          background runs + on-disk run registry
                  ├── pipeline/inference   fetch → predict → polygonise → save
                  ├── data/                Earth Engine client, chip GeoTIFF I/O
                  ├── geo/                 AOI, 10 m UTM tiling, pixel area, polygons
                  └── ml/                  indices, features, labels, 3 detectors, training, evaluation
```

Pages: Landing · Detection Workspace (draw area, dates, model, live progress) · Change Analysis (before/after blend,
loss overlay, polygons, table, coordinates) · Model Performance · Reports (Markdown + GeoJSON) · Methodology.

## Data and method

1. **Imagery.** Sentinel-2 L2A (`COPERNICUS/S2_SR_HARMONIZED`) via Earth Engine. Per period, a median of scenes in a
   season, after removing cloud, cloud shadow, cirrus, saturated and snow pixels with the SCL band. Bands B2, B3, B4,
   B8, B11, B12 at 10 m. Each pixel keeps a clear-observation count; pixels with none are excluded.
2. **Labels.** Hansen GFC (`treecover2000`, `lossyear`). Forest = canopy ≥ 30% in 2000 and not lost by the before-year.
   Loss = Hansen loss year in (before-year, after-year]. **Hansen is a Landsat-derived reference product, not field
   truth.** Metrics measure agreement with it.
3. **Context.** ESA WorldCover (2021) gives each detection a land-cover class (it reflects the post-clearing state).
4. **Detectors**, all compared on the same test sites:
   - *Spectral baseline*: dNBR and dNDVI thresholds, grid-searched on training chips.
   - *Random Forest*: 27 features (bands, differences, NDVI/NBR/NDMI at both dates and their differences), balanced class weights.
   - *Siamese U-Net*: shared encoder, `|f_before − f_after|` skip connections, weighted BCE + Dice over forest pixels only.
5. **Validation protocol.** Whole **sites** are assigned to train/val/test (no spatial neighbours across splits).
   Thresholds are chosen on validation sites; the shown model is chosen by validation F1; test sites are used once.
   Reported: precision, recall, F1, IoU, class-wise scores, confusion matrix, per-site scores, tile-bootstrap 95% CI of F1,
   Brier score and expected calibration error. Optional **independent reference polygons** (`--reference`) score only inside
   hand-digitised loss/stable polygons.
6. **Output.** Loss pixels → 8-connected polygons → area from the UTM pixel grid, centroid lon/lat, mean model probability.

## Setup

Requirements: Python 3.11+, Node 20+ (tested with Node 22), a Google Earth Engine account.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # then edit
earthengine authenticate        # or configure a service account in .env
pytest                          # 37 pass; test_siamese.py is skipped only if torch is missing
uvicorn sylvan.api.main:app --reload --port 8000     # API docs: http://localhost:8000/docs

# Frontend
cd ../frontend
cp .env.example .env.local
npm install
npm run dev                     # http://localhost:3000
```

### Earth Engine setup
Register a Cloud project for Earth Engine, set `SYLVAN_EE_PROJECT`, then `earthengine authenticate`. For servers, create a
service account, grant it Earth Engine access, and set `SYLVAN_EE_SERVICE_ACCOUNT` and `SYLVAN_EE_PRIVATE_KEY_FILE`.
If authentication fails the API returns the exact error and these instructions. It never substitutes other data.

## Reproduce training and evaluation

```bash
cd backend
python scripts/fetch_chips.py            # downloads real chips, prints a per-site loss-rate audit
python scripts/train.py                  # baseline + Random Forest + Siamese U-Net (seed 42)
python scripts/evaluate.py               # writes storage/results/metrics.json
python scripts/evaluate.py --reference my_polygons.geojson   # optional independent validation
```
Edit `configs/sites.json` first: confirm each site has meaningful Hansen loss, keep before/after seasons identical, and keep
train/val/test sites far apart. Chips are cached in `storage/chips/`, so the fetch is resumable. Weights, chips and results live
under `storage/` and are git-ignored; to deploy, copy `storage/models` and `storage/results` to the server.
Training is seeded; GPU runs may still differ slightly because some CUDA kernels are non-deterministic.

Independent reference file format: GeoJSON, WGS84, each feature with `properties.kind` = `"loss"` or `"stable"`. Trace 20–30
polygons on very-high-resolution imagery inside the **test** sites.

## API (full OpenAPI at `/docs`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness, trained models, whether an evaluation exists |
| GET | `/api/metrics` | evaluation report (404 with an explanation if none) |
| POST | `/api/detections` | queue a run (bbox ≤ 15 km/side, years ≥ 2018, one-calendar-year season) → `{id}` |
| GET | `/api/detections` · `/{id}` | list runs · status with real stage/progress and, when done, result + GeoJSON |
| GET | `/api/detections/{id}/images/{before\|after\|change}.png` | previews |
| GET | `/api/detections/{id}/report?format=md\|geojson` | downloadable report / detections |

## Motion (NullMotion)

The NullMotion repo is a library of GSAP video-ad scenes (fixed 1920×1080, dark theme), not reusable React components, so nothing
was copied. Four techniques were re-implemented with Framer Motion in `frontend/components/motion/`: blur-reveal with light sweep
(`12-blur-reveal`), kinetic headline with squash-and-spring pill (`22-kinetic-headline`), line draw (`16-line-growth`, used only
for the real training curve) and the hub-and-node network (`09-grid-network`, used for the real pipeline stages).
NullMotion is MIT-licensed; credited on the Methodology page.

## Deployment (untested)
Frontend: Vercel with `NEXT_PUBLIC_API_URL`. Backend: `render.yaml` / `backend/Dockerfile` on Render or Railway with a persistent disk
at `/data`, Earth Engine credentials as secrets, and `SYLVAN_CORS_ORIGINS` set to the Vercel URL. Cold start: the first run needs
trained weights on the disk. The map uses Esri World Imagery tiles: check Esri's terms before production use.

## Limitations
Hansen labels are not field truth; imagery cannot establish legality; plantation harvest and fire look like loss; selective logging is
below 10 m resolution; results are valid only for evaluated sites, seasons and years; the API runs one detection at a time.

## AI tools used
Claude (Anthropic) generated the code from the project specification; the author must review, run and validate it.






 
