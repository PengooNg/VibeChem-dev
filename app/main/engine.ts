// SPDX-License-Identifier: GPL-3.0-or-later
// app/main/engine.ts — start the engine and read its port + token (DATA_MODEL.md §1).
//
// Development: `python -m vibechem_engine.api` from the repository's uv environment with
// VIBECHEM_DEV=1 (T0.10). Packaged app: the PyInstaller engine bundle that electron-builder
// copies into the app's resources, plus the bundled testdata/ (T0.11). Restart after a crash
// and the F-84 banner are not part of the walking skeleton.
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

/** How to launch the engine process. */
export interface EngineCommand {
  file: string;
  args: string[];
  cwd: string;
  env: NodeJS.ProcessEnv;
}

/** Development: the repository's uv environment (`uv sync` creates `.venv`), dev mode on. */
export function devEngineCommand(
  repoRoot: string,
  platform: NodeJS.Platform,
  env: NodeJS.ProcessEnv,
): EngineCommand {
  const python =
    platform === "win32"
      ? join(repoRoot, ".venv", "Scripts", "python.exe")
      : join(repoRoot, ".venv", "bin", "python");
  return {
    file: python,
    args: ["-m", "vibechem_engine.api"],
    cwd: repoRoot,
    env: { ...env, VIBECHEM_DEV: "1" },
  };
}

/**
 * Packaged app: `<resources>/engine/vibechem-engine[.exe]` with `<resources>/testdata`
 * (electron-builder.yml `extraResources`). Dev mode is forced off, so only the app origin passes.
 */
export function packagedEngineCommand(
  resourcesPath: string,
  platform: NodeJS.Platform,
  env: NodeJS.ProcessEnv,
): EngineCommand {
  const engineDir = join(resourcesPath, "engine");
  const productionEnv = { ...env };
  delete productionEnv["VIBECHEM_DEV"];
  return {
    file: join(engineDir, platform === "win32" ? "vibechem-engine.exe" : "vibechem-engine"),
    args: ["--testdata-dir", join(resourcesPath, "testdata")],
    cwd: engineDir,
    env: productionEnv,
  };
}

/** A started engine: its connection (once announced) and a way to stop it. */
export interface Engine {
  connection: Promise<EngineConnection>;
  stop(): void;
}

/** Start the engine; `connection` resolves when it announces port + token. */
export function startEngine(command: EngineCommand): Engine {
  // Step 1: spawn the engine; stderr (uvicorn logs) goes to this process's stderr.
  const child: ChildProcess = spawn(command.file, command.args, {
    cwd: command.cwd,
    env: command.env,
    stdio: ["ignore", "pipe", "inherit"],
    windowsHide: true,
  });

  // Step 2: wait for the one `engine.listening` line, or fail on exit/timeout.
  const connection = new Promise<EngineConnection>((resolve, reject) => {
    const timer = setTimeout(() => {
      child.kill(); // don't leave a late-starting engine behind
      reject(new Error(`engine did not start within ${START_TIMEOUT_MS / 1000} s`));
    }, START_TIMEOUT_MS);
    child.once("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.once("exit", (code) => {
      clearTimeout(timer);
      // Before the announcement this rejects; after it, the promise is settled and only the log
      // remains (no restart in the walking skeleton).
      console.error(`[engine] exited with code ${String(code)}`);
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
