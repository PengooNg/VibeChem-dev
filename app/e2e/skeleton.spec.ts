// SPDX-License-Identifier: GPL-3.0-or-later
/// <reference lib="dom" />
// app/e2e/skeleton.spec.ts — walking skeleton: launch → Run → raw and SNV spectra visible (TASKS.md T0.10).
import { resolve } from "node:path";

import { _electron as electron, expect, test } from "@playwright/test";

import { RENDERER_PORT } from "../playwright.config";

const APP_DIR = resolve(import.meta.dirname, "..");

test("launch, Run, raw and SNV spectra are drawn", async () => {
  const app = await electron.launch({
    args: ["."],
    cwd: APP_DIR,
    env: { ...process.env, ELECTRON_RENDERER_URL: `http://localhost:${String(RENDERER_PORT)}` },
  });
  try {
    const window = await app.firstWindow();
    await expect(window.getByText("Press Run to see the spectra.")).toHaveCount(2);

    await window.getByRole("button", { name: "Run" }).click();

    // The SNV block shows where the data is: 60 spectra × 401 points (gasoline NIR).
    await expect(window.getByText("Data here · 60 × 401")).toBeVisible({ timeout: 90_000 });
    for (const name of ["Raw spectra", "After SNV"]) {
      const canvas = window.getByRole("region", { name }).locator("canvas");
      await expect(canvas).toBeVisible();
      // Lines are drawn in the data colour (teal: green well above red); axes are grey.
      const linePixels = await canvas.evaluate((element: HTMLCanvasElement) => {
        const context = element.getContext("2d");
        if (context === null) return 0;
        const { data } = context.getImageData(0, 0, element.width, element.height);
        let count = 0;
        for (let i = 0; i < data.length; i += 4) {
          if ((data[i + 3] ?? 0) > 0 && (data[i + 1] ?? 0) > (data[i] ?? 0) + 40) count += 1;
        }
        return count;
      });
      expect(linePixels).toBeGreaterThan(1000);
    }
  } finally {
    await app.close();
  }
});
