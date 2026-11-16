import boundaryRaw from "../../../../regions/jocotan_chiquimula_boundary.geojson?raw";

/**
 * Municipal boundary used by the map. It is the SAME GeoJSON file the server validates parcels against
 * (`regions/jocotan_chiquimula_boundary.geojson`, see docs/MAP_AND_LOCATION.md). The check here only gives
 * immediate feedback; the server decides (PostGIS `ST_Covers`) whenever a location would be stored.
 */
export type LatLon = [lat: number, lon: number];
export type Polygon = LatLon[][]; // [outer ring, ...holes]
export type Boundary = {
  name: string;
  department: string;
  municipalCode: number | null;
  label: string;
  polygons: Polygon[];
  /** [[south, west], [north, east]] */
  bounds: [LatLon, LatLon];
};

const EDGE_TOLERANCE = 1e-9;

function toRing(raw: unknown): LatLon[] {
  if (!Array.isArray(raw) || raw.length < 4) throw new Error("A boundary ring needs at least four positions.");
  return raw.map((position) => {
    if (!Array.isArray(position) || typeof position[0] !== "number" || typeof position[1] !== "number") {
      throw new Error("A boundary position must be [longitude, latitude].");
    }
    return [position[1], position[0]] as LatLon;
  });
}

export function parseBoundary(text: string): Boundary {
  const data = JSON.parse(text) as { features?: Array<{ properties?: Record<string, unknown>; geometry?: { type?: string; coordinates?: unknown } }> };
  const feature = data.features?.[0];
  const geometry = feature?.geometry;
  if (!feature || !geometry || (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon")) {
    throw new Error("The boundary must be a Polygon or MultiPolygon feature.");
  }
  const coordinates = geometry.coordinates as unknown[];
  const rawPolygons = geometry.type === "Polygon" ? [coordinates] : coordinates;
  const polygons = rawPolygons.map((polygon) => (polygon as unknown[]).map(toRing));
  const all = polygons.flat(2);
  const lats = all.map(([lat]) => lat);
  const lons = all.map(([, lon]) => lon);
  const props = feature.properties ?? {};
  const name = String(props.NOMBRE_1 ?? props.name ?? "");
  const department = String(props.DEPTO_1 ?? props.department ?? "");
  const code = props.COD_MUN;
  return {
    name,
    department,
    municipalCode: typeof code === "number" ? code : null,
    label: [name, department].filter(Boolean).join(", "),
    polygons,
    bounds: [[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]],
  };
}

function onSegment(lat: number, lon: number, a: LatLon, b: LatLon): boolean {
  const cross = (lon - a[1]) * (b[0] - a[0]) - (lat - a[0]) * (b[1] - a[1]);
  if (Math.abs(cross) > EDGE_TOLERANCE) return false;
  return lat >= Math.min(a[0], b[0]) - EDGE_TOLERANCE && lat <= Math.max(a[0], b[0]) + EDGE_TOLERANCE
    && lon >= Math.min(a[1], b[1]) - EDGE_TOLERANCE && lon <= Math.max(a[1], b[1]) + EDGE_TOLERANCE;
}

function ringContains(ring: LatLon[], lat: number, lon: number): "inside" | "edge" | "outside" {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const a = ring[i];
    const b = ring[j];
    if (onSegment(lat, lon, a, b)) return "edge";
    if (a[0] > lat !== b[0] > lat && lon < ((b[1] - a[1]) * (lat - a[0])) / (b[0] - a[0]) + a[1]) inside = !inside;
  }
  return inside ? "inside" : "outside";
}

/** True when the point is inside the boundary or on its edge (the server's `ST_Covers` is inclusive too). */
export function insideBoundary(boundary: Boundary, lat: number, lon: number): boolean {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return false;
  return boundary.polygons.some(([outer, ...holes]) => {
    const where = ringContains(outer, lat, lon);
    if (where === "outside") return false;
    if (where === "edge") return true;
    return !holes.some((hole) => ringContains(hole, lat, lon) === "inside");
  });
}

/** Outer rings (lat/lon) of a GeoJSON Polygon/MultiPolygon geometry; anything else yields no rings. */
export function outerRings(geometry: unknown): LatLon[][] {
  if (typeof geometry !== "object" || geometry === null) return [];
  const { type, coordinates } = geometry as { type?: string; coordinates?: unknown };
  if (!Array.isArray(coordinates)) return [];
  const polygons = type === "Polygon" ? [coordinates] : type === "MultiPolygon" ? coordinates : [];
  try {
    return polygons.map((polygon) => toRing((polygon as unknown[])[0]));
  } catch {
    return [];
  }
}

export type CellBounds = { south: number; west: number; north: number; east: number };

export function insideCell(cell: CellBounds, lat: number, lon: number): boolean {
  return lat >= cell.south && lat <= cell.north && lon >= cell.west && lon <= cell.east;
}

export const jocotan: Boundary = parseBoundary(boundaryRaw);
