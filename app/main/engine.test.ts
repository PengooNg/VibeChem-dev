// SPDX-License-Identifier: GPL-3.0-or-later
// app/main/engine.test.ts
// @vitest-environment node
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { devEngineCommand, packagedEngineCommand, parseListeningLine } from "./engine";

describe("engine commands", () => {
  it("runs the dev engine from the repository .venv with dev mode on", () => {
    expect(devEngineCommand("repo", "linux", { PATH: "p" })).toEqual({
      file: join("repo", ".venv", "bin", "python"),
      args: ["-m", "vibechem_engine.api"],
      cwd: "repo",
      env: { PATH: "p", VIBECHEM_DEV: "1" },
    });
    expect(devEngineCommand("repo", "win32", {}).file).toBe(
      join("repo", ".venv", "Scripts", "python.exe"),
    );
  });

  it("runs the bundled engine with the bundled testdata and dev mode forced off", () => {
    expect(packagedEngineCommand("res", "darwin", { PATH: "p", VIBECHEM_DEV: "1" })).toEqual({
      file: join("res", "engine", "vibechem-engine"),
      args: ["--testdata-dir", join("res", "testdata")],
      cwd: join("res", "engine"),
      env: { PATH: "p" },
    });
    expect(packagedEngineCommand("res", "win32", {}).file).toBe(
      join("res", "engine", "vibechem-engine.exe"),
    );
  });
});

describe("parseListeningLine", () => {
  it("reads port and token from the engine.listening line (DATA_MODEL.md §1)", () => {
    const line = JSON.stringify({ event: "engine.listening", port: 52114, token: "abc" });
    expect(parseListeningLine(line)).toEqual({ port: 52114, token: "abc" });
  });

  it.each([
    ["a log line", "INFO: Started server process"],
    ["another event", JSON.stringify({ event: "engine.stopping", port: 1, token: "t" })],
    [
      "a port that is not a number",
      JSON.stringify({ event: "engine.listening", port: "1", token: "t" }),
    ],
    ["a missing token", JSON.stringify({ event: "engine.listening", port: 1 })],
    ["JSON that is not an object", "null"],
  ])("ignores %s", (_name, line) => {
    expect(parseListeningLine(line)).toBeNull();
  });
});
