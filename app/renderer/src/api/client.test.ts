// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/api/client.test.ts
import { tableFromArrays, tableToIPC } from "apache-arrow";
import { afterEach, describe, expect, it, vi } from "vitest";

import { decodeSpectra, EngineRequestError, getEngineConnection, runSkeleton } from "./client";

/** Arrow IPC stream shaped like the engine's `spectra_to_arrow` output. */
function spectraStream(): Uint8Array {
  const table = tableFromArrays({
    x: new Float32Array([900, 902, 904]),
    y_0: new Float32Array([0.1, 0.2, 0.3]),
    y_1: new Float32Array([1.5, 1.25, 1]),
  });
  return tableToIPC(table, "stream");
}

const connection = { port: 52114, token: "tok" };

afterEach(() => {
  delete window.vibechem;
});

describe("decodeSpectra", () => {
  it("returns the shared x column and one y per spectrum, in order", () => {
    const spectra = decodeSpectra(spectraStream());
    expect(Array.from(spectra.x)).toEqual([900, 902, 904]);
    expect(spectra.y).toHaveLength(2);
    expect(Array.from(spectra.y[1] ?? [])).toEqual([1.5, 1.25, 1]);
  });

  it("rejects a non-float32 column", () => {
    const table = tableFromArrays({ x: new Float64Array([1, 2]) });
    expect(() => decodeSpectra(tableToIPC(table, "stream"))).toThrow(/float32/);
  });
});

describe("runSkeleton", () => {
  it("posts the request with the bearer token to the engine on 127.0.0.1", async () => {
    const fetchFn = vi.fn<typeof fetch>(() =>
      Promise.resolve(new Response(spectraStream().slice().buffer)),
    );
    const body = { dataset: "gasoline_nir", apply_snv: true, width: 1200 } as const;
    const spectra = await runSkeleton(connection, body, fetchFn);

    expect(spectra.y).toHaveLength(2);
    const [url, init] = fetchFn.mock.calls[0] ?? [];
    expect(url).toBe("http://127.0.0.1:52114/api/v1/skeleton/run");
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer tok");
    expect(JSON.parse(String(init?.body))).toEqual(body);
  });

  it("throws EngineRequestError with the HTTP status on an error response", async () => {
    const fetchFn = vi.fn<typeof fetch>(() => Promise.resolve(new Response("{}", { status: 401 })));
    const run = runSkeleton(
      connection,
      { dataset: "gasoline_nir", apply_snv: false, width: 1200 },
      fetchFn,
    );
    await expect(run).rejects.toEqual(new EngineRequestError(401));
  });

  it("throws EngineRequestError(0) when the engine is unreachable", async () => {
    const fetchFn = vi.fn<typeof fetch>(() => Promise.reject(new TypeError("Failed to fetch")));
    const run = runSkeleton(
      connection,
      { dataset: "gasoline_nir", apply_snv: false, width: 1200 },
      fetchFn,
    );
    await expect(run).rejects.toMatchObject({ status: 0 });
  });
});

describe("getEngineConnection", () => {
  it("asks the preload bridge", async () => {
    window.vibechem = { engine: () => Promise.resolve(connection) };
    await expect(getEngineConnection()).resolves.toEqual(connection);
  });

  it("fails without the preload bridge (plain browser)", async () => {
    await expect(getEngineConnection()).rejects.toBeInstanceOf(EngineRequestError);
  });
});
