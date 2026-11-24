// SPDX-License-Identifier: GPL-3.0-or-later
// app/main/appOrigin.ts — the `app://vibechem` origin of the built renderer (pure helpers).
//
// A `file://` page sends `Origin: null`, which the engine rejects (DATA_MODEL.md §1). The
// built renderer is therefore served from a standard, secure custom scheme (index.ts), so its
// origin is exactly `app://vibechem` — the one production origin the engine allows.
import { isAbsolute, relative, resolve } from "node:path";

export const APP_SCHEME = "app";
export const APP_HOST = "vibechem";
/** Origin of the packaged renderer; must equal `APP_ORIGIN` in the engine's security.py. */
export const APP_ORIGIN = `${APP_SCHEME}://${APP_HOST}`;

/**
 * File inside `rootDir` for an `app://vibechem/...` URL, or null for another host, a path
 * outside `rootDir` (e.g. encoded `..`), or a malformed URL. `/` maps to `index.html`.
 */
export function resolveAppFile(rootDir: string, url: string): string | null {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (parsed.protocol !== `${APP_SCHEME}:` || parsed.host !== APP_HOST) return null;
  let pathname: string;
  try {
    pathname = decodeURIComponent(parsed.pathname);
  } catch {
    return null; // malformed percent-encoding
  }
  if (pathname.includes("\0")) return null;
  const root = resolve(rootDir);
  const file = resolve(root, `.${pathname === "/" ? "/index.html" : pathname}`);
  const inside = relative(root, file);
  if (inside === "" || inside.startsWith("..") || isAbsolute(inside)) return null;
  return file;
}

/**
 * True when an IPC message comes from our own page: the `app://vibechem` renderer, or — in
 * development only — the Vite dev server page (`devServerUrl`).
 */
export function isTrustedSenderUrl(senderUrl: string, devServerUrl: string | null): boolean {
  let sender: URL;
  try {
    sender = new URL(senderUrl);
  } catch {
    return false;
  }
  // Node's URL gives a custom scheme the origin "null", so compare scheme and host.
  if (sender.protocol === `${APP_SCHEME}:` && sender.host === APP_HOST) return true;
  if (devServerUrl === null) return false;
  try {
    return sender.origin === new URL(devServerUrl).origin;
  } catch {
    return false;
  }
}
