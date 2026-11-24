// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/App.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import type { Spectra } from "./api/client";
import { App } from "./App";
import { LANGUAGES, resources } from "./i18n";

// uPlot needs a real canvas; the e2e test covers drawing. Here the plot reports what it got.
vi.mock("./plots/SpectraPlot", () => ({
  SpectraPlot: ({ spectra, yLabel }: { spectra: Spectra; yLabel: string }) => (
    <div data-testid="plot">{`${yLabel}: ${String(spectra.y.length)} spectra`}</div>
  ),
}));

const runSkeleton = vi.hoisted(() => vi.fn());
vi.mock("./api/client", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  getEngineConnection: () => Promise.resolve({ port: 1, token: "t" }),
  runSkeleton,
}));

/** All dotted keys of a nested string table, e.g. ["app.name", "toolbar.run"]. */
function keys(table: object, prefix = ""): string[] {
  return Object.entries(table).flatMap(([k, v]) =>
    typeof v === "object" && v !== null ? keys(v as object, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

function renderApp() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

beforeAll(() => {
  // React Flow measures nodes with ResizeObserver, which jsdom lacks.
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
});

afterEach(() => {
  cleanup();
  runSkeleton.mockReset();
});

describe("App", () => {
  it("shows the two fixed blocks and empty previews before a run", () => {
    renderApp();
    expect(screen.getByText("Dataset")).toBeDefined();
    expect(screen.getByText("SNV")).toBeDefined();
    expect(screen.getAllByText("Press Run to see the spectra.")).toHaveLength(2);
    expect(screen.getAllByTitle("Not run yet")).toHaveLength(2);
  });

  it("runs raw and SNV on Run and shows both previews", async () => {
    const spectra: Spectra = {
      x: new Float32Array(401),
      y: Array.from({ length: 60 }, () => new Float32Array(401)),
    };
    runSkeleton.mockResolvedValue(spectra);
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: /Run/ }));

    expect(await screen.findByText("log(1/R): 60 spectra")).toBeDefined();
    expect(screen.getByText("SNV value: 60 spectra")).toBeDefined();
    expect(screen.getByText("Data here · 60 × 401")).toBeDefined();
    const bodies = runSkeleton.mock.calls.map((call: unknown[]) => call[1]);
    expect(bodies).toEqual([
      { dataset: "gasoline_nir", width: 1200, apply_snv: false },
      { dataset: "gasoline_nir", width: 1200, apply_snv: true },
    ]);
  });

  it("shows an alert and error state when the engine fails", async () => {
    const { EngineRequestError } = await import("./api/client");
    runSkeleton.mockRejectedValue(new EngineRequestError(500));
    renderApp();
    fireEvent.click(screen.getByRole("button", { name: /Run/ }));

    expect((await screen.findByRole("alert")).textContent).toBe(
      "The engine returned an error (HTTP 500).",
    );
    expect(screen.getAllByTitle("Error")).toHaveLength(2);
  });
});

describe("i18n string files", () => {
  it("have the same keys in en, ja and vi", () => {
    const en = keys(resources.en).sort();
    for (const lng of LANGUAGES) {
      expect(keys(resources[lng]).sort()).toEqual(en);
    }
  });
});
