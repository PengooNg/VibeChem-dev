// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/App.test.tsx
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { App } from "./App";
import { LANGUAGES, resources } from "./i18n";

/** All dotted keys of a nested string table, e.g. ["app.name", "app.tagline"]. */
function keys(table: object, prefix = ""): string[] {
  return Object.entries(table).flatMap(([k, v]) =>
    typeof v === "object" && v !== null ? keys(v as object, `${prefix}${k}.`) : [`${prefix}${k}`],
  );
}

afterEach(cleanup);

describe("App", () => {
  it("shows the app name and tagline in every language", () => {
    render(<App />);
    expect(screen.getAllByRole("heading", { name: "VibeChem" })).toHaveLength(LANGUAGES.length);
    for (const lng of LANGUAGES) {
      expect(screen.getByText(resources[lng].common.app.tagline)).toBeDefined();
    }
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
