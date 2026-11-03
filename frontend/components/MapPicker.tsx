"use client";
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
maplibregl.setWorkerUrl("/maplibre-gl-worker.mjs");
import { useEffect, useRef, useState } from "react";
import { bboxPolygon, SATELLITE_STYLE, type BBox } from "./map";

interface Props { bbox: BBox | null; onChange: (bbox: BBox) => void; center?: [number, number]; zoom?: number }

/** Satellite map with a click-and-drag rectangle tool for choosing the area of interest. */
export function MapPicker({ bbox, onChange, center = [79.3, 13.68], zoom = 9 }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [drawing, setDrawing] = useState(false);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    const map = new maplibregl.Map({ container: container.current!, style: SATELLITE_STYLE, center, zoom, attributionControl: { compact: true } });
    map.on("error", (e) => {
  console.error("SYLVAN MAP ERROR:", e.error);
});
    map.on("load", () => {
  console.log("SYLVAN MAP LOADED:", map.isStyleLoaded());
});

    map.on("styledata", () => {
  console.log("SYLVAN STYLE DATA RECEIVED");
});
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl(), "bottom-left");
    map.on("load", () => {
      map.addSource("aoi", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({ id: "aoi-fill", type: "fill", source: "aoi", paint: { "fill-color": "#FBE9A6", "fill-opacity": 0.25 } });
      map.addLayer({ id: "aoi-line", type: "line", source: "aoi", paint: { "line-color": "#FF7B6B", "line-width": 3 } });
    });
    mapRef.current = map;
    return () => map.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Reflect the current bbox (typed or drawn) on the map.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => (map.getSource("aoi") as maplibregl.GeoJSONSource | undefined)?.setData(
      bbox ? bboxPolygon(bbox) : { type: "FeatureCollection", features: [] });
    map.isStyleLoaded() ? apply() : map.once("load", apply);
  }, [bbox]);

  // Rectangle drawing: mouse and touch share the same handlers.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !drawing) return;
    let start: maplibregl.LngLat | null = null;
    const rect = (a: maplibregl.LngLat, b: maplibregl.LngLat): BBox =>
      [Math.min(a.lng, b.lng), Math.min(a.lat, b.lat), Math.max(a.lng, b.lng), Math.max(a.lat, b.lat)];
    const down = (e: maplibregl.MapMouseEvent | maplibregl.MapTouchEvent) => { start = e.lngLat; };
    const move = (e: maplibregl.MapMouseEvent | maplibregl.MapTouchEvent) => {
      if (start) (map.getSource("aoi") as maplibregl.GeoJSONSource).setData(bboxPolygon(rect(start, e.lngLat)));
    };
    const up = (e: maplibregl.MapMouseEvent | maplibregl.MapTouchEvent) => {
      if (start) onChangeRef.current(rect(start, e.lngLat));
      start = null;
      setDrawing(false);
    };
    map.dragPan.disable();
    map.getCanvas().style.cursor = "crosshair";
    map.on("mousedown", down); map.on("mousemove", move); map.on("mouseup", up);
    map.on("touchstart", down); map.on("touchmove", move); map.on("touchend", up);
    return () => {
      map.dragPan.enable();
      map.getCanvas().style.cursor = "";
      map.off("mousedown", down); map.off("mousemove", move); map.off("mouseup", up);
      map.off("touchstart", down); map.off("touchmove", move); map.off("touchend", up);
    };
  }, [drawing]);

  return (
    <div className="relative h-full min-h-[420px] overflow-hidden rounded-3xl border border-line">
      <div ref={container} className="absolute inset-0" />
      <button type="button" onClick={() => setDrawing((d) => !d)} className={`absolute left-3 top-3 z-10 ${drawing ? "btn-primary" : "btn-soft"}`}>
        {drawing ? "Drag on the map…" : "Draw area"}
      </button>
    </div>
  );
}
