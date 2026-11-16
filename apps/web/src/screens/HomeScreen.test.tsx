import { cleanup, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { EXPERIENCES, HomeScreen } from "./HomeScreen";

afterEach(cleanup);

const view = () => render(<MemoryRouter><HomeScreen /></MemoryRouter>);

describe("index", () => {
  it("states the headline, the challenge it answers and keeps a single h1", () => {
    view();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("The next harvest starts with the sky.");
    const plate = document.querySelector(".home-plate") as HTMLElement;
    expect(within(plate).getByText("NASA Space Apps Challenge")).toBeVisible();
    expect(within(plate).getByText("Field Shift: Adapting Farms with NASA Data")).toBeVisible();
  });

  it("keeps every LAUNCH DEMO entry pointing at /demo", () => {
    view();
    const links = screen.getAllByRole("link", { name: "Launch demo" });
    expect(links.length).toBeGreaterThanOrEqual(3);
    for (const link of links) expect(link).toHaveAttribute("href", "/demo");
  });

  it("lists the six experiences with their routes and no sequence numbers", () => {
    view();
    const list = screen.getByRole("heading", { name: "Six ways into the same evidence" }).closest("section") as HTMLElement;
    expect(within(list).getAllByRole("link")).toHaveLength(EXPERIENCES.length);
    for (const item of EXPERIENCES) expect(within(list).getByRole("link", { name: new RegExp(item.name) })).toHaveAttribute("href", item.to);
    expect(list.textContent).not.toMatch(/\b0[1-6]\b/);
  });

  it("does not imply NASA endorsement or a forecast", () => {
    view();
    expect(document.body).toHaveTextContent("not affiliated with or endorsed by NASA");
    expect(document.body).toHaveTextContent("Scenarios are synthetic and are not forecasts");
  });

  it("draws one tick per year from 2001 to 2025", () => {
    view();
    expect(document.querySelectorAll(".home-ruler li")).toHaveLength(25);
    expect(screen.getByRole("img", { name: /2001 to 2025/ })).toBeVisible();
  });
});
