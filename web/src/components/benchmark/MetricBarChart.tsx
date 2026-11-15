"use client";

import { cn } from "@/lib/utils";

export type MetricBar = {
  label: string;
  value: number | null;
  detail?: string;
};

type MetricBarChartProps = {
  bars: MetricBar[];
  formatValue: (value: number) => string;
  emptyLabel?: string;
};

export function MetricBarChart({
  bars,
  formatValue,
  emptyLabel = "No measured values.",
}: MetricBarChartProps) {
  const present = bars.filter(
    (bar): bar is MetricBar & { value: number } => bar.value !== null,
  );
  const maximum = Math.max(...present.map((bar) => bar.value), 1);

  if (!present.length) {
    return (
      <p className="rounded-xl border border-dashed border-border px-4 py-8 text-sm text-muted-foreground">
        {emptyLabel}
      </p>
    );
  }

  return (
    <div className="space-y-3" role="img" aria-label="Benchmark metric chart">
      {present.map((bar) => (
        <div
          key={bar.label}
          className="grid grid-cols-[minmax(9rem,1fr)_minmax(7rem,3fr)_4.5rem] items-center gap-3"
        >
          <span className="truncate text-xs text-muted-foreground">
            {bar.label}
          </span>
          <span className="h-2 overflow-hidden rounded-full bg-muted">
            <span
              className={cn(
                "block h-full min-w-px rounded-full bg-brand/75",
                bar.value === maximum && "bg-brand",
              )}
              style={{ width: `${(bar.value / maximum) * 100}%` }}
            />
          </span>
          <span
            className="text-right font-mono text-xs tabular-nums text-foreground"
            title={bar.detail}
          >
            {formatValue(bar.value)}
          </span>
        </div>
      ))}
    </div>
  );
}
