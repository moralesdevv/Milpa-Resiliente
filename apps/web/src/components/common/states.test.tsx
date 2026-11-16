import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "../../i18n";
import { Empty, ErrorState, InsufficientData, Loading, ProvisionalBanner } from "./states";

describe("shared interface states", () => {
  beforeEach(async () => {
    await i18n.changeLanguage("es");
  });

  it("announces loading and empty states to assistive technology", () => {
    const { rerender } = render(<Loading />);
    expect(screen.getByRole("status")).toHaveTextContent("Cargando información");
    rerender(<Empty title="Sin registros" />);
    expect(screen.getByRole("status")).toHaveTextContent("Sin registros");
  });

  it("keeps error code and retry action visible", () => {
    const retry = vi.fn();
    render(<ErrorState error={Object.assign(new Error("Error de API"), { code: "RUN_MISSING" })} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("RUN_MISSING");
    screen.getByRole("button", { name: "Intentar de nuevo" }).click();
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("shows missing items in the insufficient state and keeps provisional notice textual", () => {
    const { container } = render(<>
      <InsufficientData title="Información insuficiente" missing={["Cita del umbral"]} />
      <ProvisionalBanner />
    </>);
    expect(screen.getByText("Cita del umbral")).toBeVisible();
    expect(screen.getByRole("note")).toHaveTextContent("Resultado provisional");
    expect(container.querySelector(".provisional-banner")).toBeVisible();
  });
});
