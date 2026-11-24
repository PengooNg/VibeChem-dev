// SPDX-License-Identifier: GPL-3.0-or-later
// app/scripts/bench-transport-client.mjs — Node client of the transport spike (TASKS.md T0.12).
//
// node scripts/bench-transport-client.mjs <port> <token> <lines|density> <width> <repeats>
//
// Started by scripts/bench_transport.py. Times GET /api/v1/spike/preview with fetch and
// decodes it with apache-arrow (the renderer's decoder), extracting the typed arrays a
// plot needs, as decodeSpectra in renderer/src/api/client.ts does. Prints one JSON line.
import { tableFromIPC } from "apache-arrow";

const [port, token, mode, width, repeats] = process.argv.slice(2);
const url = `http://127.0.0.1:${port}/api/v1/spike/preview?mode=${mode}&width=${width}`;

/** Decode and pull out every column's values (float32 curves; density counts as Uint16Arrays). */
function decode(bytes) {
  const table = tableFromIPC(bytes);
  const arrays = [];
  for (const field of table.schema.fields) {
    const column = table.getChild(field.name);
    if (field.name !== "density") {
      arrays.push(column.toArray());
      continue;
    }
    // Fixed-size list: each chunk's child holds `length * listSize` counts from `offset`.
    for (const chunk of column.data) {
      const size = chunk.type.listSize;
      const start = chunk.offset * size;
      arrays.push(chunk.children[0].values.subarray(start, start + chunk.length * size));
    }
  }
  return arrays;
}

const samples = [];
let size = 0;
for (let i = 0; i <= Number(repeats); i++) {
  const t0 = performance.now();
  const response = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  if (!response.ok) throw new Error(`HTTP ${String(response.status)}`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  const t1 = performance.now();
  decode(bytes);
  const t2 = performance.now();
  if (i === 0) {
    size = bytes.length; // warm-up, not timed
    continue;
  }
  const serverMs = Number(response.headers.get("Server-Timing").split("dur=")[1]);
  samples.push({ server_ms: serverMs, fetch_ms: t1 - t0, decode_ms: t2 - t1, total_ms: t2 - t0 });
}

const result = { client: "node", mode, bytes: size };
for (const key of Object.keys(samples[0])) {
  const values = samples.map((s) => s[key]).sort((a, b) => a - b);
  const mid = values.length >> 1;
  const median = values.length % 2 ? values[mid] : (values[mid - 1] + values[mid]) / 2;
  result[`${key}_median`] = Math.round(median * 100) / 100;
  result[`${key}_max`] = Math.round(values[values.length - 1] * 100) / 100;
}
process.stdout.write(JSON.stringify(result) + "\n");
