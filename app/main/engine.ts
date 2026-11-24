// SPDX-License-Identifier: GPL-3.0-or-later
// app/main/engine.ts — start the engine in development and read its port + token (DATA_MODEL.md §1).
//
// Dev mode only (T0.10): runs `python -m vibechem_engine.api` from the repository's uv
// environment with VIBECHEM_DEV=1. T0.11 adds the packaged engine (PyInstaller bundle),
// health check and restart.
import { type ChildProcess, spawn } from "node:child_process";
import { join } from "node:path";
import { createInterface } from "node:readline";

/** Port + session token announced by the engine's `engine.listening` line. */
export interface EngineConnection {
  port: number;
  token: string;
}

const START_TIMEOUT_MS = 60_000;

/** Parse one stdout line; returns the connection for an `engine.listening` event, else null. */
export function parseListeningLine(line: string): EngineConnection | null {
  let message: unknown;
  try {
    message = JSON.parse(line);
  } catch {
    return null; // not the announcement (e.g. a log line)
  }
  if (typeof message !== "object" || message === null) return null;
  const { event, port, token } = message as Record<string, unknown>;
  if (event !== "engine.listening" || typeof port !== "number" || typeof token !== "string") {
    return null;
  }
  return { port, token };
}

/** Python interpreter of the repository's uv environment (`uv sync` creates `.venv`). */
function devPython(repoRoot: string): string {
  return process.platform === "win32"
    ? join(repoRoot, ".venv", "Scripts", "python.exe")
    : join(repoRoot, ".venv", "bin", "python");
}

/** A started engine: its connection (once announced) and a way to stop it. */
export interface DevEngine {
  connection: Promise<EngineConnection>;
  stop(): void;
}

/** Start the dev engine from `repoRoot`; `connection` resolves when it announces port + token. */
export function startDevEngine(repoRoot: string): DevEngine {
  // Step 1: spawn the engine; stderr (uvicorn logs) goes to this terminal.
  const child: ChildProcess = spawn(devPython(repoRoot), ["-m", "vibechem_engine.api"], {
    cwd: repoRoot,
    env: { ...process.env, VIBECHEM_DEV: "1" },
    stdio: ["ignore", "pipe", "inherit"],
    windowsHide: true,
  });

  // Step 2: wait for the one `engine.listening` line, or fail on exit/timeout.
  const connection = new Promise<EngineConnection>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`engine did not start within ${START_TIMEOUT_MS / 1000} s`));
    }, START_TIMEOUT_MS);
    child.once("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.once("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`engine exited with code ${String(code)} before it was ready`));
    });
    if (child.stdout === null) throw new Error("engine stdout is not piped");
    createInterface({ input: child.stdout }).on("line", (line) => {
      const announced = parseListeningLine(line);
      if (announced !== null) {
        clearTimeout(timer);
        resolve(announced);
      }
    });
  });

  return {
    connection,
    stop: () => {
      if (child.exitCode === null) child.kill();
    },
  };
}
