import { useEffect, useState } from "react";
import { Section, SectionHeader } from "./Section";
import { Reveal } from "./Reveal";
import { PIPELINE_COPY, PIPELINE_TERMINAL } from "./sections";
import { cn } from "@/lib/utils";

export function PipelineSection() {
  const [visibleLines, setVisibleLines] = useState(0);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setVisibleLines(PIPELINE_TERMINAL.stream.length);
      return;
    }
    const timers: number[] = [];
    PIPELINE_TERMINAL.stream.forEach((_, index) => {
      timers.push(window.setTimeout(() => setVisibleLines(index + 1), 500 + index * 450));
    });
    return () => timers.forEach((timer) => window.clearTimeout(timer));
  }, []);

  return (
    <Section id="pipeline" className="bg-background">
      <div className="grid items-center gap-12 lg:grid-cols-2">
        <SectionHeader heading={PIPELINE_COPY.heading} subhead={PIPELINE_COPY.subhead} />
        <Reveal direction="right" delay={120}>
          <div className="relative overflow-hidden border border-border bg-card font-mono text-xs sm:text-sm">
            <div className="flex items-center gap-2 border-b border-border px-4 py-2.5">
              <span className="size-2.5 rounded-full bg-[#ff5f57]" />
              <span className="size-2.5 rounded-full bg-[#febc2e]" />
              <span className="size-2.5 rounded-full bg-[#28c840]" />
              <span className="ml-2 text-muted-foreground">voice session</span>
            </div>
            <div className="p-4 sm:p-5">
              <div className="text-muted-foreground">
                <span className="text-brand-text">$</span> {PIPELINE_TERMINAL.command}
              </div>
              <div className="mt-1 text-muted-foreground/80">{PIPELINE_TERMINAL.body}</div>
              <div className="mt-4 space-y-1.5">
                {PIPELINE_TERMINAL.stream.map((line, index) => (
                  <div
                    key={line}
                    className={cn(
                      "break-all text-foreground transition-all duration-500",
                      index < visibleLines ? "opacity-100" : "translate-y-1 opacity-0",
                    )}
                  >
                    <span className="text-brand-text/70">←</span> {line}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </Section>
  );
}
