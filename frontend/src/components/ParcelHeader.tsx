import type { ParcelRef } from "../api/types";
import { num } from "../lib/format";

export function ParcelHeader({ parcel }: { parcel: ParcelRef }) {
  const [lon, lat] = parcel.centroid;
  return (
    <div className="parcel-header">
      <h2>Działka nr {parcel.parcel_number ?? parcel.id}</h2>
      <dl>
        <dt>Identyfikator</dt><dd>{parcel.id}</dd>
        <dt>Obręb</dt><dd>{parcel.region_name ?? "brak danych"}</dd>
        <dt>Gmina</dt><dd>{parcel.commune ?? "brak danych"}</dd>
        <dt>Powiat</dt><dd>{parcel.county ?? "brak danych"}</dd>
        <dt>Województwo</dt><dd>{parcel.voivodeship ?? "brak danych"}</dd>
        <dt>Powierzchnia</dt><dd>{num(parcel.area_ha, "ha", 2)}</dd>
        <dt>Środek działki</dt><dd>{lat.toFixed(5)}° N, {lon.toFixed(5)}° E</dd>
      </dl>
      <p className="muted small">Granice: GUGiK ULDK (ewidencja gruntów). Działka ewidencyjna nie zawsze pokrywa się z polem uprawnym.</p>
    </div>
  );
}
