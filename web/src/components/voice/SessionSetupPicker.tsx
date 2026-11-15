"use client";

import { ChevronDownIcon, Settings2Icon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverHeader,
  PopoverTitle,
  PopoverTrigger,
} from "@/components/ui/popover";
import type { Scenario } from "@/lib/scenarios";
import type { ProviderChoice } from "@/lib/voice-providers";
import { ProviderSelector } from "./ProviderSelector";
import { ScenarioPicker } from "./ScenarioPicker";

type SessionSetupPickerProps = {
  scenarios: Scenario[];
  scenarioId: string;
  onScenarioChange: (scenarioId: string) => void;
  sttProvider: string;
  sttChoices: ProviderChoice[];
  onSttProviderChange: (provider: string) => void;
  ttsProvider: string;
  ttsChoices: ProviderChoice[];
  onTtsProviderChange: (provider: string) => void;
  disabled?: boolean;
};

export function SessionSetupPicker({
  scenarios,
  scenarioId,
  onScenarioChange,
  sttProvider,
  sttChoices,
  onSttProviderChange,
  ttsProvider,
  ttsChoices,
  onTtsProviderChange,
  disabled = false,
}: SessionSetupPickerProps) {
  const selected = scenarios.find((scenario) => scenario.id === scenarioId);

  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            disabled={disabled}
            className="h-9 max-w-[240px] justify-between gap-2 rounded-full px-3 text-sm font-normal text-muted-foreground hover:text-foreground"
          />
        }
      >
        <span className="flex min-w-0 items-center gap-2">
          <Settings2Icon className="size-4 shrink-0" />
          <span className="truncate">
            {selected?.title ?? "Conversation setup"}
          </span>
        </span>
        <ChevronDownIcon className="size-4 shrink-0 opacity-60" />
      </PopoverTrigger>
      <PopoverContent
        align="end"
        side="bottom"
        sideOffset={8}
        className="w-[min(36rem,calc(100vw-1rem))] gap-5 p-4 sm:p-5"
      >
        <PopoverHeader>
          <PopoverTitle>Conversation setup</PopoverTitle>
          <PopoverDescription>
            Pick the scenario and the speech providers for the next call.
          </PopoverDescription>
        </PopoverHeader>

        <ScenarioPicker
          scenarios={scenarios}
          value={scenarioId}
          onChange={onScenarioChange}
          disabled={disabled}
        />

        <div className="grid gap-3 border-t border-border/70 pt-4 sm:grid-cols-2">
          <ProviderSelector
            label="Speech recognition"
            value={sttProvider}
            choices={sttChoices}
            onChange={onSttProviderChange}
            disabled={disabled}
          />
          <ProviderSelector
            label="Voice synthesis"
            value={ttsProvider}
            choices={ttsChoices}
            onChange={onTtsProviderChange}
            disabled={disabled}
          />
        </div>
      </PopoverContent>
    </Popover>
  );
}
