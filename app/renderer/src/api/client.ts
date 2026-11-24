// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/api/client.ts — typed calls to the local engine API (DATA_MODEL.md §1, §2.12).
//
// Paths and bodies come from the generated OpenAPI types (`schema.d.ts`, `pnpm gen:api`).
import { tableFromIPC } from "apache-arrow";

import type { components, paths } from "./schema";

/** Port + session token of the local engine, handed over by the preload (main/preload.ts). */
export interface EngineConnection {
  port: number;
  token: string;
}

declare global {
  interface Window {
    /** Set by the Electron preload; absent in a plain browser. */
    vibechem?: { engine(): Promise<EngineConnection> };
  }
}

export type SkeletonRunRequest = components["schemas"]["SkeletonRunRequest"];

/** Spectra in the `view=spectra` lines format (DATA_MODEL.md §2.8): shared x, one y per spectrum. */
export interface Spectra {
  x: Float32Array;
  y: Float32Array[];
}

/** An engine request failed; `status` is the HTTP status (0 = engine unreachable). */
export class EngineRequestError extends Error {
  constructor(readonly status: number) {
    super(`engine request failed (HTTP ${String(status)})`);
    this.name = "EngineRequestError";
  }
}

const SKELETON_RUN = "/api/v1/skeleton/run" satisfies keyof paths;

/** Ask the preload for the engine connection. */
export function getEngineConnection(): Promise<EngineConnection> {
  if (window.vibechem === undefined) return Promise.reject(new EngineRequestError(0));
  return window.vibechem.engine();
}

/** Decode an Arrow IPC stream with columns `x`, `y_0` … `y_{n-1}` (engine `spectra_to_arrow`). */
export function decodeSpectra(bytes: Uint8Array): Spectra {
  const table = tableFromIPC(bytes);
  const column = (name: string): Float32Array => {
    const values: unknown = table.getChild(name)?.toArray();
    if (!(values instanceof Float32Array)) throw new Error(`Arrow column ${name} is not float32`);
    return values;
  };
  const yNames = table.schema.fields.map((field) => field.name).filter((n) => n.startsWith("y_"));
  return { x: column("x"), y: yNames.map(column) };
}

/** `POST /skeleton/run`: raw or SNV spectra of a bundled reference dataset. */
export async function runSkeleton(
  connection: EngineConnection,
  body: SkeletonRunRequest,
  fetchFn: typeof fetch = fetch,
): Promise<Spectra> {
  let response: Response;
  try {
    response = await fetchFn(`http://127.0.0.1:${String(connection.port)}${SKELETON_RUN}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${connection.token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
  } catch {
    throw new EngineRequestError(0);
  }
  if (!response.ok) throw new EngineRequestError(response.status);
  return decodeSpectra(new Uint8Array(await response.arrayBuffer()));
}
