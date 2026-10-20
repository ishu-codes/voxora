"use client";

import { ChevronsUpDown } from "lucide-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export type VoiceOption = {
  voiceId: string;
  name: string;
  labels?: {
    accent?: string;
    gender?: string;
    age?: string;
    description?: string;
    "use case"?: string;
  };
  previewUrl?: string;
};

interface VoicePickerProps {
  voices: VoiceOption[];
  value?: string;
  onValueChange?: (value: string) => void;
  placeholder?: string;
  className?: string;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  disabled?: boolean;
  triggerVariant?: "outline" | "ghost";
}

function VoiceDot({
  className,
  pulse,
}: {
  className?: string;
  pulse?: boolean;
}) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block shrink-0 rounded-full bg-[radial-gradient(circle_at_35%_30%,var(--brand-text),var(--brand))] shadow-[inset_0_0_6px_rgba(255,255,255,0.45)]",
        pulse && "animate-pulse",
        className,
      )}
    />
  );
}

function VoicePicker({
  voices,
  value,
  onValueChange,
  placeholder = "Select a voice…",
  className,
  open,
  onOpenChange,
  disabled = false,
  triggerVariant = "outline",
}: VoicePickerProps) {
  const [internalOpen, setInternalOpen] = React.useState(false);
  const isControlled = open !== undefined;
  const isOpen = isControlled ? open : internalOpen;
  const setIsOpen = isControlled ? onOpenChange : setInternalOpen;

  const selectedVoice = voices.find((voice) => voice.voiceId === value);

  const handleOpenChange = (next: boolean) => {
    if (disabled && next) return;
    setIsOpen?.(next);
  };

  return (
    <Popover open={isOpen} onOpenChange={handleOpenChange}>
      <PopoverTrigger
        render={
          <Button
            variant={triggerVariant}
            role="combobox"
            aria-expanded={isOpen}
            disabled={disabled}
            className={cn("w-full justify-between gap-2", className)}
          />
        }
      >
        {selectedVoice ? (
          <span className="flex min-w-0 items-center gap-2">
            <VoiceDot
              className="size-4"
              pulse={selectedVoice.voiceId !== "system"}
            />
            <span className="truncate">{selectedVoice.name}</span>
          </span>
        ) : (
          <span className="truncate text-muted-foreground">{placeholder}</span>
        )}
        <ChevronsUpDown className="ml-2 size-4 shrink-0 opacity-50" />
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 max-w-[calc(100vw-2rem)] p-0">
        <Command>
          <CommandInput placeholder="Search voices…" />
          <CommandList>
            <CommandEmpty>No voice found.</CommandEmpty>
            <CommandGroup>
              {voices.map((voice) => {
                const detail =
                  voice.labels?.description ??
                  [
                    voice.labels?.accent,
                    voice.labels?.gender,
                    voice.labels?.age,
                  ]
                    .filter(Boolean)
                    .join(" · ");

                return (
                  <CommandItem
                    key={voice.voiceId}
                    value={voice.voiceId}
                    keywords={[
                      voice.name,
                      voice.labels?.accent,
                      voice.labels?.gender,
                      voice.labels?.age,
                      voice.labels?.description,
                      voice.labels?.["use case"],
                    ].filter((keyword): keyword is string => Boolean(keyword))}
                    data-checked={voice.voiceId === value}
                    onSelect={() => onValueChange?.(voice.voiceId)}
                    className="flex items-center gap-3"
                  >
                    <VoiceDot className="size-7" />
                    <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                      <span className="truncate font-medium">{voice.name}</span>
                      {detail ? (
                        <span className="truncate text-xs text-muted-foreground">
                          {detail}
                        </span>
                      ) : null}
                    </span>
                  </CommandItem>
                );
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}

export { VoicePicker };
