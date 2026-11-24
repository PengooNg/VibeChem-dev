// SPDX-License-Identifier: GPL-3.0-or-later
// app/renderer/src/canvas/BlockNode.tsx — one block on the canvas (UI_GUIDE.md §6 block anatomy).
//
// Walking-skeleton version: class stripe, placeholder glyph, title, one-line summary,
// state dot with its label, and ● spectra ports. Not connectable (the graph is fixed).
import { Handle, type Node, type NodeProps, Position } from "@xyflow/react";
import { useTranslation } from "react-i18next";

import { cn } from "@/ui/utils";

export type RunState = "idle" | "running" | "done" | "error";
export type BlockClass = "data" | "preprocess";

export type BlockNodeData = {
  titleKey: string;
  tipKey?: string;
  summary: string;
  blockClass: BlockClass;
  glyph: string; // URL of the glyph SVG (drawn as a mask so it takes the class tint)
  state: RunState;
  input: boolean;
  output: boolean;
  dataHere?: string; // "Data here" marker text under the furthest done block (UI_GUIDE.md §2.3)
};

export type BlockNodeType = Node<BlockNodeData, "block">;

const STATE_DOT: Record<RunState, string> = {
  idle: "bg-muted-foreground",
  running: "bg-focus motion-safe:animate-pulse",
  done: "bg-state-done",
  error: "bg-state-error",
};

const PORT = "!size-2.5 !rounded-full !border-[1.5px] !border-muted-foreground !bg-surface";

export function BlockNode({ data }: NodeProps<BlockNodeType>) {
  const { t } = useTranslation();
  const tint = `var(--block-${data.blockClass})`;
  return (
    <div className="relative">
      <div
        title={data.tipKey === undefined ? undefined : t(data.tipKey)}
        className={cn(
          "bg-surface relative flex w-44 items-center gap-2 overflow-hidden rounded-lg border py-2 pr-3 pl-4",
          data.state === "error" ? "border-state-error" : "border-border",
        )}
      >
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 w-[3px]"
          style={{ background: tint }}
        />
        <span
          aria-hidden
          className="size-6 shrink-0"
          style={{
            background: tint,
            mask: `url("${data.glyph}") center / contain no-repeat`,
          }}
        />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-semibold">{t(data.titleKey)}</span>
          <span className="text-muted-foreground block truncate font-mono text-xs">
            {data.summary}
          </span>
        </span>
        <span
          role="img"
          aria-label={t(`state.${data.state}`)}
          title={t(`state.${data.state}`)}
          className={cn("size-2 shrink-0 rounded-full", STATE_DOT[data.state])}
        />
      </div>
      {data.input && (
        <Handle type="target" position={Position.Left} isConnectable={false} className={PORT} />
      )}
      {data.output && (
        <Handle type="source" position={Position.Right} isConnectable={false} className={PORT} />
      )}
      {data.dataHere !== undefined && (
        <span className="bg-surface border-border text-muted-foreground absolute top-full left-1/2 mt-2 -translate-x-1/2 rounded-full border px-2 py-0.5 text-xs whitespace-nowrap">
          <span aria-hidden className="text-state-done">
            ●{" "}
          </span>
          {data.dataHere}
        </span>
      )}
    </div>
  );
}
