import { API_URL } from "./voice-catalog";

export type SttBenchmarkGroup = {
  provider: string;
  condition: string;
  language: string;
  count: number;
  failures: number;
  empty: number;
  wer_median: number | null;
  cer_median: number | null;
  time_to_final_median_ms: number | null;
  time_to_final_p95_ms: number | null;
  rtf_median: number | null;
  rtf_p95: number | null;
};

export type TtsBenchmarkGroup = {
  provider: string;
  language: string;
  count: number;
  failures: number;
  time_to_first_audio_median_ms: number | null;
  time_to_first_audio_p95_ms: number | null;
  total_synthesis_median_ms: number | null;
  total_synthesis_p95_ms: number | null;
  audio_duration_median_s: number | null;
  rtf_median: number | null;
  rtf_p95: number | null;
  roundtrip_wer_median: number | null;
  roundtrip_cer_median: number | null;
};

export type BenchmarkFailure = {
  provider: string;
  condition?: string;
  language?: string;
  utterance_id?: string;
  text_id?: string;
  error: string;
};

export type BenchmarkSummary = {
  status: "ok" | "not_run";
  message?: string;
  summary_file?: string;
  started_at_utc?: string;
  finished_at_utc?: string;
  machine?: string;
  network_region?: string;
  runs_per_item?: number;
  models?: Record<string, string>;
  normalization?: {
    description: string;
    implementation: string;
  };
  stt?: {
    raw_results: string;
    groups: SttBenchmarkGroup[];
    failures: BenchmarkFailure[];
  };
  tts?: {
    raw_results: string;
    groups: TtsBenchmarkGroup[];
    failures: BenchmarkFailure[];
  };
};

export async function getBenchmarkSummary(): Promise<BenchmarkSummary> {
  try {
    const response = await fetch(`${API_URL}/api/v1/voice/benchmark`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) {
      return {
        status: "not_run",
        message: `Benchmark request failed (${response.status}).`,
      };
    }
    return (await response.json()) as BenchmarkSummary;
  } catch {
    return {
      status: "not_run",
      message: "The benchmark API is unavailable.",
    };
  }
}
