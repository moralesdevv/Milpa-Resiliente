import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { VisionSection } from "./VisionSection";
import { CATEGORIES, GAPS, LEVELS, STATUSES } from "./visionData";

afterEach(cleanup);

const view = () => render(<MemoryRouter><VisionSection /></MemoryRouter>);

describe("index vision section", () => {
  it("carries the central message and the required closing statement verbatim", () => {
    view();
    expect(screen.getByRole("heading", { level: 2 })).toHaveTextContent("From a local pilot to a national climate-resilient agricultural intelligence network.");
    expect(document.body).toHaveTextContent("begins with a pilot in Jocotán, but its ambition goes beyond a single territory: turning Earth observation, agricultural science and local knowledge into better-informed climate adaptation decisions for farming communities.");
  });

  it("marks only Level 01 as built and every other level as planned", () => {
    view();
    expect(LEVELS.filter((level) => level.state === "Built").map((level) => level.id)).toEqual(["l1"]);
    const buttons = screen.getAllByRole("button", { name: /^Level 0\d/ });
    expect(buttons).toHaveLength(4);
    expect(within(buttons[0]).getByText("Built")).toBeVisible();
    for (const button of buttons.slice(1)) expect(within(button).getByText("Planned")).toBeVisible();
  });

  it("separates implemented, simulated and pending-validation items for the pilot and opens one level at a time", () => {
    view();
    expect(screen.getByText("Implemented", { selector: ".vision-today .v-tag" })).toBeVisible();
    expect(screen.getByText("Simulated")).toBeVisible();
    expect(screen.getByText("Pending validation")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Level 02/ }));
    expect(screen.getByRole("button", { name: /Level 02/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("button", { name: /Level 01/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText(/No institution has agreed to participate/)).toBeVisible();
  });

  it("lists every gap with the six required fields and filters by category and priority", () => {
    view();
    expect(GAPS.length).toBeGreaterThanOrEqual(18);
    expect(new Set(GAPS.map((item) => item.category))).toEqual(new Set(CATEGORIES));
    for (const item of GAPS) {
      expect(Object.values(item).every((value) => String(value).length > 0)).toBe(true);
    }
    expect(screen.getAllByText("What is missing")).toHaveLength(GAPS.length);

    fireEvent.click(screen.getByRole("button", { name: /^Scalability/ }));
    expect(screen.getByText("A second real territory")).toBeVisible();
    expect(screen.queryByText("Camotán station history and local validation of satellite rainfall")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Critical" }));
    expect(screen.getByText(/No gaps match these filters/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Show all gaps" }));
    expect(screen.getAllByText("What is missing")).toHaveLength(GAPS.length);
  });

  it("includes the gaps the brief names and never labels a planned item as implemented", () => {
    const titles = GAPS.map((item) => item.title).join(" | ");
    for (const needle of ["Camotán station", "Kc and phenological", "planting windows", "Field trials", "water-stress", "Processing for many regions", "technicians and farmers"]) {
      expect(titles.toLowerCase()).toContain(needle.toLowerCase());
    }
    const implemented = GAPS.filter((item) => item.status === "Implemented").map((item) => item.id);
    expect(implemented).toEqual(["repro", "rls"]);
    expect(STATUSES).toHaveLength(4);
  });

  it("states that no impact has been measured", () => {
    view();
    expect(screen.getByText(/No gain in yield, reduction in losses or change in income is claimed/)).toBeVisible();
    expect(screen.getByText(/nothing below has been measured/i)).toBeVisible();
  });
});
