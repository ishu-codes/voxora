import { DashedPanel } from "./DashedPanel";
import { Reveal } from "./Reveal";
import { Section, SectionHeader } from "./Section";
import { LATENCY_COPY, LATENCY_PROPS } from "./sections";

export function LatencyStats() {
  return (
    <Section id="latency" className="bg-background">
      <SectionHeader
        heading={LATENCY_COPY.heading}
        subhead={LATENCY_COPY.subhead}
      />

      <div className="mt-14 grid gap-6 sm:grid-cols-3">
        {LATENCY_PROPS.map((stat, index) => (
          <Reveal key={stat.label} delay={index * 80}>
            <DashedPanel className="flex flex-col items-center bg-card p-8 text-center">
              <span className="font-mono text-4xl font-semibold tracking-tight tabular-nums sm:text-5xl">
                {stat.value}
              </span>
              <span className="mt-3 font-mono text-xs uppercase tracking-widest text-muted-foreground">
                {stat.label}
              </span>
            </DashedPanel>
          </Reveal>
        ))}
      </div>
    </Section>
  );
}
