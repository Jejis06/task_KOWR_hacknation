import type { ParcelRef } from "../api/types";

export function ParcelHeader({ parcel }: { parcel: ParcelRef }) {
  return (
    <div className="parcel-header">
      <h2>Działka {parcel.parcel_number}</h2>
      <dl>
        <dt>Identyfikator</dt><dd>{parcel.id}</dd>
        <dt>Gmina</dt><dd>{parcel.commune}</dd>
        <dt>Powiat</dt><dd>{parcel.county}</dd>
        <dt>Województwo</dt><dd>{parcel.voivodeship}</dd>
        <dt>Obręb</dt><dd>{parcel.region_name}</dd>
        <dt>Powierzchnia</dt><dd>{parcel.area_ha.toFixed(2)} ha</dd>
      </dl>
    </div>
  );
}
