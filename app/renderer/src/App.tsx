// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/App.tsx — walking-skeleton window: top bar with Run, canvas, spectra previews.
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { EngineRequestError, type Spectra } from "./api/client";
import { PREVIEW_WIDTH, useSkeletonRun } from "./api/useSkeletonRun";
import type { RunState } from "./canvas/BlockNode";
import { SkeletonCanvas } from "./canvas/SkeletonCanvas";
import { SpectraPlot } from "./plots/SpectraPlot";

function errorText(error: Error, t: TFunction): string {
  return error instanceof EngineRequestError && error.status > 0
    ? t("errors.engine.request_failed", { status: error.status })
    : t("errors.engine.unreachable");
}

interface PreviewProps {
  titleKey: string;
  yLabelKey: string;
  spectra: Spectra | undefined;
}

function Preview({ titleKey, yLabelKey, spectra }: PreviewProps) {
  const { t } = useTranslation();
  return (
    <section aria-label={t(titleKey)} className="bg-surface min-w-0 rounded-lg border p-3">
      <h2 className="mb-2 text-[13px] font-semibold">{t(titleKey)}</h2>
      {spectra === undefined ? (
        <p className="text-muted-foreground flex h-60 items-center justify-center text-center">
          {t("plots.empty")}
        </p>
      ) : (
        <SpectraPlot spectra={spectra} xLabel={t("plots.wavelength_nm")} yLabel={t(yLabelKey)} />
      )}
    </section>
  );
}

export function App() {
  const { t } = useTranslation();
  const run = useSkeletonRun();
  const state: RunState = run.isPending
    ? "running"
    : run.isError
      ? "error"
      : run.isSuccess
        ? "done"
        : "idle";
  const snv = run.data?.snv;
  // The preview has the true number of points only when it was not decimated.
  const shape =
    snv !== undefined && snv.x.length < PREVIEW_WIDTH
      ? { rows: snv.y.length, cols: snv.x.length }
      : undefined;

  return (
    <div className="flex h-screen flex-col">
      <header className="bg-surface flex h-12 shrink-0 items-center gap-3 border-b px-4">
        <h1 className="text-base font-semibold">{t("app.name")}</h1>
        <span className="text-muted-foreground truncate">{t("pipeline.skeleton")}</span>
        <div className="ml-auto flex items-center gap-3">
          {run.error !== null && (
            <p role="alert" className="text-state-error">
              {errorText(run.error, t)}
            </p>
          )}
          <button
            type="button"
            onClick={() => {
              run.mutate();
            }}
            disabled={run.isPending}
            className="bg-primary text-primary-foreground focus-visible:ring-ring inline-flex h-8 items-center gap-1.5 rounded-md px-3 font-medium focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:outline-none disabled:opacity-60"
          >
            <span aria-hidden>▶</span>
            {run.isPending ? t("toolbar.running") : t("toolbar.run")}
          </button>
        </div>
      </header>
      <main className="flex min-h-0 flex-1 flex-col">
        <div className="min-h-48 flex-1">
          <SkeletonCanvas state={state} {...(shape === undefined ? {} : { shape })} />
        </div>
        <div className="bg-background grid shrink-0 grid-cols-1 gap-3 border-t p-3 lg:grid-cols-2">
          <Preview titleKey="plots.raw" yLabelKey="plots.log_inv_r" spectra={run.data?.raw} />
          <Preview titleKey="plots.snv" yLabelKey="plots.snv_value" spectra={snv} />
        </div>
      </main>
    </div>
  );
}
