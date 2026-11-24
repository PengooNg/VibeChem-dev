// SPDX-License-Identifier: GPL-3.0-or-later
// app/main/appOrigin.test.ts
// @vitest-environment node
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { APP_ORIGIN, isTrustedSenderUrl, resolveAppFile } from "./appOrigin";

const ROOT = resolve("renderer-out");

describe("resolveAppFile", () => {
  it("maps app://vibechem paths to files in the renderer folder", () => {
    expect(APP_ORIGIN).toBe("app://vibechem");
    expect(resolveAppFile(ROOT, "app://vibechem/")).toBe(join(ROOT, "index.html"));
    expect(resolveAppFile(ROOT, "app://vibechem/index.html")).toBe(join(ROOT, "index.html"));
    expect(resolveAppFile(ROOT, "app://vibechem/assets/a%20b.js?x=1#y")).toBe(
      join(ROOT, "assets", "a b.js"),
    );
    // The URL parser already removes encoded dot segments: this stays inside the folder.
    expect(resolveAppFile(ROOT, "app://vibechem/%2e%2e/%2e%2e/secret.txt")).toBe(
      join(ROOT, "secret.txt"),
    );
  });

  it.each([
    ["another host", "app://evil/index.html"],
    ["another scheme", "file:///etc/passwd"],
    ["a lookalike host", "app://vibechem.evil/index.html"],
    ["an encoded backslash parent path", "app://vibechem/..%5c..%5csecret.txt"],
    ["an encoded slash parent path", "app://vibechem/assets%2f..%2f..%2f..%2fsecret.txt"],
    ["a NUL byte", "app://vibechem/index.html%00.js"],
    ["broken percent-encoding", "app://vibechem/%E0%A4%A"],
    ["not a URL", "nonsense"],
  ])("refuses %s", (_name, url) => {
    expect(resolveAppFile(ROOT, url)).toBeNull();
  });
});

describe("isTrustedSenderUrl", () => {
  it("trusts the app origin and, in development, the dev server origin only", () => {
    expect(isTrustedSenderUrl("app://vibechem/index.html", null)).toBe(true);
    expect(isTrustedSenderUrl("http://localhost:5173/", "http://localhost:5173")).toBe(true);
    expect(isTrustedSenderUrl("http://localhost:5173/", null)).toBe(false);
    expect(isTrustedSenderUrl("http://localhost:9999/", "http://localhost:5173")).toBe(false);
    expect(isTrustedSenderUrl("https://example.com/", "http://localhost:5173")).toBe(false);
    expect(isTrustedSenderUrl("", null)).toBe(false);
    expect(isTrustedSenderUrl("app://vibechem/", "not a url")).toBe(true);
    expect(isTrustedSenderUrl("http://localhost:5173/", "not a url")).toBe(false);
  });
});
