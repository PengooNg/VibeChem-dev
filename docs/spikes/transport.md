<!-- SPDX-License-Identifier: GPL-3.0-or-later -->
# Spike — transport (T0.12)

**Question:** can the ADR-003 transport (local HTTP on 127.0.0.1, Arrow IPC for arrays) deliver a 2,000 × 2,000 spectra preview in under 300 ms on all three OS?
**Answer:** yes. The slowest run was 207 ms (Node client, lines mode, macOS runner). Sending the bytes over loopback is a small share of that; most of the time goes to building the preview on the engine side.

## What was measured
`scripts/bench_transport.py` starts the real engine app (`create_app`, with the token and Origin checks) on uvicorn at 127.0.0.1. It adds a spike-only route, `GET /api/v1/spike/preview?mode=lines|density&width=1200`, and serves a synthetic 2,000 × 2,000 float64 matrix held in memory (three Gaussian bands, a slope and noise, seeded). Each timed round-trip covers:

1. the client sends the request with `Authorization: Bearer …`;
2. the engine builds the preview and encodes it as an Arrow IPC stream (returned in `Server-Timing`);
3. the bytes cross loopback;
4. the client decodes them.

Two clients ran: Python (`urllib` + pyarrow) and Node 24 (`fetch` + apache-arrow 21.2.0, the renderer's decoder). The Node client also pulls out every typed array, the same way `decodeSpectra` does in the renderer. Each combination got one warm-up request and then 20 timed ones.

| Mode | Payload | Size |
|---|---|---|
| lines (`max_lines` ≥ 2000) | `x` + 2,000 × `y_i`, float32, min/max-decimated to 1,200 points (`decimate_minmax`, `spectra_to_arrow` from the skeleton) | 9,567 KiB |
| density (default `max_lines` 500) | 1,200 rows: `x`, `mean`, `sd_lo`, `sd_hi`, 10 selected `y_i` (float32, averaged per pixel column), `density` = fixed-size list of 256 uint16 counts; y range in the schema metadata | 667 KiB |

The density layout exists only for this spike. It is not a DATA_MODEL.md format; the real one gets fixed when the preview endpoint is built (Phase 4).

## Results (GitHub-hosted runners, 2026-11-24, run 45324542102)
Times in ms, given as median with the maximum in brackets. "fetch" is the time from sending the request to having all the bytes, so it includes the server's build time. Transport alone is roughly fetch − server.

| OS | Client | Mode | Server build + encode | Fetch | Decode | **Total** |
|---|---|---|---|---|---|---|
| Linux x86_64 | Python | lines | 95.6 (102.1) | 100.3 (106.4) | 1.1 (1.4) | **101.4 (107.4)** |
| Linux x86_64 | Node | lines | 96.9 (104.1) | 110.0 (123.7) | 43.3 (70.8) | **152.4 (192.5)** |
| Linux x86_64 | Python | density | 41.1 (42.0) | 42.9 (43.8) | 0.1 (0.1) | **43.0 (43.9)** |
| Linux x86_64 | Node | density | 42.4 (47.2) | 46.9 (52.8) | 0.7 (1.1) | **47.8 (53.8)** |
| Windows AMD64 | Python | lines | 89.1 (101.1) | 99.7 (125.7) | 1.2 (2.8) | **101.1 (126.9)** |
| Windows AMD64 | Node | lines | 88.7 (103.6) | 107.3 (126.8) | 26.4 (44.1) | **133.9 (164.2)** |
| Windows AMD64 | Python | density | 61.8 (64.8) | 64.3 (67.5) | 0.1 (0.3) | **64.4 (67.6)** |
| Windows AMD64 | Node | density | 61.0 (86.5) | 64.9 (91.6) | 0.5 (1.0) | **65.5 (92.1)** |
| macOS arm64 | Python | lines | 100.5 (133.4) | 106.2 (141.4) | 0.7 (1.9) | **107.2 (143.2)** |
| macOS arm64 | Node | lines | 100.5 (136.4) | 111.4 (147.8) | 45.4 (63.9) | **155.2 (206.6)** |
| macOS arm64 | Python | density | 25.9 (32.3) | 27.5 (34.7) | 0.1 (0.2) | **27.5 (34.7)** |
| macOS arm64 | Node | density | 25.7 (31.4) | 28.3 (38.2) | 0.4 (0.6) | **28.6 (38.8)** |

As a cross-check, the Windows laptop on the work branch gave similar numbers (5 repeats): Python lines 113 ms, Node lines 143 ms, density 67–89 ms. Raw JSON for each OS is in the `transport-<os>` artifacts of the run, and the tables are in its job summaries. To reproduce: `uv run python scripts/bench_transport.py --node`, or run the `spike-transport` workflow by hand.

## Findings
1. **Loopback HTTP is cheap.** Moving 9.6 MB over loopback costs about 5–20 ms (fetch − server), and 0.67 MB costs about 2–5 ms. On these numbers ADR-003's other options (B: stdio via Electron main, C: ZeroMQ/gRPC) would save little. B would also need an extra copy through the main process.
2. **The engine's preview build dominates (≈ 90–100 ms in lines mode).** Nearly all of it is the Python loop over 600 buckets in the skeleton's `decimate_minmax`. A vectorised version (`np.minimum.reduceat` / `argmin` on a reshaped view) or the C++ kernel path should cut this a lot. That belongs to the Phase 4 preview endpoint, not to transport.
3. **Many-column Arrow tables are slow to decode in JS.** Decoding 2,001 columns takes 26–45 ms in Node (up to 71 ms), against about 1 ms in pyarrow: the cost is per column, not per byte. For large line counts, the real preview format should consider one `FixedSizeList<float32>` column (or one flat buffer) instead of one column per spectrum. Density mode decodes in under 1 ms.
4. **Density mode is about 14× smaller than all-lines mode and 1.6–5.4× faster end to end.** That supports the `max_lines` = 500 default in DATA_MODEL §2.8.
5. **Headroom:** the worst maximum is 207 ms, against the 300 ms target. CI runners are not 8 GB user laptops, so the margin is roughly 1.5× in lines mode and 3× or more in density mode.

## Not measured (limits of this spike)
- Chromium's own fetch and network stack in the Electron renderer, and uPlot drawing. Node uses undici rather than Chromium's stack, so renderer times may differ somewhat. The plot pipeline gets measured with benchmarks in T2.12 and in Phase 4.
- WebSocket progress events (DATA_MODEL §3), which don't exist yet.
- Antivirus or firewall interference with loopback servers on user machines (ADR-003's fallback trigger). Check this at Quan's install test (T0.15) and in beta reports.
- Real datasets (the payload size depends only on n, width and mode, not on the values) and concurrent requests.

## Recommendation for ADR-003 (for the T0.15 gate)
**Accept option A as written** (HTTP + WS on 127.0.0.1 with a random port, per-launch token, Origin check, and binary Arrow endpoints for arrays). The 300 ms target is met on all three OS with margin, and transport is not the bottleneck. Proposed additions to the ADR's Consequences/Actions:
- Phase 4 preview endpoint: vectorise or move decimation and the density raster to native code; budget ≤ 50 ms server time at 2,000 × 2,000.
- Preview wire format: for many lines, use a single list column rather than one column per spectrum (finding 3); fix the density layout in DATA_MODEL §2.8 then.
- Keep option B (stdio) as the documented fallback for blocked loopback; no work is needed now.
