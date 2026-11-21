// Czysty Leaflet (BSD-2) – bez react-leaflet (licencja Hippocratic, niezgodna z przeniesieniem praw na KOWR).
import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import type { HydrologyInfo, ParcelRef, TerrainInfo } from "../api/types";
import { KIND } from "./blocks/EnvViews";
import { emit, fmtDist, on } from "../lib/events";

export interface MapOverlays {
  terrain?: TerrainInfo | null; hydrology?: HydrologyInfo | null;
  places?: { title: string; geojson: GeoJSON.GeoJsonObject }[];   // miejsca z rekomendacji (raport)
}

export function ParcelMap(props: {
  parcel: ParcelRef | null; overlays?: MapOverlays; expandable?: boolean; onPick: (lon: number, lat: number) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const parcelLayer = useRef<L.GeoJSON | null>(null);
  const overlayGroup = useRef<L.LayerGroup | null>(null);
  const control = useRef<L.Control.Layers | null>(null);
  const waterLayers = useRef<Map<number, L.GeoJSON>>(new Map());
  const onPick = useRef(props.onPick);
  onPick.current = props.onPick;

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { tap: true } as L.MapOptions).setView([52.1, 19.4], 6);
    const osm = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap", maxZoom: 19 });
    const orto = L.tileLayer.wms("https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution", {
      layers: "Raster", format: "image/jpeg", attribution: "Ortofotomapa GUGiK", maxZoom: 19,
    });
    osm.addTo(m);
    // granice i numery działek – KIEG GUGiK (od dużych zoomów)
    const kieg = L.tileLayer.wms("https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow", {
      layers: "dzialki,numery_dzialek", format: "image/png", transparent: true, minZoom: 15, attribution: "GUGiK KIEG",
    }).addTo(m);
    control.current = L.control.layers({ "Mapa": osm, "Zdjęcie lotnicze": orto }, { "Granice działek": kieg }, { collapsed: true }).addTo(m);
    overlayGroup.current = L.layerGroup().addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => onPick.current(e.latlng.lng, e.latlng.lat));
    map.current = m;
    return () => { m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    parcelLayer.current?.remove();
    if (!props.parcel) return;
    parcelLayer.current = L.geoJSON(props.parcel.geometry as never, { style: { color: "#d4a017", weight: 3, fillOpacity: 0.08 } }).addTo(m);
    const [x1, y1, x2, y2] = props.parcel.bbox;
    m.fitBounds([[y1, x1], [y2, x2]], { padding: [40, 40], maxZoom: 17 });
  }, [props.parcel]);

  // warstwy z bloków: zagłębienia i linie spływu (teren), wody w pobliżu (hydrologia)
  useEffect(() => {
    const g = overlayGroup.current;
    if (!g) return;
    g.clearLayers();
    const t = props.overlays?.terrain;
    if (t?.depressions_geojson) {
      L.geoJSON(t.depressions_geojson as never, { style: { color: "#1d4ed8", weight: 1, fillColor: "#3b82f6", fillOpacity: 0.45 } })
        .bindTooltip("Zagłębienie terenu – tu zbiera się woda").addTo(g);
    }
    if (t?.flow_lines_geojson) {
      L.geoJSON(t.flow_lines_geojson as never, { style: { color: "#0ea5e9", weight: 2.5, dashArray: "6 4" } })
        .bindTooltip("Linia spływu wody").addTo(g);
    }
    waterLayers.current.clear();
    (props.overlays?.hydrology?.nearest_water ?? []).forEach((w, i) => {
      if (!w.geometry) return;
      const kind = KIND[w.kind] ?? w.kind;
      const color = w.kind === "ditch" ? "#0891b2" : "#1e40af";
      const popup = document.createElement("div");
      popup.className = "water-popup";
      popup.innerHTML = `<b></b><span></span><br/><button type="button" class="btn-secondary">Więcej danych o wodach →</button>`;
      popup.querySelector("b")!.textContent = w.name ?? kind;
      popup.querySelector("span")!.textContent = `${w.name && w.name !== kind ? `${kind} · ` : ""}${fmtDist(w.distance_m)} od działki`;
      popup.querySelector("button")!.addEventListener("click", () => { setExpanded(false); emit("water:details", { index: i }); });
      const layer = L.geoJSON(w.geometry as never, {
        style: { color, weight: 4, fillColor: "#60a5fa", fillOpacity: 0.35 },
        // szerszy, niewidoczny obrys ułatwia trafienie w cienką linię rowu palcem/myszką
        onEachFeature: (_f, l) => { if (l instanceof L.Polyline && !(l instanceof L.Polygon)) L.polyline(l.getLatLngs() as L.LatLngExpression[], { weight: 16, opacity: 0 }).on("click", (e) => { L.DomEvent.stopPropagation(e.originalEvent); layer.openPopup(e.latlng); }).addTo(g); },
      }).bindTooltip(`${w.name ?? kind} – ${fmtDist(w.distance_m)} (kliknij)`).bindPopup(popup)
        .on("click", (e) => L.DomEvent.stopPropagation((e as L.LeafletMouseEvent).originalEvent)).addTo(g);
      waterLayers.current.set(i, layer);
    });
    for (const p of props.overlays?.places ?? []) {
      L.geoJSON(p.geojson as never, { style: { color: "#c2410c", weight: 3, fillColor: "#fb923c", fillOpacity: 0.45 } })
        .bindTooltip(`Rekomendacja: ${p.title}`).addTo(g);
    }
  }, [props.overlays?.terrain, props.overlays?.hydrology, props.overlays?.places]);

  // klik w wiersz tabeli „Wody w pobliżu” → pokaż ten ciek/zbiornik na mapie
  useEffect(() => on("water:focus", ({ index }) => {
    const m = map.current, layer = waterLayers.current.get(index);
    if (!m || !layer) return;
    el.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    const b = layer.getBounds();
    if (props.parcel) { const [x1, y1, x2, y2] = props.parcel.bbox; b.extend([[y1, x1], [y2, x2]]); }
    m.fitBounds(b, { padding: [30, 30], maxZoom: 17 });
    layer.setStyle({ weight: 7, color: "#f59e0b" });
    setTimeout(() => layer.setStyle({ weight: 4, color: "#1e40af" }), 2500);
    layer.openPopup(layer.getBounds().getCenter());
  }), [props.parcel]);

  // powiększenie całego kafelka (nie zoom): po zmianie rozmiaru Leaflet musi przeliczyć wymiary
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const t = setTimeout(() => {
      m.invalidateSize();
      if (props.parcel) {
        const [x1, y1, x2, y2] = props.parcel.bbox;
        m.fitBounds([[y1, x1], [y2, x2]], { padding: [40, 40], maxZoom: 17 });
      }
    }, 60);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setExpanded(false);
    if (expanded) window.addEventListener("keydown", esc);
    document.body.classList.toggle("map-open", expanded);
    return () => { clearTimeout(t); window.removeEventListener("keydown", esc); };
  }, [expanded]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className={`map-wrap${expanded ? " expanded" : ""}`}>
      {props.expandable && (
        <button type="button" className="map-expand no-print" aria-pressed={expanded} onClick={() => setExpanded((v) => !v)}>
          {expanded ? "✕ Zmniejsz mapę" : "⤢ Powiększ mapę"}
        </button>
      )}
      <div className="map" ref={el} role="application" aria-label="Mapa – kliknij pole, aby wybrać działkę" />
      <p className="hint no-print">Przybliż mapę i kliknij swoje pole – granice działek widać od dużego przybliżenia. Zmień podkład na „Zdjęcie lotnicze” w prawym górnym rogu.</p>
    </div>
  );
}
