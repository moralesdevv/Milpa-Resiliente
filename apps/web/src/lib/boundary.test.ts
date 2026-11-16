import { describe, expect, it } from "vitest";

import { insideBoundary, insideCell, jocotan, parseBoundary } from "./boundary";

const feature = (geometry: unknown) => JSON.stringify({ type: "FeatureCollection", features: [{ type: "Feature", properties: { NOMBRE_1: "Prueba", DEPTO_1: "Depto" }, geometry }] });

describe("municipal boundary (Jocotán)", () => {
  it("loads the real file with its administrative attributes", () => {
    expect(jocotan.label).toBe("Jocotán, Chiquimula");
    expect(jocotan.municipalCode).toBe(2004);
    expect(jocotan.polygons).toHaveLength(1);
    expect(jocotan.polygons[0][0].length).toBeGreaterThan(100);
    const [[south, west], [north, east]] = jocotan.bounds;
    expect(south).toBeGreaterThan(14.7);
    expect(north).toBeLessThan(14.95);
    expect(west).toBeLessThan(east);
  });

  it("accepts a point in Jocotán and rejects neighbouring municipalities and bounding-box corners", () => {
    expect(insideBoundary(jocotan, 14.8194, -89.3903)).toBe(true); // Jocotán town (public reference point)
    expect(insideBoundary(jocotan, 14.8203, -89.3733)).toBe(false); // Camotán town: next municipality
    expect(insideBoundary(jocotan, 14.8011, -89.5436)).toBe(false); // Chiquimula city
    expect(insideBoundary(jocotan, 14.90, -89.22)).toBe(false); // inside the bounding box, outside the polygon
    expect(insideBoundary(jocotan, 14.5, -89.5)).toBe(false);
  });

  it("treats a vertex of the polygon as inside (inclusive, like the server)", () => {
    const [lat, lon] = jocotan.polygons[0][0][10];
    expect(insideBoundary(jocotan, lat, lon)).toBe(true);
  });

  it("rejects non-finite input instead of guessing", () => {
    expect(insideBoundary(jocotan, Number.NaN, -89.39)).toBe(false);
    expect(insideBoundary(jocotan, 14.82, Number.POSITIVE_INFINITY)).toBe(false);
  });

  it("honours holes and multipolygons", () => {
    const withHole = parseBoundary(feature({
      type: "Polygon",
      coordinates: [
        [[-89.5, 14.7], [-89.2, 14.7], [-89.2, 14.9], [-89.5, 14.9], [-89.5, 14.7]],
        [[-89.4, 14.78], [-89.3, 14.78], [-89.3, 14.82], [-89.4, 14.82], [-89.4, 14.78]],
      ],
    }));
    expect(insideBoundary(withHole, 14.72, -89.45)).toBe(true);
    expect(insideBoundary(withHole, 14.80, -89.35)).toBe(false); // inside the hole
    const multi = parseBoundary(feature({
      type: "MultiPolygon",
      coordinates: [
        [[[-89.5, 14.7], [-89.4, 14.7], [-89.4, 14.8], [-89.5, 14.8], [-89.5, 14.7]]],
        [[[-89.3, 14.8], [-89.2, 14.8], [-89.2, 14.9], [-89.3, 14.9], [-89.3, 14.8]]],
      ],
    }));
    expect(insideBoundary(multi, 14.75, -89.45)).toBe(true);
    expect(insideBoundary(multi, 14.85, -89.25)).toBe(true);
    expect(insideBoundary(multi, 14.75, -89.25)).toBe(false);
  });

  it("refuses a malformed boundary", () => {
    expect(() => parseBoundary(feature({ type: "Point", coordinates: [0, 0] }))).toThrow(/Polygon/);
    expect(() => parseBoundary(feature({ type: "Polygon", coordinates: [[[-89.5, 14.7], [-89.4, 14.7]]] }))).toThrow(/four positions/);
  });

  it("checks whether a point falls inside a climate cell", () => {
    const cell = { south: 14.8, west: -89.4, north: 14.9, east: -89.3 };
    expect(insideCell(cell, 14.85, -89.35)).toBe(true);
    expect(insideCell(cell, 14.79, -89.35)).toBe(false);
  });
});
