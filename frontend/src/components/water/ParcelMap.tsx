import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { Expand, Layers, LocateFixed, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { USE_MOCKS, type DataBlock, type ParcelRef } from "@/api/client";
import { dist, WATER_KIND } from "@/api/adapt";
const svg = (body: string) =>
  `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
/** Ikony proponowanych działań (proste, w stylu lucide). */
const REC_ICON = {
  weir: svg('<path d="M3 19h18M6 19V7m12 12V7M6 9h12M6 13h12"/>'),
  pond: svg('<path d="M12 3s-6 7-6 11a6 6 0 0 0 12 0c0-4-6-11-6-11z"/>'),
  buffer: svg('<path d="M12 22v-6m0 0c-4 0-6-3-6-6 0-4 3-7 6-8 3 1 6 4 6 8 0 3-2 6-6 6z"/>'),
  well: svg('<path d="M4 10h16M6 10v10h12V10M8 10V6h8v4M12 3v3"/>'),
  other: svg('<circle cx="12" cy="12" r="4"/>'),
};
const REC_KIND: Record<string, keyof typeof REC_ICON> = {
  zastawka_row: "weir", oczko_zbiornik: "pond", mokradlo: "pond", pas_buforowy: "buffer",
};
const REC_LABEL: Partial<Record<keyof typeof REC_ICON, string>> = { weir: "Zastawka", pond: "Zbiornik / oczko", buffer: "Pas zieleni", well: "Studnia" };
/** Punkty zaczepienia pinezek: punkt → on sam; poligon → środek; linie → środkowy wierzchołek każdej linii. */
function anchorPoints(g: GeoJSON.GeoJsonObject): L.LatLngExpression[] {
  const out: L.LatLngExpression[] = [];
  const walk = (o: GeoJSON.GeoJsonObject) => {
    if (o.type === "FeatureCollection") (o as GeoJSON.FeatureCollection).features.forEach(walk);
    else if (o.type === "Feature") walk((o as GeoJSON.Feature).geometry);
    else if (o.type === "Point") { const [x, y] = (o as GeoJSON.Point).coordinates; out.push([y!, x!]); }
    else if (o.type === "LineString") {
      const c = (o as GeoJSON.LineString).coordinates, m = c[Math.floor(c.length / 2)]!;
      out.push([m[1]!, m[0]!]);
    } else if (o.type === "MultiLineString") (o as GeoJSON.MultiLineString).coordinates.forEach((c) =>
      walk({ type: "LineString", coordinates: c } as GeoJSON.LineString));
    else {
      const b = L.geoJSON(o).getBounds();
      if (b.isValid()) out.push(b.getCenter());
    }
  };
  walk(g);
  return out;
}
type Props = {
  parcel: ParcelRef | null;
  blocks: Record<string, DataBlock>;
  /** pokazuj warstwy z analizy (po „Sprawdź działkę”); false = tylko wskazana działka */
  showAnalysis: boolean;
  onSelect: (lon: number, lat: number) => void;
  /** id obiektu do wycentrowania; `n` zmienia się przy każdym kliknięciu (ponowne centrowanie tego samego) */
  highlight: { id: string; n: number } | null;
  onMore: (key: string) => void;
  fullscreen: boolean;
  onFullscreen: () => void;
  /** działka kliknięta na mapie (inna niż analizowana) – obrys + dymek z informacjami */
  picked?: ParcelRef | null;
  onAnalyze?: (id: string) => void;
};
/** Kafelki przez backend (cache na dysku + w przeglądarce); w trybie demo bez backendu – prosto ze źródeł. */
const TILE = USE_MOCKS
  ? {
      ortho: null as string | null,
      osm: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      parcels: null as string | null,
    }
  : { ortho: "/api/tiles/ortho/{z}/{x}/{y}", osm: "/api/tiles/osm/{z}/{x}/{y}", parcels: "/api/tiles/parcels/{z}/{x}/{y}" };
export default function ParcelMap({
  picked = null,
  onAnalyze,
  parcel,
  blocks,
  showAnalysis,
  onSelect,
  highlight,
  onMore,
  fullscreen,
  onFullscreen,
}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const features = useRef<Record<string, L.Layer>>({});
  const callbacks = useRef({ onSelect, onMore, onAnalyze });
  callbacks.current = { onSelect, onMore, onAnalyze };
  const [base, setBase] = useState<"ortho" | "osm">("ortho");
  const [menu, setMenu] = useState(false);
  const [visible, setVisible] = useState({ water: true, recommendations: true, boundaries: true });
  const [tileWarning, setTileWarning] = useState(false);
  useEffect(() => {
    if (!host.current) return;
    const m = L.map(host.current, { zoomControl: true, scrollWheelZoom: true, dragging: true, doubleClickZoom: true }).setView([52.1, 19.4], 6);
    map.current = m;
    L.control.scale({ imperial: false, position: "bottomright" }).addTo(m);
    const click = (e: L.LeafletMouseEvent) =>
      callbacks.current.onSelect(e.latlng.lng, e.latlng.lat);
    m.on("click", click);
    return () => {
      m.remove();
      map.current = null;
    };
  }, []);
  // nowa działka → dopasuj widok (mapa zostaje ta sama, bez przeładowania podkładu)
  useEffect(() => {
    const m = map.current;
    if (!m || !parcel) return;
    m.fitBounds([[parcel.bbox[1], parcel.bbox[0]], [parcel.bbox[3], parcel.bbox[2]]], { padding: [42, 65], maxZoom: 17 });
  }, [parcel?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    setTileWarning(false);
    const layer =
      base === "osm"
        ? L.tileLayer(TILE.osm, {
            maxZoom: 19,
            updateWhenIdle: true,
            keepBuffer: 2,
            attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
          })
        : TILE.ortho
          ? L.tileLayer(TILE.ortho, {
              // kafle 512 px = 4× mniej zapytań; backend składa je z WMS GUGiK i trzyma w cache
              tileSize: 512,
              zoomOffset: -1,
              maxZoom: 20,
              updateWhenIdle: true,
              keepBuffer: 2,
              attribution: "Ortofotomapa © GUGiK / Geoportal",
            })
          : L.tileLayer.wms(
            "https://mapy.geoportal.gov.pl/wss/service/PZGIK/ORTO/WMS/StandardResolution",
            {
              layers: "Raster",
              format: "image/jpeg",
              transparent: false,
              maxZoom: 20,
              // kafle 512 px = 4× mniej zapytań WMS niż 256 px (GUGiK ogranicza liczbę zapytań z jednego IP)
              tileSize: 512,
              zoomOffset: -1,
              updateWhenIdle: true,
              keepBuffer: 4,
              attribution: "Ortofotomapa © GUGiK / Geoportal",
            },
          );
    let errors = 0;
    layer.on("tileerror", () => {
      errors++;
      if (errors >= 3) {
        setTileWarning(true);
        // zdjęcie lotnicze limitowane → sam przełączam na mapę, zamiast zostawiać szare pole
        if (base === "ortho") setBase("osm");
      }
    });
    layer.addTo(m);
    layer.bringToBack();
    return () => {
      layer.remove();
    };
  }, [base]);
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const css = getComputedStyle(document.documentElement);
    const token = (name: string) => css.getPropertyValue(name).trim();
    const green = token("--primary"),
      blue = token("--water"),
      orange = token("--warning"),
      waterDark = "#1e3a8a";
    const group = L.featureGroup().addTo(m);
    features.current = {};
    if (parcel) {
      const boundary = L.geoJSON(parcel.geometry as GeoJSON.GeoJsonObject, {
        style: { color: green, weight: 3, fillColor: green, fillOpacity: 0.06 },
      }).addTo(group);
      features.current["parcel"] = boundary;
      boundary.on("click", (e: L.LeafletMouseEvent) => {
        L.DomEvent.stopPropagation(e);
        callbacks.current.onSelect(e.latlng.lng, e.latlng.lat);
      });
    }
    const popup = (title: string, detail: string, key: string | null, note = "") => {
      const el = document.createElement("div");
      const strong = document.createElement("strong");
      strong.textContent = title;
      el.append(strong);
      const p = document.createElement("div");
      p.textContent = detail;
      el.append(p);
      if (note) {
        const n = document.createElement("small");
        n.textContent = note;
        el.append(n);
      }
      if (key) {
        const button = document.createElement("button");
        button.className = "map-popup-action";
        button.textContent = "Więcej danych →";
        button.addEventListener("click", () => callbacks.current.onMore(key));
        el.append(button);
      }
      return el;
    };
    const stop = (e: L.LeafletEvent) => L.DomEvent.stopPropagation(e as L.LeafletMouseEvent);
    if (picked && picked.id !== parcel?.id) {
      const el = document.createElement("div");
      el.className = "picked-popup";
      const t = document.createElement("strong");
      t.textContent = `Działka ${picked.parcel_number ?? picked.id}`;
      const info = document.createElement("div");
      info.textContent = `${picked.area_ha.toLocaleString("pl-PL", { maximumFractionDigits: 2 })} ha · ${picked.region_name ? `obręb ${picked.region_name} · ` : ""}gmina ${picked.commune ?? "?"}`;
      const idEl = document.createElement("small");
      idEl.textContent = picked.id;
      el.append(t, info, idEl);
      if (callbacks.current.onAnalyze) {
        const b = document.createElement("button");
        b.className = "map-popup-action";
        b.textContent = "Sprawdź tę działkę →";
        b.addEventListener("click", () => callbacks.current.onAnalyze?.(picked.id));
        el.append(b);
      }
      const pl = L.geoJSON(picked.geometry as GeoJSON.GeoJsonObject, {
        style: { color: "#f8fafc", weight: 3, dashArray: "6 5", fillColor: "#f8fafc", fillOpacity: 0.12 },
      }).bindPopup(el).on("click", stop).addTo(group);
      setTimeout(() => pl.openPopup(), 50);
    }
    const terrain = showAnalysis ? blocks["terrain"]?.data.raw : null;
    const hydro = showAnalysis ? blocks["hydrology"]?.data.raw : null;
    const recs = showAnalysis ? blocks["analysis"]?.data.recommendations ?? [] : [];
    if (visible.water) {
      (terrain?.flow_lines_geojson?.features ?? []).forEach((f: GeoJSON.Feature) =>
        L.geoJSON(f, { style: { color: blue, weight: 2, dashArray: "6 7" }, interactive: false }).addTo(group));
      (terrain?.depressions_geojson?.features ?? []).forEach((f: GeoJSON.Feature<GeoJSON.Geometry, Record<string, number>>, i: number) => {
        const pr = f.properties ?? {};
        const l = L.geoJSON(f, { style: { color: blue, weight: 2, fillColor: blue, fillOpacity: 0.35 } })
          .bindPopup(popup("Zagłębienie terenu – zbiera się tu woda",
            `${(pr.area_m2 ?? 0).toLocaleString("pl-PL")} m² · do ${(pr.max_depth_m ?? 0).toLocaleString("pl-PL")} m · ok. ${(pr.volume_m3 ?? 0).toLocaleString("pl-PL")} m³`,
            "terrain", pr.catchment_ha != null ? `Woda spływa tu z ok. ${pr.catchment_ha.toLocaleString("pl-PL")} ha` : ""))
          .on("click", stop).addTo(group);
        features.current[`dep-${i}`] = l;
        if (!features.current["depression"] && (f.properties as unknown as { touches_parcel?: boolean })?.touches_parcel) features.current["depression"] = l;
      });
      (terrain?.runoff_exits_geojson?.features ?? []).forEach((f: GeoJSON.Feature<GeoJSON.Geometry, Record<string, number>>, i: number) => {
        const l = L.geoJSON(f, { style: { color: waterDark, weight: 6, opacity: 0.85, lineCap: "round" } })
          .bindPopup(popup("Tu woda ucieka z pola", `ok. ${f.properties?.length_m ?? "?"} m granicy · spływ z ${f.properties?.catchment_ha?.toLocaleString("pl-PL") ?? "?"} ha`,
            "terrain"))
          .on("click", stop).addTo(group);
        features.current[`exit-${i}`] = l;
      });
      (hydro?.nearest_water ?? []).forEach((w: { kind: string; name: string | null; distance_m: number; geometry: GeoJSON.Geometry | null }, i: number) => {
        if (!w.geometry) return;
        const kind = WATER_KIND[w.kind] ?? "Woda";
        const l = L.geoJSON(w.geometry, { style: { color: w.kind === "ditch" ? "#0e7490" : blue, weight: 4, fillColor: blue, fillOpacity: 0.55 } })
          .bindPopup(popup(w.name && !kind.toLowerCase().includes(w.name.toLowerCase()) ? `${kind}: ${w.name}` : kind, `${dist(w.distance_m)} od działki`, "hydrology", "BDOT10k (GUGiK)"))
          .bindTooltip(`${kind} · ${dist(w.distance_m)}`)
          .on("click", stop).addTo(group);
        features.current[`water-${i}`] = l;
      });
    }
    if (visible.recommendations) {
      // proponowane działania = pinezki z ikoną (osobno od wody); zbiornik dodatkowo przerywanym obrysem bez wypełnienia
      const pin = (kind: keyof typeof REC_ICON, label: string) =>
        L.divIcon({ className: "rec-pin-wrap", html: `<div class="rec-pin ${kind}${label ? "" : " icon-only"}">${REC_ICON[kind]}${label ? `<b>${label}</b>` : ""}</div>`,
          iconSize: [0, 0], iconAnchor: [15, 34], popupAnchor: [0, -30] });
      recs.filter((r) => r.where_geojson).forEach((r) => {
        const kind = REC_KIND[r.measure_id] ?? "other";
        const fg = L.featureGroup().addTo(group);
        const pts = anchorPoints(r.where_geojson as GeoJSON.GeoJsonObject);
        // pinezki najpierw – popup grupy otwiera się na pierwszej warstwie
        // kilka miejsc tego samego działania (np. pas zieleni) → podpis tylko przy pierwszym, reszta sama ikona
        pts.forEach((p, i) => L.marker(p, { icon: pin(kind, i === 0 ? REC_LABEL[kind] ?? r.title : ""), keyboard: true, title: r.title }).addTo(fg));
        if (kind === "pond")
          L.geoJSON(r.where_geojson as GeoJSON.GeoJsonObject, {
            style: { color: orange, weight: 2.5, dashArray: "5 5", fill: false }, interactive: false,
          }).addTo(fg);
        fg.bindPopup(popup(r.title, r.when ? `Kiedy: ${r.when}` : "", null, "Proponowane miejsce – sprawdź w terenie przed pracami"))
          .on("click", stop);
        features.current[`rec-${r.measure_id}`] = fg;
        if (!features.current["recommendation"]) features.current["recommendation"] = fg;
      });
      // studnia / ujęcie wody: tylko gdy nawadnianie jest zasadne i prawo nie wyklucza ujęcia (np. park narodowy)
      const irr = showAnalysis ? blocks["analysis"]?.data.irrigation : null;
      const wellAllowed = ((blocks["legal_context"]?.data.raw?.hints ?? []) as { topic: string }[]).some((h) => h.topic === "studnia");
      if (parcel && irr && (irr.recommended === "yes" || irr.recommended === "monitor") && wellAllowed) {
        const fg = L.featureGroup().addTo(group);
        L.marker([parcel.centroid[1], parcel.centroid[0]], { icon: pin("well", "Studnia"), title: "Studnia lub ujęcie wody" }).addTo(fg);
        fg.bindPopup(popup("Studnia lub ujęcie wody do nawadniania",
          "Do 30 m głębokości i 5 m³ na dobę (średnio w roku) – bez pozwolenia wodnoprawnego.", "legal_context",
          "Miejsce orientacyjne – lokalizację i głębokość wskaże firma studniarska lub hydrogeolog")).on("click", stop);
        features.current["rec-studnia"] = fg;
      }
    }
    let wms: L.TileLayer | null = null;
    if (visible.boundaries) {
      const opts = { minZoom: 15, maxZoom: 20, tileSize: 512, zoomOffset: -1, updateWhenIdle: true,
        attribution: "Granice ewidencyjne © GUGiK" };
      wms = (TILE.parcels
        ? L.tileLayer(TILE.parcels, opts)
        : L.tileLayer.wms("https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow", {
            ...opts, layers: "dzialki,numery_dzialek", format: "image/png", transparent: true })
      ).addTo(m);
    }
    return () => {
      group.remove();
      wms?.remove();
    };
  }, [parcel, picked, visible, blocks, showAnalysis]);
  // wycentruj wskazany obiekt (z tabeli analityka lub przycisku w raporcie) na mapie – bez powiększania
  useEffect(() => {
    const m = map.current;
    const f = highlight ? features.current[highlight.id] : null;
    if (!m || !f) return;
    host.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    if (f instanceof L.Marker || f instanceof L.CircleMarker) {
      m.setView(f.getLatLng(), Math.max(m.getZoom(), 16));
    } else if (f instanceof L.FeatureGroup) {
      const b = f.getBounds();
      if (b.isValid()) {
        m.flyToBounds(b, { padding: [40, 40], maxZoom: 17, duration: 0.6 });
        if (f instanceof L.GeoJSON) {
          f.setStyle({ weight: 7 });
          setTimeout(() => f.resetStyle(), 2200);
        }
      }
    }
    setTimeout(() => (f as L.Layer & { openPopup?: () => void }).openPopup?.(), 650);
  }, [highlight, parcel, visible, blocks]);
  useEffect(() => {
    const t = setTimeout(() => map.current?.invalidateSize(), 100);
    return () => clearTimeout(t);
  }, [fullscreen]);
  return (
    <div className="map-shell">
      <div
        className="map-canvas"
        ref={host}
        role="region"
        aria-label="Mapa działki, obniżeń terenu i wody w okolicy"
      />
      <div className="map-top">
        <div className="map-base-switch" aria-label="Podkład mapy">
          <Button
            variant={base === "ortho" ? "secondary" : "ghost"}
            className="map-choice"
            onClick={() => setBase("ortho")}
            aria-pressed={base === "ortho"}
          >
            Zdjęcie lotnicze
          </Button>
          <Button
            variant={base === "osm" ? "secondary" : "ghost"}
            className="map-choice"
            onClick={() => setBase("osm")}
            aria-pressed={base === "osm"}
          >
            Mapa
          </Button>
        </div>
        <div className="map-toolbar">
          <Button
            variant="ghost"
            className="map-tool"
            aria-label="Warstwy mapy"
            title="Warstwy mapy"
            onClick={() => setMenu(!menu)}
            aria-expanded={menu}
          >
            <Layers />
          </Button>
          <Button
            variant="ghost"
            className="map-tool"
            aria-label={fullscreen ? "Zamknij dużą mapę" : "Powiększ mapę"}
            title={fullscreen ? "Zamknij mapę" : "Powiększ mapę"}
            onClick={onFullscreen}
          >
            {fullscreen ? <X /> : <Expand />}
          </Button>
        </div>
      </div>
      {menu && (
        <div className="map-layer-menu">
          <strong>Widoczne na mapie</strong>
          {(
            [
              ["water", "Woda i kierunek odpływu"],
              ["recommendations", "Proponowane działania (zastawka, zbiornik, studnia…)"],
              ["boundaries", "Granice z Geoportalu"],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              <input
                type="checkbox"
                checked={visible[key]}
                onChange={(e) => setVisible((v) => ({ ...v, [key]: e.target.checked }))}
              />
              {label}
            </label>
          ))}
          <Button
            variant="ghost"
            className="w-full mt-2"
            onClick={() => {
              if (parcel) map.current?.fitBounds(
                [
                  [parcel.bbox[1], parcel.bbox[0]],
                  [parcel.bbox[3], parcel.bbox[2]],
                ],
                { padding: [45, 65] },
              );
              setMenu(false);
            }}
          >
            <LocateFixed />
            Wróć do działki
          </Button>
        </div>
      )}
      <div className="map-legend">
        <div className="legend-row">
          <span className="legend-sample" />
          Twoja działka
        </div>
        <div className="legend-row">
          <span className="legend-sample blue" />
          Miejsce zbierania wody
        </div>
        <div className="legend-row">
          <span className="legend-sample flow" />
          Kierunek odpływu
        </div>
        <div className="legend-row">
          <span className="legend-sample exit" />
          Tu woda ucieka z pola
        </div>
        <div className="legend-row">
          <span className="legend-pin" />
          Proponowane działanie
        </div>
        {tileWarning && (
          <Button
            variant="link"
            className="h-auto p-0 text-xs"
            onClick={() => setBase(base === "ortho" ? "osm" : "ortho")}
          >
            Nie wczytano podkładu. Zmień widok.
          </Button>
        )}
      </div>
    </div>
  );
}
