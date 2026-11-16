import "leaflet/dist/leaflet.css";

import { CircleMarker, MapContainer, Rectangle, TileLayer, Tooltip } from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";
import { useTranslation } from "react-i18next";

import type { ZoneContextView } from "../../api/adapters";
import type { components } from "../../api/types.gen";

type Cell = ZoneContextView["cells"][number];
type Parcel = components["schemas"]["ParcelOut"];

const tileUrl = (import.meta.env.VITE_MAP_TILE_URL as string | undefined)?.trim();
const tileAttribution = (import.meta.env.VITE_MAP_ATTRIBUTION as string | undefined)?.trim() ?? "";

/** IMERG se dibuja con trazo continuo azul; las demás fuentes, con trazo discontinuo dorado. */
const cellStyle = (source: string) => source === "IMERG"
  ? { color: "#0b659f", dash: undefined, kind: "solid" as const }
  : { color: "#a56b00", dash: "6 4", kind: "dashed" as const };

/**
 * Zone map: climate cells (zone level) and, when present, the parcel's
 * generalized display cell. Exact parcel geometry is never drawn.
 * The base layer provider is configured by environment variable; with none,
 * only the cell outlines are drawn. The legend only restates what is drawn.
 */
export default function ZoneMap({ cells, parcel }: { cells: Cell[]; parcel?: Parcel | null }) {
  const { t } = useTranslation();
  const bounds: LatLngBoundsExpression = cells.length
    ? [[Math.min(...cells.map((c) => c.south)), Math.min(...cells.map((c) => c.west))], [Math.max(...cells.map((c) => c.north)), Math.max(...cells.map((c) => c.east))]]
    : [[0, 0], [1, 1]];
  const hasParcel = parcel?.display_location != null;
  const sources = [...new Set(cells.map((cell) => cell.source))];

  return <figure className="zone-map" role="group" aria-label={t("map.label")}>
    <MapContainer bounds={bounds} scrollWheelZoom={false} style={{ height: 400, width: "100%" }} keyboard>
      {tileUrl && <TileLayer url={tileUrl} attribution={tileAttribution} />}
      {cells.map((cell) => {
        const style = cellStyle(cell.source);
        return <Rectangle key={cell.cell_id} bounds={[[cell.south, cell.west], [cell.north, cell.east]]} pathOptions={{ color: style.color, weight: 2.5, fillOpacity: 0.12, dashArray: style.dash }}>
          <Tooltip sticky>{cell.source} · {cell.cell_id}</Tooltip>
        </Rectangle>;
      })}
      {hasParcel && <CircleMarker center={[parcel!.display_location!.lat, parcel!.display_location!.lon]} radius={9} pathOptions={{ color: "#05191f", weight: 2.5, fillColor: "#ffc933", fillOpacity: 1 }}>
        <Tooltip permanent>{t("map.parcelGeneralized", { meters: parcel!.display_grid_m ?? 1000 })}</Tooltip>
      </CircleMarker>}
    </MapContainer>
    <figcaption>
      <ul className="map-legend" aria-label={t("map.legend")}>
        {sources.map((source) => {
          const style = cellStyle(source);
          return <li key={source}>
            <span className={`map-legend__swatch map-legend__swatch--${style.kind}`} style={{ borderColor: style.color }} aria-hidden="true" />
            {source} · {t(style.kind === "solid" ? "map.legendSolid" : "map.legendDashed")}
          </li>;
        })}
        {hasParcel && <li><span className="map-legend__dot" aria-hidden="true" />{t("map.legendParcel")}</li>}
      </ul>
    </figcaption>
  </figure>;
}
