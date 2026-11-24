// SPDX-License-Identifier: GPL-3.0-or-later
// app/main/engine.test.ts
// @vitest-environment node
import { describe, expect, it } from "vitest";

import { parseListeningLine } from "./engine";

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
