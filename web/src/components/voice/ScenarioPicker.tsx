"use client";

import { ArrowUpRightIcon } from "lucide-react";
import type { Scenario } from "@/lib/scenarios";
import { cn } from "@/lib/utils";

type ScenarioPickerProps = {
  scenarios: Scenario[];
  value?: string;
  onChange: (scenarioId: string) => void;
  disabled?: boolean;
};

export function ScenarioPicker({
  scenarios,
  value,
  onChange,
  disabled = false,
}: ScenarioPickerProps) {
  return (
    <fieldset className="grid w-full gap-2 sm:grid-cols-3" disabled={disabled}>
      <legend className="mb-2 text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
        Choose a conversation
      </legend>
      {scenarios.map((scenario) => {
        const selected = scenario.id === value;
        return (
          <button
            key={scenario.id}
            type="button"
            aria-pressed={selected}
            onClick={() => onChange(scenario.id)}
            className={cn(
              "group min-h-24 rounded-2xl border px-3.5 py-3 text-left transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30",
              selected
                ? "border-brand/55 bg-brand/8"
                : "border-border/70 bg-background/45 hover:border-border hover:bg-muted/25",
              disabled && "cursor-not-allowed opacity-55",
            )}
          >
            <span className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-foreground">
                {scenario.title}
              </span>
              <ArrowUpRightIcon
                className={cn(
                  "size-3.5 transition-transform",
                  selected
                    ? "text-brand"
                    : "text-muted-foreground group-hover:-translate-y-0.5 group-hover:translate-x-0.5",
                )}
              />
            </span>
            <span className="mt-1.5 block text-xs leading-5 text-muted-foreground">
              {scenario.description}
            </span>
            <span className="mt-2 block text-[10px] uppercase tracking-[0.14em] text-muted-foreground/80">
              {scenario.outbound ? "Outbound" : "Inbound"} ·{" "}
              {scenario.language_hint}
            </span>
          </button>
        );
      })}
    </fieldset>
  );
}
