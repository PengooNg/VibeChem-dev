// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/api/useSkeletonRun.ts — Run button action: raw and SNV spectra of the skeleton dataset.
import { useMutation } from "@tanstack/react-query";

import { getEngineConnection, runSkeleton, type Spectra } from "./client";

/** Preview width in points; the engine decimates spectra with more points (DATA_MODEL.md §2.12). */
export const PREVIEW_WIDTH = 1200;

export interface SkeletonResult {
  raw: Spectra;
  snv: Spectra;
}

/** The skeleton always runs Dataset (gasoline NIR) → SNV; previews are decimated to PREVIEW_WIDTH points. */
export function useSkeletonRun() {
  return useMutation({
    mutationFn: async (): Promise<SkeletonResult> => {
      const connection = await getEngineConnection();
      const request = { dataset: "gasoline_nir", width: PREVIEW_WIDTH } as const;
      const [raw, snv] = await Promise.all([
        runSkeleton(connection, { ...request, apply_snv: false }),
        runSkeleton(connection, { ...request, apply_snv: true }),
      ]);
      return { raw, snv };
    },
  });
}
