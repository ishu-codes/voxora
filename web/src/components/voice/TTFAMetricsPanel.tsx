"use client";

import { DownloadIcon, RotateCcwIcon } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  calculateTTFAStats,
  type TTFAStages,
  type TurnMetricRecord,
} from "@/lib/metrics";

type TTFAMetricsPanelProps = {
  records: TurnMetricRecord[];
  onReset: () => void;
};

function formatMs(value: number | null): string {
  return value == null ? "Unavailable" : `${Math.round(value)} ms`;
}

function recordLabel(record: TurnMetricRecord): string {
  if (record.status === "interrupted") return "Interrupted";
  if (record.status === "failed") return "Failed";
  if (record.coldStart) return "Cold start";
  return record.mode === "backend" ? "Backend" : "BYOK";
}

export function TTFAMetricsPanel({ records, onReset }: TTFAMetricsPanelProps) {
  const [includeColdStart, setIncludeColdStart] = useState(false);
  const stats = useMemo(
    () => calculateTTFAStats(records, { includeColdStart }),
    [includeColdStart, records],
  );
  const recent = records.slice(-6).reverse();
  const stages: Array<[string, keyof TTFAStages]> = [
    ["STT", "sttMs"],
    ["LLM", "llmMs"],
    ["TTS", "ttsMs"],
    ["Playback", "playbackMs"],
  ];

  const exportRecords = () => {
    const blob = new Blob([JSON.stringify(records, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `voxora-ttfa-${new Date().toISOString()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section
      aria-label="Time to first audio metrics"
      className="min-h-full bg-sidebar"
    >
      <div className="space-y-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Time to first audio
            </p>
            <p className="mt-1 text-2xl font-semibold tabular-nums">
              {formatMs(stats.lastTurn?.ttfaMs ?? null)}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Last turn
              {stats.lastTurn
                ? ` · ${stats.lastTurn.mode === "backend" ? "Backend" : "BYOK"}${
                    stats.lastTurn.coldStart ? " · cold start" : ""
                  }`
                : ""}
            </p>
          </div>
          <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={includeColdStart}
              onChange={(event) => setIncludeColdStart(event.target.checked)}
              className="size-3.5 accent-primary"
            />
            Include cold start
          </label>
        </div>

        <div className="grid grid-cols-3 gap-x-3 gap-y-3 border-y border-border py-3">
          {[
            ["Mean", stats.mean],
            ["Median", stats.median],
            ["p95", stats.p95],
            ["Min", stats.min],
            ["Max", stats.max],
          ].map(([label, value]) => (
            <div key={label as string}>
              <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground">
                {label}
              </p>
              <p className="mt-0.5 text-sm font-medium tabular-nums">
                {formatMs(value as number | null)}
              </p>
            </div>
          ))}
          <div>
            <p className="font-mono text-[9px] uppercase tracking-[0.16em] text-muted-foreground">
              Counted
            </p>
            <p className="mt-0.5 text-sm font-medium tabular-nums">
              {stats.count} turns
            </p>
          </div>
        </div>

        <p className="text-xs text-muted-foreground">
          Excluded: {stats.excluded.total} turns ({stats.excluded.interrupted}{" "}
          interrupted, {stats.excluded.failed} failed,{" "}
          {stats.excluded.coldStart} cold start)
        </p>

        <div>
          <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Average stage breakdown
          </p>
          <table className="w-full text-xs">
            <caption className="sr-only">
              Average duration of each time-to-first-audio stage
            </caption>
            <tbody>
              {stages.map(([label, key]) => (
                <tr
                  key={key}
                  className="border-t border-border/70 first:border-t-0"
                >
                  <th
                    scope="row"
                    className="py-1.5 text-left font-normal text-muted-foreground"
                  >
                    {label}
                  </th>
                  <td className="py-1.5 text-right font-medium tabular-nums">
                    {formatMs(stats.stages[key])}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              Recent turns
            </p>
            <span className="text-[11px] text-muted-foreground">
              TTFA trend
            </span>
          </div>
          {recent.length ? (
            <ol className="space-y-1.5">
              {recent.map((record) => (
                <li
                  key={record.turnId}
                  className="flex items-center justify-between gap-3 text-xs"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span
                      className="size-1.5 shrink-0 rounded-full bg-brand-text"
                      aria-hidden="true"
                    />
                    <span className="truncate text-muted-foreground">
                      {recordLabel(record)} · {record.sttProvider}
                    </span>
                  </span>
                  <span className="shrink-0 font-medium tabular-nums">
                    {formatMs(record.ttfaMs)}
                  </span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-xs text-muted-foreground">
              Complete one spoken turn to collect TTFA. Empty transcripts,
              interrupted turns, and failures are excluded.
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onReset}
            disabled={records.length === 0}
          >
            <RotateCcwIcon />
            Reset stats
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={exportRecords}
            disabled={records.length === 0}
          >
            <DownloadIcon />
            Export JSON
          </Button>
        </div>
      </div>
    </section>
  );
}
