"use client";

import { cn } from "@/lib/utils";
import type { ProviderChoice } from "@/lib/voice-providers";

type ProviderSelectorProps = {
  label: string;
  value: string;
  choices: ProviderChoice[];
  onChange: (provider: string) => void;
  disabled?: boolean;
  className?: string;
};

export function ProviderSelector({
  label,
  value,
  choices,
  onChange,
  disabled = false,
  className,
}: ProviderSelectorProps) {
  return (
    <label className={cn("flex min-w-0 flex-col gap-1.5", className)}>
      <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled || choices.length === 0}
        className="h-9 min-w-0 rounded-full border border-border/70 bg-background/70 px-3 text-sm text-foreground outline-none transition-colors focus-visible:border-brand/60 focus-visible:ring-2 focus-visible:ring-brand/20 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {choices.map((choice) => (
          <option
            key={choice.id}
            value={choice.id}
            disabled={!choice.available}
          >
            {choice.name} · {choice.model}
            {!choice.available ? " (key missing)" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
