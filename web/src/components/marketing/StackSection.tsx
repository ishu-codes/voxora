import { DashedPanel } from "./DashedPanel";
import { Reveal } from "./Reveal";
import { Section, SectionHeader } from "./Section";
import { STACK_COPY, STACK_ITEMS } from "./sections";

export function StackSection() {
  return (
    <Section id="stack" className="bg-background">
      <SectionHeader
        heading={STACK_COPY.heading}
        subhead={STACK_COPY.subhead}
      />

      <div className="mt-14 space-y-3">
        {STACK_ITEMS.map((item, index) => (
          <Reveal key={item.slot} delay={index * 50}>
            <DashedPanel className="flex flex-col gap-3 bg-card px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
              <div className="flex items-center gap-4">
                <span className="rounded-full border border-border bg-muted px-3 py-1 font-mono text-xs font-semibold text-foreground">
                  {item.slot}
                </span>
                <span className="text-sm font-medium text-foreground sm:text-base">
                  {item.options}
                </span>
              </div>
              <span className="font-mono text-xs text-muted-foreground">
                {item.detail}
              </span>
            </DashedPanel>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}
