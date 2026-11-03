"use client";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
import type { FeatureCollection, Polygon } from "geojson";
import { useEffect, useRef, useState } from "react";
import { api, type DetectionProps, type DetectionResult } from "@/lib/api";
import { geometryBounds, SATELLITE_STYLE } from "./map";

interface Props {
  runId: string; result: DetectionResult; detections: FeatureCollection<Polygon, DetectionProps>;
  blend: number; showChange: boolean; showOutlines: boolean; focusId: number | null;
}

/** Before/after composites and detections georeferenced on a satellite basemap. */
export function ResultMap({ runId, result, detections, blend, showChange, showOutlines, focusId }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    const corners = result.grid.corners_lonlat as [[number, number], [number, number], [number, number], [number, number]];
    const [w, s, e, n] = result.request.bbox;
    const map = new maplibregl.Map({ container: container.current!, style: SATELLITE_STYLE, bounds: [w, s, e, n], fitBoundsOptions: { padding: 40 }, attributionControl: { compact: true } });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl(), "bottom-left");
    map.on("load", () => {
      for (const name of ["before", "after", "change"] as const) {
        map.addSource(name, { type: "image", url: api.imageUrl(runId, name), coordinates: corners });
        map.addLayer({ id: name, type: "raster", source: name, paint: { "raster-opacity": name === "before" ? 1 : 0, "raster-fade-duration": 0 } });
      }
      map.addSource("detections", { type: "geojson", data: detections });
      map.addLayer({ id: "det-fill", type: "fill", source: "detections", paint: { "fill-color": "#FF7B6B", "fill-opacity": 0.08 } });
      map.addLayer({ id: "det-line", type: "line", source: "detections", paint: { "line-color": "#FBE9A6", "line-width": 2 } });
      map.on("click", "det-fill", (ev) => {
        const p = ev.features?.[0]?.properties as unknown as DetectionProps | undefined;
        if (!p) return;
        const conf = p.confidence == null ? "n/a (rule-based)" : p.confidence.toFixed(2);
        new maplibregl.Popup({ closeButton: false }).setLngLat(ev.lngLat)
          .setHTML(`<strong>#${p.id}</strong><br/>${p.area_ha} ha<br/>confidence ${conf}<br/>${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}`).addTo(map);
      });
      map.on("mouseenter", "det-fill", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "det-fill", () => (map.getCanvas().style.cursor = ""));
      setMapReady(true);
    });
    mapRef.current = map;
    return () => { setMapReady(false); map.remove(); };
  }, [runId, result, detections]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) return;
    map.setPaintProperty("after", "raster-opacity", blend);
    map.setPaintProperty("change", "raster-opacity", showChange ? 1 : 0);
    map.setLayoutProperty("det-line", "visibility", showOutlines ? "visible" : "none");
  }, [blend, showChange, showOutlines, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    const feature = detections.features.find((f) => f.properties.id === focusId);
    if (map && feature) map.fitBounds(geometryBounds(feature.geometry), { padding: 80, maxZoom: 17 });
  }, [focusId, detections]);

  return <div ref={container} className="h-[520px] w-full overflow-hidden rounded-3xl border border-line" />;
}
