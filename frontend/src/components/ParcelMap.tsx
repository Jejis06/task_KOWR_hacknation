// Czysty Leaflet (BSD-2) – bez react-leaflet (licencja Hippocratic, niezgodna z przeniesieniem praw na KOWR).
import { useEffect, useRef } from "react";
import L from "leaflet";
import type { ParcelRef } from "../api/types";

export function ParcelMap(props: { parcel: ParcelRef | null; onPick: (lon: number, lat: number) => void }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.GeoJSON | null>(null);
  const onPick = useRef(props.onPick);
  onPick.current = props.onPick;

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current).setView([52.1, 19.4], 6);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "&copy; OpenStreetMap", maxZoom: 19 }).addTo(m);
    // granice i numery działek – KIEG GUGiK (od dużych zoomów)
    L.tileLayer
      .wms("https://integracja.gugik.gov.pl/cgi-bin/KrajowaIntegracjaEwidencjiGruntow", {
        layers: "dzialki,numery_dzialek", format: "image/png", transparent: true, minZoom: 15, attribution: "GUGiK KIEG",
      })
      .addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) => onPick.current(e.latlng.lng, e.latlng.lat));
    map.current = m;
    return () => { m.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    layer.current?.remove();
    if (!props.parcel) return;
    layer.current = L.geoJSON(props.parcel.geometry as never, { style: { color: "#0a7d32", weight: 3 } }).addTo(m);
    const [x1, y1, x2, y2] = props.parcel.bbox;
    m.fitBounds([[y1, x1], [y2, x2]], { padding: [40, 40], maxZoom: 17 });
  }, [props.parcel]);

  return <div className="map" ref={el} />;
}
