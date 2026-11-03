import type { Feature, Polygon } from "geojson";
import type { StyleSpecification } from "maplibre-gl";

export type BBox = [number, number, number, number]; // west, south, east, north

/** Esri World Imagery basemap (check Esri's terms of use before production deployment). */
export const SATELLITE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    sat: {
      type: "raster", tileSize: 256, maxzoom: 18,
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      attribution: "Imagery © Esri, Maxar, Earthstar Geographics",
    },
  },
  layers: [{ id: "sat", type: "raster", source: "sat" }],
};

export function bboxPolygon([w, s, e, n]: BBox): Feature<Polygon> {
  return { type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] } };
}

/** Approximate side lengths in km (equirectangular). */
export function bboxSizeKm([w, s, e, n]: BBox): [number, number] {
  const lat = ((s + n) / 2) * (Math.PI / 180);
  return [(e - w) * 111.32 * Math.cos(lat), (n - s) * 110.57];
}

export function geometryBounds(geometry: Polygon): BBox {
  const pts = geometry.coordinates[0];
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}
