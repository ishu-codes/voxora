"use client";

import {
  ArrowLeftIcon,
  CheckIcon,
  KeyRoundIcon,
  ShieldCheckIcon,
  SparklesIcon,
  Trash2Icon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Navbar } from "@/components/navbar/Navbar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  clearVoiceSettings,
  EMPTY_VOICE_SETTINGS,
  hasUnlimitedVoiceSettings,
  hasVoiceSettings,
  loadVoiceSettings,
  saveVoiceSettings,
  type VoiceSettings,
} from "@/lib/voice-settings";

type FieldKey = keyof VoiceSettings;

export default function SettingsPage() {
  const [form, setForm] = useState<VoiceSettings>(EMPTY_VOICE_SETTINGS);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(loadVoiceSettings());
  }, []);

  const update =
    (key: FieldKey) => (event: React.ChangeEvent<HTMLInputElement>) => {
      setSaved(false);
      setError(null);
      setForm((previous) => ({ ...previous, [key]: event.target.value }));
    };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (
      form.openaiBaseUrl &&
      !/^https?:\/\//i.test(form.openaiBaseUrl.trim())
    ) {
      setError(
        "The OpenAI-compatible base URL must start with http:// or https://.",
      );
      return;
    }
    setForm(saveVoiceSettings(form));
    setSaved(true);
    setError(null);
  };

  const clear = () => {
    clearVoiceSettings();
    setForm(EMPTY_VOICE_SETTINGS);
    setSaved(false);
    setError(null);
  };

  const unlimited = hasUnlimitedVoiceSettings(form);
  const custom = hasVoiceSettings(form);

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <Navbar />

      <main className="container max-w-3xl py-10 sm:py-14">
        <Link
          href="/app"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeftIcon className="size-4" />
          Back to voice studio
        </Link>

        <div className="mt-6 flex items-start gap-4">
          <div className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-brand/15 text-brand">
            <KeyRoundIcon className="size-5" />
          </div>
          <div>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
              Voice settings
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
              Use the shared Voxora platform for a limited trial, or bring your
              own Sarvam and OpenAI-compatible keys for unlimited use.
            </p>
          </div>
        </div>

        <div className="mt-8 grid gap-3 sm:grid-cols-2">
          <div
            className={`rounded-2xl border p-4 ${
              unlimited
                ? "border-border bg-muted/20"
                : "border-brand/40 bg-brand/5"
            }`}
          >
            <div className="flex items-center gap-2 text-sm font-medium">
              <SparklesIcon className="size-4 text-brand" />
              Platform trial
            </div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              No setup. Uses Voxora&apos;s shared keys and is limited to a small
              number of turns per session.
            </p>
          </div>

          <div
            className={`rounded-2xl border p-4 ${
              unlimited
                ? "border-brand/40 bg-brand/5"
                : "border-border bg-muted/20"
            }`}
          >
            <div className="flex items-center gap-2 text-sm font-medium">
              <ShieldCheckIcon className="size-4 text-brand" />
              Your own keys
            </div>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Unlimited voice sessions using your provider accounts. Add both a
              Sarvam key and an OpenAI-compatible endpoint.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <section className="rounded-2xl border border-border bg-card/40 p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">Sarvam AI</h2>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  Powers realtime speech recognition and Bulbul speech
                  synthesis.
                </p>
              </div>
              <a
                href="https://indus.sarvam.ai/key-management"
                target="_blank"
                rel="noopener"
                className="text-sm font-medium text-brand hover:underline"
              >
                Get a key
              </a>
            </div>

            <div className="mt-5">
              <label
                htmlFor="sarvam-api-key"
                className="mb-2 block text-sm font-medium"
              >
                Sarvam API key
              </label>
              <Input
                id="sarvam-api-key"
                type="password"
                value={form.sarvamApiKey}
                onChange={update("sarvamApiKey")}
                placeholder="sk_..."
                autoComplete="off"
                spellCheck={false}
                className="rounded-xl"
              />
              <p className="mt-2 text-xs text-muted-foreground">
                Required to use your own speech providers. Without it, the
                platform trial covers speech.
              </p>
            </div>
          </section>

          <section className="rounded-2xl border border-border bg-card/40 p-5 sm:p-6">
            <div>
              <h2 className="text-lg font-semibold">OpenAI-compatible model</h2>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">
                Any endpoint that implements the chat-completions API: OpenAI,
                DeepSeek, Groq, Ollama, vLLM, and similar servers.
              </p>
            </div>

            <div className="mt-5 grid gap-4">
              <div>
                <label
                  htmlFor="openai-api-key"
                  className="mb-2 block text-sm font-medium"
                >
                  API key
                </label>
                <Input
                  id="openai-api-key"
                  type="password"
                  value={form.openaiApiKey}
                  onChange={update("openaiApiKey")}
                  placeholder="sk-..."
                  autoComplete="off"
                  spellCheck={false}
                  className="rounded-xl"
                />
                <p className="mt-2 text-xs text-muted-foreground">
                  Leave empty for a local endpoint that does not require
                  authentication.
                </p>
              </div>

              <div>
                <label
                  htmlFor="openai-base-url"
                  className="mb-2 block text-sm font-medium"
                >
                  Base URL
                </label>
                <Input
                  id="openai-base-url"
                  type="url"
                  value={form.openaiBaseUrl}
                  onChange={update("openaiBaseUrl")}
                  placeholder="https://api.openai.com/v1"
                  autoComplete="off"
                  spellCheck={false}
                  className="rounded-xl"
                />
              </div>

              <div>
                <label
                  htmlFor="openai-model"
                  className="mb-2 block text-sm font-medium"
                >
                  Model
                </label>
                <Input
                  id="openai-model"
                  type="text"
                  value={form.openaiModel}
                  onChange={update("openaiModel")}
                  placeholder="gpt-4o-mini"
                  autoComplete="off"
                  spellCheck={false}
                  className="rounded-xl"
                />
              </div>
            </div>
          </section>

          {error ? (
            <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {error}
            </p>
          ) : null}

          <div className="flex flex-wrap items-center gap-3">
            <Button type="submit" size="lg" className="rounded-full px-5">
              Save settings
            </Button>
            {custom ? (
              <Button
                type="button"
                variant="outline"
                size="lg"
                onClick={clear}
                className="rounded-full px-5"
              >
                <Trash2Icon className="size-4" />
                Clear saved keys
              </Button>
            ) : null}
            {saved ? (
              <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                <CheckIcon className="size-4 text-brand" />
                Saved in this browser
              </span>
            ) : null}
          </div>
        </form>

        <p className="mt-6 text-xs leading-5 text-muted-foreground">
          Keys are saved in this browser&apos;s local storage and sent to the
          Voxora server only as part of your voice session. The server does not
          save them. Anyone with access to this browser profile can read them.
        </p>
      </main>
    </div>
  );
}
