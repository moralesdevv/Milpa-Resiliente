import "leaflet/dist/leaflet.css";

import { CircleMarker, MapContainer, Polygon, Rectangle, TileLayer, Tooltip, useMapEvents } from "react-leaflet";
import type { Map as LeafletMap } from "leaflet";
import { useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { useTranslation } from "react-i18next";

import type { ZoneContextView } from "../../api/adapters";
import type { components } from "../../api/types.gen";
import { insideBoundary, insideCell, jocotan, outerRings } from "../../lib/boundary";
import type { LatLon } from "../../lib/boundary";

type Cell = ZoneContextView["cells"][number];
type Parcel = components["schemas"]["ParcelOut"];

/**
 * Basemap: CARTO "Voyager" raster tiles (OpenStreetMap data, no token needed, attribution shown). The
 * default OpenStreetMap volunteer servers answer 403 "Access blocked" to pages that send no Referer, and
 * this app sends `Referrer-Policy: no-referrer` for privacy, so they are not a safe default. Tiles are
 * requested with `referrerPolicy="origin"` (only the site origin, never the page URL with run ids).
 * Override with VITE_MAP_TILE_URL / VITE_MAP_ATTRIBUTION (docs/MAP_AND_LOCATION.md). If tiles fail to load
 * the map stays usable: outlines still draw.
 */
const tileUrl = (import.meta.env.VITE_MAP_TILE_URL as string | undefined)?.trim() || "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png";
const tileAttribution = (import.meta.env.VITE_MAP_ATTRIBUTION as string | undefined)?.trim() || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>';
const TILE_FAILURES_BEFORE_NOTICE = 3;
const outline = jocotan.polygons[0][0];

/** IMERG is drawn with a solid blue outline; the other sources with a dashed gold one. */
const cellStyle = (source: string) => source === "IMERG"
  ? { color: "#0b659f", dash: undefined, kind: "solid" as const }
  : { color: "#a56b00", dash: "6 4", kind: "dashed" as const };

function PickLocation({ onPick }: { onPick: (point: LatLon) => void }) {
  useMapEvents({ click: ({ latlng }) => onPick([latlng.lat, latlng.lng]) });
  return null;
}

function parseCoordinate(text: string, min: number, max: number): number | null {
  const value = Number(text.trim().replace(",", "."));
  return text.trim() !== "" && Number.isFinite(value) && value >= min && value <= max ? value : null;
}

/**
 * Zone map: municipal boundary, climate data cells (context layers) and, when present, the parcel's
 * generalized display cell. Exact parcel geometry is never drawn. The location picker is a visual aid:
 * nothing is saved, and a point is never called a parcel; the server re-validates any stored location.
 */
export default function ZoneMap({ cells, parcel, area }: { cells: Cell[]; parcel?: Parcel | null; area?: unknown }) {
  const { t } = useTranslation();
  const mapRef = useRef<LeafletMap | null>(null);
  const [picked, setPicked] = useState<LatLon | null>(null);
  const [latText, setLatText] = useState("");
  const [lonText, setLonText] = useState("");
  const [formError, setFormError] = useState(false);
  const [tilesLoaded, setTilesLoaded] = useState(0);
  const [tileFailures, setTileFailures] = useState(0);
  const hasParcel = parcel?.display_location != null;
  const areaRings = useMemo(() => outerRings(area), [area]);
  const sources = [...new Set(cells.map((cell) => cell.source))];
  const bounds = jocotan.bounds;
  const check = useMemo(() => picked
    ? { inside: insideBoundary(jocotan, picked[0], picked[1]), inCell: cells.some((cell) => insideCell(cell, picked[0], picked[1])) }
    : null, [picked, cells]);
  const tilesFailed = tilesLoaded === 0 && tileFailures >= TILE_FAILURES_BEFORE_NOTICE;

  const pick = (point: LatLon) => {
    setPicked(point);
    setLatText(point[0].toFixed(5));
    setLonText(point[1].toFixed(5));
    setFormError(false);
  };
  const clear = () => { setPicked(null); setLatText(""); setLonText(""); setFormError(false); };
  const center = () => mapRef.current?.fitBounds(bounds);
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const lat = parseCoordinate(latText, -90, 90);
    const lon = parseCoordinate(lonText, -180, 180);
    if (lat === null || lon === null) { setFormError(true); setPicked(null); return; } // no stale verdict beside the error
    setFormError(false);
    setPicked([lat, lon]);
    mapRef.current?.panTo([lat, lon]);
  };

  return <figure className="zone-map" role="group" aria-label={t("map.label")}>
    <MapContainer ref={mapRef} bounds={bounds} maxBounds={[[bounds[0][0] - 0.15, bounds[0][1] - 0.15], [bounds[1][0] + 0.15, bounds[1][1] + 0.15]]} maxBoundsViscosity={0.6} scrollWheelZoom style={{ height: 460, width: "100%" }} keyboard>
      <TileLayer url={tileUrl} attribution={tileAttribution} maxZoom={18} subdomains="abcd" referrerPolicy="origin" eventHandlers={{ tileload: () => setTilesLoaded((n) => n + 1), tileerror: () => setTileFailures((n) => n + 1) }} />
      <PickLocation onPick={pick} />
      {cells.map((cell) => {
        const style = cellStyle(cell.source);
        return <Rectangle key={cell.cell_id} bounds={[[cell.south, cell.west], [cell.north, cell.east]]} pathOptions={{ color: style.color, weight: 2, fillOpacity: 0.08, dashArray: style.dash }}>
          <Tooltip sticky>{t("map.cellTooltip", { source: cell.source })}</Tooltip>
        </Rectangle>;
      })}
      {areaRings.map((ring, index) => <Polygon key={index} positions={ring} pathOptions={{ color: "#6941c6", weight: 2, dashArray: "2 6", fillOpacity: 0.05 }}>
        <Tooltip sticky>{t("map.areaTooltip")}</Tooltip>
      </Polygon>)}
      <Polygon positions={outline} pathOptions={{ color: "#087f5b", weight: 3, fillOpacity: 0.04 }}><Tooltip sticky>{jocotan.label}</Tooltip></Polygon>
      {hasParcel && <CircleMarker center={[parcel!.display_location!.lat, parcel!.display_location!.lon]} radius={9} pathOptions={{ color: "#05191f", weight: 2.5, fillColor: "#ffc933", fillOpacity: 1 }}>
        <Tooltip permanent>{t("map.parcelGeneralized", { meters: parcel!.display_grid_m ?? 1000 })}</Tooltip>
      </CircleMarker>}
      {picked && check && <CircleMarker center={picked} radius={8} pathOptions={{ color: check.inside ? "#071f26" : "#b42318", weight: 2, fillColor: check.inside ? "#ffca28" : "#fda29b", fillOpacity: 1 }}>
        <Tooltip permanent>{t(check.inside ? "map.selectedTooltip" : "map.outsideTooltip")}</Tooltip>
      </CircleMarker>}
    </MapContainer>

    {tilesFailed && <p className="notice" role="status" data-testid="map-tiles-failed">{t("map.tilesFailed")}</p>}

    <figcaption className="zone-map__panel">
      <p>{t("map.help", { label: jocotan.label })}</p>
      <form className="zone-map__form" onSubmit={submit} aria-label={t("map.formLabel")} noValidate>
        <label className="field"><span>{t("map.latitude")}</span>
          <input inputMode="decimal" autoComplete="off" value={latText} onChange={(event) => setLatText(event.currentTarget.value)} aria-invalid={formError} placeholder="14.82" /></label>
        <label className="field"><span>{t("map.longitude")}</span>
          <input inputMode="decimal" autoComplete="off" value={lonText} onChange={(event) => setLonText(event.currentTarget.value)} aria-invalid={formError} placeholder="-89.39" /></label>
        <button type="submit" className="button button--secondary button--compact">{t("map.check")}</button>
        <button type="button" className="button button--secondary button--compact" onClick={center}>{t("map.center", { name: jocotan.name })}</button>
        <button type="button" className="button button--secondary button--compact" onClick={clear} disabled={!picked && !latText && !lonText}>{t("map.clear")}</button>
      </form>
      {formError && <p role="alert" data-testid="map-form-error">{t("map.invalidCoords")}</p>}
      {picked && check && !check.inside && <p role="alert" data-testid="map-outside">{t("map.outside", { label: jocotan.label })}</p>}
      {picked && check?.inside && <div role="status" data-testid="map-inside">
        <p>{t("map.inside", { label: jocotan.label, lat: picked[0].toFixed(3), lon: picked[1].toFixed(3) })}</p>
        <p>{t(check.inCell ? "map.cellInside" : "map.cellOutside")}</p>
      </div>}
      <p className="chart-caption">{t("map.notSaved")}</p>
      <ul className="map-legend" aria-label={t("map.legend")}>
        <li><span className="map-legend__swatch map-legend__swatch--solid" style={{ borderColor: "#087f5b" }} aria-hidden="true" />{t("map.legendBoundary", { label: jocotan.label })}</li>
        {areaRings.length > 0 && <li><span className="map-legend__swatch map-legend__swatch--dotted" style={{ borderColor: "#6941c6" }} aria-hidden="true" />{t("map.legendArea")}</li>}
        {sources.map((source) => {
          const style = cellStyle(source);
          return <li key={source}>
            <span className={`map-legend__swatch map-legend__swatch--${style.kind}`} style={{ borderColor: style.color }} aria-hidden="true" />
            {t("map.legendCell", { source, style: t(style.kind === "solid" ? "map.legendSolid" : "map.legendDashed") })}
          </li>;
        })}
        {hasParcel && <li><span className="map-legend__dot" aria-hidden="true" />{t("map.legendParcel")}</li>}
        <li><span className="map-legend__dot map-legend__dot--selected" aria-hidden="true" />{t("map.legendSelected")}</li>
      </ul>
    </figcaption>
  </figure>;
}
