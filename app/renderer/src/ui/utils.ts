// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/ui/utils.ts — class-name helper used by shadcn/ui components.
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Join class names and let later Tailwind classes override earlier ones. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
