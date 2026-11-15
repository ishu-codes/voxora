"use client";

import {
  AlertTriangleIcon,
  AudioLinesIcon,
  Clock3Icon,
  GaugeIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  type MetricBar,
  MetricBarChart,
} from "@/components/benchmark/MetricBarChart";
import { Navbar } from "@/components/navbar/Navbar";
import {
  type BenchmarkSummary,
  getBenchmarkSummary,
  type SttBenchmarkGroup,
  type TtsBenchmarkGroup,
} from "@/lib/benchmark";

function percent(value: number | null): string {
  return value == null ? "not run" : `${(value * 100).toFixed(1)}%`;
}

function milliseconds(value: number | null): string {
  return value == null ? "not run" : `${Math.round(value)} ms`;
}

function number(value: number | null, digits = 3): string {
  return value == null ? "not run" : value.toFixed(digits);
}

function mean(values: Array<number | null>): number | null {
  const present = values.filter((value): value is number => value !== null);
  if (!present.length) return null;
  return present.reduce((sum, value) => sum + value, 0) / present.length;
}

function combineStt(
  groups: SttBenchmarkGroup[],
  key: "wer_median" | "time_to_final_median_ms",
): MetricBar[] {
  const combined = new Map<string, Array<SttBenchmarkGroup["wer_median"]>>();
  for (const group of groups) {
    const label = `${group.provider} · ${group.condition}`;
    const values = combined.get(label) ?? [];
    values.push(group[key]);
    combined.set(label, values);
  }
  return Array.from(combined, ([label, values]) => ({
    label,
    value: mean(values),
    detail:
      key === "wer_median"
        ? "Average of language-level median WER"
        : "Average of language-level median time to final transcript",
  }));
}

function MetricSection({
  title,
  description,
  icon,
  children,
}: {
  title: string;
  description: string;
  icon: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="border-t border-border py-8 first:border-t-0 first:pt-0">
      <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold">
            {icon}
            {title}
          </h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            {description}
          </p>
        </div>
        <div className="min-w-0">{children}</div>
      </div>
    </section>
  );
}

