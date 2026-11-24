// SPDX-License-Identifier: GPL-3.0-or-later
// app/e2e/packaged.spec.ts — installer smoke test: the packaged app starts its bundled engine
// and runs the skeleton pipeline from the app://vibechem origin (TASKS.md T0.11).
//
// Runs only when VIBECHEM_PACKAGED_APP points at the executable inside electron-builder's
// unpacked output (installers.yml); skipped in `pnpm e2e`.
import { _electron as electron, expect, test } from "@playwright/test";

const executablePath = process.env["VIBECHEM_PACKAGED_APP"];

test("packaged app: bundled engine answers the app://vibechem page", async () => {
  test.skip(executablePath === undefined, "set VIBECHEM_PACKAGED_APP to a packaged executable");
  const app = await electron.launch({ executablePath: executablePath ?? "" });
  try {
    const window = await app.firstWindow();
    expect(window.url()).toBe("app://vibechem/index.html");

    await window.getByRole("button", { name: "Run" }).click();
    // Port + token came over IPC, and the engine accepted the app origin (CORS + Origin check).
    await expect(window.getByText("Data here · 60 × 401")).toBeVisible({ timeout: 90_000 });
  } finally {
    await app.close();
  }
});
