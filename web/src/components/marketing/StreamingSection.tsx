import { DashedPanel } from "./DashedPanel";
import { Reveal } from "./Reveal";
import { Section, SectionHeader } from "./Section";
import { STREAMING_COPY } from "./sections";

export function StreamingSection() {
  return (
    <Section className="bg-muted/20">
      <SectionHeader
        heading={STREAMING_COPY.heading}
        subhead={STREAMING_COPY.subhead}
        className="mx-auto text-center"
      />

      <div className="mt-14 grid gap-6 lg:grid-cols-2">
        <Reveal direction="left">
          <DashedPanel className="flex h-full flex-col bg-card p-6 sm:p-8">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
                {STREAMING_COPY.without.label}
              </span>
              <div className="flex gap-1.5">
                {STREAMING_COPY.without.badges.map((badge) => (
                  <span
                    key={badge}
                    className="rounded-full border border-border bg-muted px-2.5 py-0.5 font-mono text-[10px] text-muted-foreground"
                  >
                    {badge}
                  </span>
                ))}
              </div>
            </div>
            <p className="mt-6 text-sm leading-relaxed text-muted-foreground sm:text-base">
              {STREAMING_COPY.without.answer}
            </p>
          </DashedPanel>
        </Reveal>

        <Reveal direction="right" delay={100}>
          <DashedPanel className="flex h-full flex-col bg-card p-6 ring-1 ring-brand/30 sm:p-8">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs uppercase tracking-widest text-brand-text">
                {STREAMING_COPY.with.label}
              </span>
              <div className="flex gap-1.5">
                {STREAMING_COPY.with.badges.map((badge) => (
                  <span
                    key={badge}
                    className="rounded-full border border-brand/30 bg-brand/10 px-2.5 py-0.5 font-mono text-[10px] text-brand-text"
                  >
                    {badge}
                  </span>
                ))}
              </div>
            </div>
            <p className="mt-6 text-sm leading-relaxed text-foreground sm:text-base">
              {STREAMING_COPY.with.answer}
            </p>
          </DashedPanel>
        </Reveal>
      </div>
    </Section>
  );
}
