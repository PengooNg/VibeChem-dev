// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/plots/SpectraPlot.tsx — all spectra as lines on one uPlot canvas (UI_GUIDE.md §2.4).
import "uplot/dist/uPlot.min.css";

import { useEffect, useRef } from "react";
import uPlot from "uplot";

import type { Spectra } from "@/api/client";

/** One colour for every spectrum: viridis at 0.5, semi-transparent so overlaps read as density. */
const LINE = "rgba(33, 145, 140, 0.55)";
const HEIGHT = 240;

interface SpectraPlotProps {
  spectra: Spectra;
  xLabel: string;
  yLabel: string;
}

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function SpectraPlot({ spectra, xLabel, yLabel }: SpectraPlotProps) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = container.current;
    if (element === null) return;
    // Step 1: axes in the UI chrome colours (plots inherit --surface and --border, no chart junk).
    const axis = {
      stroke: token("--text-muted"),
      grid: { stroke: token("--border"), width: 1 },
      ticks: { stroke: token("--border"), width: 1 },
      font: `12px ${token("--font-ui")}`,
      labelFont: `12px ${token("--font-ui")}`,
    };
    // Step 2: one series per spectrum, no legend (dozens of lines), no point markers.
    const plot = new uPlot(
      {
        width: element.clientWidth,
        height: HEIGHT,
        legend: { show: false },
        cursor: { points: { show: false } },
        scales: { x: { time: false } },
        axes: [
          { ...axis, label: xLabel },
          { ...axis, label: yLabel, size: 56 },
        ],
        series: [{}, ...spectra.y.map(() => ({ stroke: LINE, width: 1, points: { show: false } }))],
      },
      [spectra.x, ...spectra.y],
      element,
    );
    // Step 3: follow the panel width.
    const observer = new ResizeObserver(() => {
      plot.setSize({ width: element.clientWidth, height: HEIGHT });
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
      plot.destroy();
    };
  }, [spectra, xLabel, yLabel]);

  return <div ref={container} className="w-full" />;
}
