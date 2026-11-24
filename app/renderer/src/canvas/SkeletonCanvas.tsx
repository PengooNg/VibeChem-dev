// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/canvas/SkeletonCanvas.tsx — walking-skeleton canvas: two fixed blocks, Dataset → SNV.
//
// The real editable pipeline canvas comes in Phase 4; here nothing can be moved or connected.
import "@xyflow/react/dist/style.css";

import { Background, type Edge, ReactFlow } from "@xyflow/react";
import { useTranslation } from "react-i18next";

import datasetGlyph from "@/ui/glyphs/dataset.svg";
import snvGlyph from "@/ui/glyphs/snv.svg";

import { BlockNode, type BlockNodeType, type RunState } from "./BlockNode";

const NODE_TYPES = { block: BlockNode };
const EDGES: Edge[] = [{ id: "e-dataset-snv", source: "dataset", target: "snv" }];

interface SkeletonCanvasProps {
  state: RunState;
  /** Spectra × points of the output, once a run is done. */
  shape?: { rows: number; cols: number };
}

export function SkeletonCanvas({ state, shape }: SkeletonCanvasProps) {
  const { t } = useTranslation();
  const nodes: BlockNodeType[] = [
    {
      id: "dataset",
      type: "block",
      ariaLabel: t("blocks.data.dataset.title"),
      position: { x: 0, y: 0 },
      data: {
        titleKey: "blocks.data.dataset.title",
        summary: t("datasets.gasoline_nir"),
        blockClass: "data",
        glyph: datasetGlyph,
        state,
        input: false,
        output: true,
      },
    },
    {
      id: "snv",
      type: "block",
      ariaLabel: t("blocks.preprocess.snv.title"),
      position: { x: 260, y: 0 },
      data: {
        titleKey: "blocks.preprocess.snv.title",
        tipKey: "blocks.preprocess.snv.tip",
        summary: t("blocks.preprocess.snv.summary"),
        blockClass: "preprocess",
        glyph: snvGlyph,
        state,
        input: true,
        output: false,
        ...(state === "done" && shape !== undefined
          ? { dataHere: t("canvas.data_here", { rows: shape.rows, cols: shape.cols }) }
          : {}),
      },
    },
  ];
  return (
    <ReactFlow
      aria-label={t("canvas.label")}
      nodes={nodes}
      edges={EDGES}
      nodeTypes={NODE_TYPES}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      fitView
      fitViewOptions={{ padding: 0.4, maxZoom: 1.25 }}
    >
      <Background gap={16} size={1} color="var(--border)" />
    </ReactFlow>
  );
}
