export type TTFAMode = "backend" | "byok";
export type TTFAStatus = "complete" | "interrupted" | "failed";

export type TTFAStages = {
  sttMs: number | null;
  llmMs: number | null;
  ttsMs: number | null;
  playbackMs: number | null;
};

export type TurnMetricRecord = {
  turnId: string;
  mode: TTFAMode;
  sttProvider: string;
  language: string | null;
  scenarioId?: string | null;
  stages: TTFAStages;
  ttfaMs: number | null;
  bankNoticeMs?: number | null;
  bankAnswerFirstAudioMs?: number | null;
  timestamp: string;
  status: TTFAStatus;
  coldStart: boolean;
};

export type TTFAStats = {
  lastTurn: TurnMetricRecord | null;
  count: number;
  mean: number | null;
  median: number | null;
  p95: number | null;
  min: number | null;
  max: number | null;
  stages: TTFAStages;
  excluded: {
    interrupted: number;
    failed: number;
    coldStart: number;
    total: number;
  };
};

type TurnTimerInput = {
  turnId: string;
  mode: TTFAMode;
  sttProvider: string;
  language: string | null;
  scenarioId?: string | null;
  coldStart: boolean;
  startedAt?: number;
  timestamp?: string;
  now?: () => number;
};

function duration(start: number | null, end: number | null): number | null {
  if (start == null || end == null || end < start) return null;
  return Math.round(end - start);
}

function average(values: number[]): number | null {
  if (!values.length) return null;
  return Math.round(
    values.reduce((sum, value) => sum + value, 0) / values.length,
  );
}

export function percentile(values: number[], p: number): number | null {
  if (!values.length) return null;
  const ordered = [...values].sort((a, b) => a - b);
  if (ordered.length === 1) return Math.round(ordered[0]);
  const rank = (ordered.length - 1) * (p / 100);
  const lower = Math.floor(rank);
  const upper = Math.min(lower + 1, ordered.length - 1);
  const weight = rank - lower;
  return Math.round(ordered[lower] * (1 - weight) + ordered[upper] * weight);
}

/**
 * Collects monotonic client timestamps for one turn. Provider requests stay
 * outside this class; callers only mark the observable stage boundaries.
 */
export class TurnTimer {
  readonly coldStart: boolean;

  private readonly turnId: string;
  private readonly mode: TTFAMode;
  private readonly sttProvider: string;
  private readonly language: string | null;
  private readonly scenarioId: string | null;
  private readonly startedAt: number;
  private readonly timestamp: string;
  private readonly now: () => number;
  private transcriptFinalAt: number | null = null;
  private firstLlmTokenAt: number | null = null;
  private firstAudioReceivedAt: number | null = null;
  private playbackStartedAt: number | null = null;
  private bankNoticeAt: number | null = null;
  private bankAnswerAt: number | null = null;

  constructor(input: TurnTimerInput) {
    this.turnId = input.turnId;
    this.mode = input.mode;
    this.sttProvider = input.sttProvider;
    this.language = input.language;
    this.scenarioId = input.scenarioId ?? null;
    this.coldStart = input.coldStart;
    this.now = input.now ?? (() => performance.now());
    this.startedAt = input.startedAt ?? this.now();
    this.timestamp = input.timestamp ?? new Date().toISOString();
  }

  markTranscriptFinal(at = this.now()): void {
    this.transcriptFinalAt ??= at;
  }

  markFirstLlmToken(at = this.now()): void {
    this.firstLlmTokenAt ??= at;
  }

  markFirstAudioReceived(at = this.now()): void {
    this.firstAudioReceivedAt ??= at;
  }

  markBankNotice(at = this.now()): void {
    this.bankNoticeAt ??= at;
  }

  markBankAnswer(at = this.now()): void {
    this.bankAnswerAt ??= at;
    this.firstAudioReceivedAt ??= at;
  }

  finish(status: TTFAStatus, at = this.now()): TurnMetricRecord {
    if (status === "complete") this.playbackStartedAt ??= at;
    return {
      turnId: this.turnId,
      mode: this.mode,
      sttProvider: this.sttProvider,
      language: this.language,
      scenarioId: this.scenarioId,
      stages: {
        sttMs: duration(this.startedAt, this.transcriptFinalAt),
        llmMs: duration(this.transcriptFinalAt, this.firstLlmTokenAt),
        ttsMs: duration(this.firstLlmTokenAt, this.firstAudioReceivedAt),
        playbackMs: duration(this.firstAudioReceivedAt, this.playbackStartedAt),
      },
      ttfaMs: duration(this.startedAt, this.playbackStartedAt),
      bankNoticeMs: duration(this.startedAt, this.bankNoticeAt),
      bankAnswerFirstAudioMs: duration(this.startedAt, this.bankAnswerAt),
      timestamp: this.timestamp,
      status,
      coldStart: this.coldStart,
    };
  }
}

export type BankTTFAStats = {
  count: number;
  noticeMean: number | null;
  noticeMedian: number | null;
  noticeP95: number | null;
  answerMean: number | null;
  answerMedian: number | null;
  answerP95: number | null;
};

export function calculateBankTTFAStats(
  records: readonly TurnMetricRecord[],
): BankTTFAStats {
  const bankRecords = records.filter(
    (record) =>
      record.scenarioId === "demo-bank" && record.status === "complete",
  );
  const notices = bankRecords
    .map((record) => record.bankNoticeMs)
    .filter((value): value is number => value != null);
  const answers = bankRecords
    .map((record) => record.bankAnswerFirstAudioMs)
    .filter((value): value is number => value != null);
  return {
    count: bankRecords.length,
    noticeMean: average(notices),
    noticeMedian: percentile(notices, 50),
    noticeP95: percentile(notices, 95),
    answerMean: average(answers),
    answerMedian: percentile(answers, 50),
    answerP95: percentile(answers, 95),
  };
}

export function calculateTTFAStats(
  records: readonly TurnMetricRecord[],
  options: { includeColdStart?: boolean } = {},
): TTFAStats {
  const includeColdStart = options.includeColdStart ?? false;
  const excluded = {
    interrupted: 0,
    failed: 0,
    coldStart: 0,
    total: 0,
  };
  const counted: TurnMetricRecord[] = [];

  for (const record of records) {
    if (record.status === "interrupted") {
      excluded.interrupted += 1;
    } else if (record.status === "failed" || record.ttfaMs == null) {
      excluded.failed += 1;
    } else if (record.coldStart && !includeColdStart) {
      excluded.coldStart += 1;
    } else {
      counted.push(record);
    }
  }
  excluded.total = excluded.interrupted + excluded.failed + excluded.coldStart;

  const values = counted
    .map((record) => record.ttfaMs)
    .filter((value): value is number => value != null);
  const stageValues = (key: keyof TTFAStages) =>
    counted
      .map((record) => record.stages[key])
      .filter((value): value is number => value != null);
  const lastTurn =
    [...records]
      .reverse()
      .find(
        (record) => record.status === "complete" && record.ttfaMs != null,
      ) ?? null;

  return {
    lastTurn,
    count: values.length,
    mean: average(values),
    median: percentile(values, 50),
    p95: percentile(values, 95),
    min: values.length ? Math.min(...values) : null,
    max: values.length ? Math.max(...values) : null,
    stages: {
      sttMs: average(stageValues("sttMs")),
      llmMs: average(stageValues("llmMs")),
      ttsMs: average(stageValues("ttsMs")),
      playbackMs: average(stageValues("playbackMs")),
    },
    excluded,
  };
}
