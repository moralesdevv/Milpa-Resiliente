import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../i18n";

type TileProps = { eventHandlers?: { tileerror?: () => void; tileload?: () => void } };
type Children = { children?: ReactNode };
let tileBehaviour: "fail" | "ok" = "ok";
const mapStub = vi.hoisted(() => ({ fitBounds: vi.fn(), panTo: vi.fn() }));

// Leaflet needs a real layout engine (SVG, sizes) that jsdom lacks, so react-leaflet is replaced by light stubs.
// What is tested here is this component's own behaviour: legend, validation, inside/outside and failure states.
vi.mock("react-leaflet", () => ({
  MapContainer: forwardRef<unknown, Children>(({ children }, ref) => {
    useImperativeHandle(ref, () => mapStub);
    return <div data-testid="leaflet-map">{children}</div>;
  }),
  TileLayer: ({ eventHandlers }: TileProps) => {
    const reported = useRef(false); // the handlers change on every render: report the outcome once only
    useEffect(() => {
      if (reported.current) return;
      reported.current = true;
      for (let i = 0; i < 4; i += 1) {
        if (tileBehaviour === "fail") eventHandlers?.tileerror?.();
        else eventHandlers?.tileload?.();
      }
    });
    return null;
  },
  Polygon: ({ children }: Children) => <div>{children}</div>,
  Rectangle: ({ children }: Children) => <div>{children}</div>,
  CircleMarker: ({ children }: Children) => <div>{children}</div>,
  Tooltip: ({ children }: Children) => <span>{children}</span>,
  useMapEvents: () => null,
}));

import ZoneMap from "./ZoneMap";

const CELL = { cell_id: "1", source: "IMERG", weight: {} as never, south: 14.8, west: -89.4, north: 14.9, east: -89.3 };
const AREA = { type: "Polygon", coordinates: [[[-89.4, 14.8], [-89.3, 14.8], [-89.3, 14.9], [-89.4, 14.9], [-89.4, 14.8]]] };

function check(lat: string, lon: string) {
  fireEvent.change(screen.getByLabelText(i18n.t("map.latitude")), { target: { value: lat } });
  fireEvent.change(screen.getByLabelText(i18n.t("map.longitude")), { target: { value: lon } });
  fireEvent.click(screen.getByRole("button", { name: i18n.t("map.check") }));
}

describe("zone map", () => {
  beforeEach(async () => {
    tileBehaviour = "ok";
    await i18n.changeLanguage("en");
  });
  afterEach(cleanup);

  it("explains what the map shows and never calls a point a parcel", () => {
    render(<ZoneMap cells={[CELL]} area={AREA} />);
    expect(screen.getByRole("group", { name: /Jocotán/ })).toBeVisible();
    const legend = screen.getByRole("list", { name: "Map legend" });
    expect(legend).toHaveTextContent("Municipal boundary: Jocotán, Chiquimula");
    expect(legend).toHaveTextContent("IMERG climate data cell");
    expect(legend).toHaveTextContent("context layer");
    expect(legend).toHaveTextContent("Analysis zone");
    expect(screen.getByText(/not saved and no parcel is created or registered/)).toBeVisible();
  });

  it("accepts a location inside Jocotán and says whether it is inside the analysed climate cell", () => {
    render(<ZoneMap cells={[CELL]} />);
    check("14.8194", "-89.3903"); // Jocotán town
    expect(screen.getByTestId("map-inside")).toHaveTextContent("inside Jocotán, Chiquimula");
    expect(screen.getByTestId("map-inside")).toHaveTextContent("inside the climate data cell");
    expect(screen.queryByTestId("map-outside")).toBeNull();
  });

  it("warns when the location is in Jocotán but outside the climate cell the results describe", () => {
    render(<ZoneMap cells={[{ ...CELL, west: -89.2, east: -89.1 }]} />);
    check("14.8194", "-89.3903");
    expect(screen.getByTestId("map-inside")).toHaveTextContent("outside the climate data cell");
  });

  it("rejects a point in the neighbouring municipality and inside the bounding box corner", () => {
    render(<ZoneMap cells={[CELL]} />);
    check("14.8203", "-89.3733"); // Camotán town
    expect(screen.getByTestId("map-outside")).toHaveTextContent("outside Jocotán, Chiquimula");
    check("14.90", "-89.22");
    expect(screen.getByTestId("map-outside")).toBeVisible();
    expect(screen.queryByTestId("map-inside")).toBeNull();
  });

  it("does not keep the previous verdict next to a coordinate error", () => {
    render(<ZoneMap cells={[CELL]} />);
    check("14.60", "-89.30");
    expect(screen.getByTestId("map-outside")).toBeVisible();
    check("abc", "-89.30");
    expect(screen.getByTestId("map-form-error")).toBeVisible();
    expect(screen.queryByTestId("map-outside")).toBeNull();
    expect(screen.queryByTestId("map-inside")).toBeNull();
  });

  it("validates the typed coordinates before using them and can clear the selection", () => {
    render(<ZoneMap cells={[CELL]} />);
    check("abc", "-89.39");
    expect(screen.getByTestId("map-form-error")).toBeVisible();
    check("95", "-89.39");
    expect(screen.getByTestId("map-form-error")).toBeVisible();
    check("14,8194", "-89,3903"); // decimal comma is accepted
    expect(screen.queryByTestId("map-form-error")).toBeNull();
    expect(screen.getByTestId("map-inside")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Clear location" }));
    expect(screen.queryByTestId("map-inside")).toBeNull();
    expect(screen.getByLabelText("Latitude")).toHaveValue("");
  });

  it("shows the same interface in Spanish", async () => {
    await i18n.changeLanguage("es");
    render(<ZoneMap cells={[CELL]} />);
    expect(screen.getByRole("list", { name: "Leyenda del mapa" })).toHaveTextContent("Límite municipal: Jocotán, Chiquimula");
    check("14.8203", "-89.3733");
    expect(screen.getByTestId("map-outside")).toHaveTextContent("fuera de Jocotán, Chiquimula");
  });

  it("keeps working and says so when the basemap tiles fail to load", () => {
    tileBehaviour = "fail";
    render(<ZoneMap cells={[CELL]} />);
    expect(screen.getByTestId("map-tiles-failed")).toHaveTextContent("could not be loaded");
    expect(screen.getByRole("list", { name: "Map legend" })).toBeVisible();
  });

  it("does not show the tile warning when tiles load", () => {
    render(<ZoneMap cells={[CELL]} />);
    expect(screen.queryByTestId("map-tiles-failed")).toBeNull();
  });
});
