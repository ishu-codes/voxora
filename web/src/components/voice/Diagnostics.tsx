import { cn } from "@/lib/utils";
import type { ReadyEvent, ConnectionStatus } from "@/voice/protocol";
import type { TurnDiagnostics } from "@/voice/useVoiceSession";

type DiagnosticsProps = {
  status: ConnectionStatus;
  ready: ReadyEvent | null;
  summary: { turns: number; firstPlaybackP50: number | null; firstPlaybackP95: number | null; bargeInP95: number | null };
  diagnostics: TurnDiagnostics[];
};

function Row({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 py-2 last:border-0">
      <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </span>
      <span className={cn("font-mono text-xs", accent ? "text-brand-text" : "text-foreground")}>
        {value}
      </span>
    </div>
  );
}

function format(value: number | null | undefined): string {
  return value == null ? "—" : `${Math.round(value)} ms`;
}

export function Diagnostics({ status, ready, summary, diagnostics }: DiagnosticsProps) {
  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto p-5">
      <section>
        <h3 className="font-mono text-xs uppercase tracking-[0.3em] text-muted-foreground">
          Connection
        </h3>
        <div className="mt-2">
          <Row label="Socket" value={status} accent={status === "connected"} />
          <Row label="Audio in" value="16 kHz · PCM16 · 20 ms" />
          {ready && <Row label="Session" value={ready.session_id.slice(0, 8)} />}
        </div>
      </section>

      {ready && (
        <section>
          <h3 className="font-mono text-xs uppercase tracking-[0.3em] text-muted-foreground">
            Providers
          </h3>
          <div className="mt-2">
            <Row
              label="STT"
              value={ready.stt.name}
              accent={ready.stt.mode === "server-stt"}
            />
            <Row label="LLM" value={ready.llm.name} accent={ready.llm.name !== "echo (demo)"} />
            <Row label="TTS" value={ready.tts.name} accent={ready.tts.kind === "audio"} />
            <Row label="VAD" value={ready.vad.name} />
          </div>
        </section>
      )}

      <section>
        <h3 className="font-mono text-xs uppercase tracking-[0.3em] text-muted-foreground">
          This session
        </h3>
        <div className="mt-2">
          <Row label="Turns" value={String(summary.turns)} />
          <Row label="First audio p50" value={format(summary.firstPlaybackP50)} accent />
          <Row label="First audio p95" value={format(summary.firstPlaybackP95)} accent />
          <Row label="Barge-in p95" value={format(summary.bargeInP95)} accent />
        </div>
      </section>

      {ready && (
        <section>
          <h3 className="font-mono text-xs uppercase tracking-[0.3em] text-muted-foreground">
            Targets
          </h3>
          <div className="mt-2">
            <Row label="First audio p50" value={`≤ ${ready.targets.first_audio_p50_ms} ms`} />
            <Row label="First audio p95" value={`≤ ${ready.targets.first_audio_p95_ms} ms`} />
            <Row label="Barge-in p95" value={`≤ ${ready.targets.barge_in_p95_ms} ms`} />
          </div>
        </section>
      )}

      <section>
        <h3 className="font-mono text-xs uppercase tracking-[0.3em] text-muted-foreground">
          Recent turns
        </h3>
        {diagnostics.length === 0 ? (
          <p className="mt-3 text-xs text-muted-foreground">No turns yet.</p>
        ) : (
          <div className="mt-2 overflow-x-auto">
            <table className="w-full border-collapse font-mono text-[11px]">
              <thead>
                <tr className="text-muted-foreground">
                  <th className="border-b border-border py-1.5 text-left font-normal">turn</th>
                  <th className="border-b border-border py-1.5 text-right font-normal">server e2e</th>
                  <th className="border-b border-border py-1.5 text-right font-normal">playback</th>
                  <th className="border-b border-border py-1.5 text-right font-normal">barge-in</th>
                </tr>
              </thead>
              <tbody>
                {[...diagnostics].reverse().map((diag) => (
                  <tr key={diag.turnId} className="text-foreground">
                    <td className="border-b border-border/50 py-1.5 pr-2 text-muted-foreground">
                      {diag.turnId.slice(-6)}
                    </td>
                    <td className="border-b border-border/50 py-1.5 text-right">{format(diag.serverE2e)}</td>
                    <td className="border-b border-border/50 py-1.5 text-right">{format(diag.firstPlayback)}</td>
                    <td className="border-b border-border/50 py-1.5 text-right">{format(diag.bargeIn)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