function SttTable({ groups }: { groups: SttBenchmarkGroup[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[58rem] border-collapse text-left text-xs">
        <thead className="border-b border-border text-muted-foreground">
          <tr>
            <th className="py-2 pr-4 font-medium">Provider</th>
            <th className="py-2 pr-4 font-medium">Condition</th>
            <th className="py-2 pr-4 font-medium">Language</th>
            <th className="py-2 pr-4 text-right font-medium">Runs</th>
            <th className="py-2 pr-4 text-right font-medium">Failures</th>
            <th className="py-2 pr-4 text-right font-medium">WER</th>
            <th className="py-2 pr-4 text-right font-medium">CER</th>
            <th className="py-2 pr-4 text-right font-medium">Final p50</th>
            <th className="py-2 pr-4 text-right font-medium">Final p95</th>
            <th className="py-2 text-right font-medium">RTF p50</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => (
            <tr
              key={`${group.provider}-${group.condition}-${group.language}`}
              className="border-b border-border/60"
            >
              <td className="py-2.5 pr-4">{group.provider}</td>
              <td className="py-2.5 pr-4 text-muted-foreground">
                {group.condition}
              </td>
              <td className="py-2.5 pr-4 text-muted-foreground">
                {group.language}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {group.count}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {group.failures}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {percent(group.wer_median)}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {percent(group.cer_median)}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {milliseconds(group.time_to_final_median_ms)}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {milliseconds(group.time_to_final_p95_ms)}
              </td>
              <td className="py-2.5 text-right tabular-nums">
                {number(group.rtf_median)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TtsTable({ groups }: { groups: TtsBenchmarkGroup[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[58rem] border-collapse text-left text-xs">
        <thead className="border-b border-border text-muted-foreground">
          <tr>
            <th className="py-2 pr-4 font-medium">Provider</th>
            <th className="py-2 pr-4 font-medium">Language</th>
            <th className="py-2 pr-4 text-right font-medium">Runs</th>
            <th className="py-2 pr-4 text-right font-medium">Failures</th>
            <th className="py-2 pr-4 text-right font-medium">
              First audio p50
            </th>
            <th className="py-2 pr-4 text-right font-medium">
              First audio p95
            </th>
            <th className="py-2 pr-4 text-right font-medium">Synthesis p50</th>
            <th className="py-2 pr-4 text-right font-medium">RTF p50</th>
            <th className="py-2 pr-4 text-right font-medium">Round-trip WER</th>
            <th className="py-2 text-right font-medium">Round-trip CER</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => (
            <tr
              key={`${group.provider}-${group.language}`}
              className="border-b border-border/60"
            >
              <td className="py-2.5 pr-4">{group.provider}</td>
              <td className="py-2.5 pr-4 text-muted-foreground">
                {group.language}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {group.count}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {group.failures}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {milliseconds(group.time_to_first_audio_median_ms)}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {milliseconds(group.time_to_first_audio_p95_ms)}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {milliseconds(group.total_synthesis_median_ms)}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {number(group.rtf_median)}
              </td>
              <td className="py-2.5 pr-4 text-right tabular-nums">
                {percent(group.roundtrip_wer_median)}
              </td>
              <td className="py-2.5 text-right tabular-nums">
                {percent(group.roundtrip_cer_median)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BenchmarkPage() {
  const [summary, setSummary] = useState<BenchmarkSummary | null>(null);

  useEffect(() => {
    void getBenchmarkSummary().then(setSummary);
  }, []);

  const sttGroups = summary?.stt?.groups ?? [];
  const ttsGroups = summary?.tts?.groups ?? [];
  const ttsOverall = ttsGroups.filter((group) => group.language === "all");
  const ttsLanguages = ttsGroups.filter((group) => group.language !== "all");
  const sttAccuracy = useMemo(
    () => combineStt(sttGroups, "wer_median"),
    [sttGroups],
  );
  const sttLatency = useMemo(
    () => combineStt(sttGroups, "time_to_final_median_ms"),
    [sttGroups],
  );
  const ttsFirstAudio: MetricBar[] = ttsOverall.map((group) => ({
    label: group.provider,
    value: group.time_to_first_audio_median_ms,
    detail: "Median across all sentences and runs",
  }));
  const ttsRoundTrip: MetricBar[] = ttsLanguages.map((group) => ({
    label: `${group.provider} · ${group.language}`,
    value: group.roundtrip_wer_median,
    detail: "Normalized WER from faster-whisper-base transcription",
  }));
  const failures = [
    ...(summary?.stt?.failures ?? []),
    ...(summary?.tts?.failures ?? []),
  ];

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <Navbar />
      <main className="container max-w-6xl py-10 sm:py-14">
        <div className="flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="text-xs font-medium uppercase tracking-[0.18em] text-brand">
              Speech provider benchmark
            </p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              STT and TTS results
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              Prisma v2.5, Faster Whisper base, Sarvam Saaras, Timbre v2.5 and
              Sarvam Bulbul on the same recorded inputs.
            </p>
          </div>
          {summary?.status === "ok" ? (
            <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
              <span className="rounded-full border border-border px-3 py-1.5">
                {summary.runs_per_item} runs per item
              </span>
              <span className="rounded-full border border-border px-3 py-1.5">
                {summary.finished_at_utc}
              </span>
            </div>
          ) : null}
        </div>

        {!summary ? (
          <p className="mt-12 text-sm text-muted-foreground">
            Loading measured results…
          </p>
        ) : summary.status !== "ok" ? (
          <div className="mt-12 border-t border-border pt-8">
            <p className="flex items-center gap-2 text-sm">
              <AlertTriangleIcon className="size-4 text-amber-500" />
              {summary.message ?? "No benchmark has been run."}
            </p>
          </div>
        ) : (
          <div className="mt-10">
            <MetricSection
              title="Recognition accuracy"
              description="Normalized word error rate, averaged across the three language groups for each provider and condition."
              icon={<GaugeIcon className="size-4 text-brand" />}
            >
              <MetricBarChart bars={sttAccuracy} formatValue={percent} />
            </MetricSection>

            <MetricSection
              title="Final transcript latency"
              description="Median time from request start to the final transcript. The table below includes p95 and real-time factor."
              icon={<Clock3Icon className="size-4 text-brand" />}
            >
              <MetricBarChart bars={sttLatency} formatValue={milliseconds} />
            </MetricSection>

            <section className="border-t border-border py-8">
              <h2 className="text-base font-semibold">STT detail</h2>
              <div className="mt-4">
                <SttTable groups={sttGroups} />
              </div>
            </section>

            <MetricSection
              title="Time to first audio"
              description="Median across all TTS sentences and runs. Lower is better."
              icon={<AudioLinesIcon className="size-4 text-brand" />}
            >
              <MetricBarChart bars={ttsFirstAudio} formatValue={milliseconds} />
            </MetricSection>

            <MetricSection
              title="Round-trip intelligibility"
              description="Every generated clip was transcribed by faster-whisper-base. This proxy can miss pronunciation problems that a person would hear."
              icon={<GaugeIcon className="size-4 text-brand" />}
            >
              <MetricBarChart bars={ttsRoundTrip} formatValue={percent} />
            </MetricSection>

            <section className="border-t border-border py-8">
              <h2 className="text-base font-semibold">TTS detail</h2>
              <div className="mt-4">
                <TtsTable groups={ttsGroups} />
              </div>
            </section>

            <MetricSection
              title="Failures"
              description="Timeouts and provider errors remain failures. They are not removed or estimated."
              icon={<AlertTriangleIcon className="size-4 text-amber-500" />}
            >
              {failures.length ? (
                <ul className="space-y-2 text-xs">
                  {failures.map((failure, index) => (
                    <li
                      key={`${failure.provider}-${failure.utterance_id ?? failure.text_id}-${index}`}
                      className="border-b border-border/60 pb-2"
                    >
                      <span className="font-medium">{failure.provider}</span>
                      <span className="text-muted-foreground">
                        {" "}
                        · {failure.condition ?? failure.language} ·{" "}
                        {failure.utterance_id ?? failure.text_id}
                      </span>
                      <span className="mt-1 block text-destructive">
                        {failure.error}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">
                  No provider failures were recorded.
                </p>
              )}
            </MetricSection>

            <section className="border-t border-border py-8">
              <h2 className="text-base font-semibold">Method and limits</h2>
              <p className="mt-3 max-w-4xl text-sm leading-6 text-muted-foreground">
                {summary.normalization?.description}
              </p>
              <p className="mt-3 max-w-4xl text-sm leading-6 text-muted-foreground">
                Devanagari transliteration is deterministic, not phonetic, so
                spelling variants can inflate error rates. The TTS
                intelligibility score is an STT proxy, not a human listening
                test. Raw rows are stored in{" "}
                <code className="font-mono text-xs text-foreground">
                  {summary.stt?.raw_results} and {summary.tts?.raw_results}
                </code>
                .
              </p>
            </section>
          </div>
        )}
      </main>
    </div>
  );
}
