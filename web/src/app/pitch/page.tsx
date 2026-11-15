import type { Metadata } from "next";

import { Footer } from "@/components/marketing/Footer";
import { Navbar } from "@/components/marketing/Navbar";
import { NoiseOverlay } from "@/components/marketing/NoiseOverlay";
import { OutlinePill, Pill } from "@/components/marketing/Pill";
import { Reveal } from "@/components/marketing/Reveal";
import { Section } from "@/components/marketing/Section";
import { WordReveal } from "@/components/marketing/WordReveal";

export const metadata: Metadata = {
  title: "Solution pitch",
  description:
    "A voice first way for people in small towns and villages to understand banking information in their own language.",
};

const QUESTIONS = [
  "Which documents do I need to open an account?",
  "मैं ATM कार्ड कैसे चालू करूँ?",
  "UPI se paise kaise bhejein?",
  "What documents do I need for a loan?",
];

const EVIDENCE = [
  {
    value: "12 / 12",
    label: "Demo Bank evaluation cases passed",
  },
  {
    value: "190 ms",
    label: "Median clean English final transcript, saved Prisma run",
  },
  {
    value: "5 files",
    label: "Allowlisted banking documents available to the agent",
  },
];

function VoiceExchange() {
  return (
    <figure className="relative overflow-hidden rounded-3xl border border-background/20 bg-background p-5 text-foreground sm:p-6">
      <figcaption className="sr-only">
        Example Demo Bank voice exchange
      </figcaption>
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            Demo Bank Helper
          </p>
          <p className="mt-1 text-sm font-medium">Hindi, Hinglish or English</p>
        </div>
        <output
          className="size-2.5 rounded-full bg-brand"
          aria-label="Session active"
        />
      </div>

      <div className="flex h-16 items-center gap-1.5 border-b border-border py-4">
        {[12, 22, 40, 26, 52, 34, 58, 28, 44, 20, 36, 14].map(
          (height, index) => (
            <span
              key={height}
              className="w-full animate-pulse rounded-full bg-brand/70"
              style={{
                height,
                animationDelay: `${index * 80}ms`,
              }}
              aria-hidden="true"
            />
          ),
        )}
      </div>

      <div className="space-y-4 pt-5 text-sm leading-6">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
            You
          </p>
          <p className="mt-1">
            Mere paas smartphone nahi hai. ATM card kaise activate karun?
          </p>
        </div>
        <div className="rounded-2xl bg-muted/50 p-3.5">
          <p className="font-mono text-xs uppercase tracking-widest text-brand">
            Checking documents
          </p>
          <p className="mt-1">
            Ek minute, main aapke sawaal ke liye documents check kar raha hoon.
          </p>
          <p className="mt-2 font-mono text-xs text-muted-foreground">
            atm_card.md
          </p>
        </div>
      </div>
    </figure>
  );
}

export default function PitchPage() {
  return (
    <div className="min-h-dvh bg-background text-foreground">
      <Navbar />

      <main className="pt-[85px]">
        <section className="relative overflow-hidden bg-brand text-brand-foreground">
          <NoiseOverlay />
          <div className="container relative z-10 grid min-h-[calc(100svh-85px)] items-center gap-12 py-16 lg:grid-cols-[1.15fr_0.85fr] lg:py-20">
            <Reveal direction="up">
              <div className="max-w-2xl">
                <p className="font-mono text-sm uppercase tracking-widest text-brand-foreground/75">
                  Solution pitch
                </p>
                <h1 className="mt-5 max-w-[680px] text-4xl font-semibold tracking-tighter text-balance sm:text-5xl lg:text-6xl">
                  Banking knowledge, spoken in the language people already use.
                </h1>
                <p className="mt-6 max-w-[680px] text-base leading-7 text-brand-foreground/80 sm:text-lg">
                  Voxora helps people in small towns and villages ask a banking
                  question out loud, hear the agent check an approved document,
                  and get a short answer in Hindi, Hinglish or English.
                </p>
                <div className="mt-8 flex flex-wrap items-center gap-3">
                  <Pill
                    asLink
                    to="/app"
                    className="bg-background text-foreground hover:bg-background/90"
                  >
                    Try the voice demo
                  </Pill>
                  <OutlinePill
                    asLink
                    href="#how-it-works"
                    className="border-brand-foreground/30 text-brand-foreground hover:bg-brand-foreground/10"
                  >
                    See how it works
                  </OutlinePill>
                </div>
              </div>
            </Reveal>

            <Reveal direction="right" delay={120}>
              <VoiceExchange />
            </Reveal>
          </div>
        </section>

        <Section dashed>
          <Reveal>
            <div className="grid gap-10 lg:grid-cols-[0.75fr_1.25fr]">
              <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
                The access gap
              </p>
              <div>
                <h2 className="max-w-[680px] text-3xl font-semibold tracking-tighter text-balance sm:text-4xl lg:text-5xl">
                  A simple question should not require a trip to the branch.
                </h2>
                <p className="mt-6 max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
                  Banking information is spread across forms, apps, websites and
                  staff conversations. Text available only in English and
                  unfamiliar terms such as KYC, IFSC and loan eligibility can
                  make a routine question feel difficult. Without a clear
                  answer, people may make repeated trips or depend on someone
                  else to interpret their own account information.
                </p>
              </div>
            </div>
          </Reveal>
        </Section>

        <Section className="bg-brand/8">
          <Reveal>
            <WordReveal text="Banking knowledge should be available where people already are." />
          </Reveal>
        </Section>

        <Section id="how-it-works" className="bg-muted/20">
          <Reveal>
            <h2 className="max-w-[680px] text-3xl font-semibold tracking-tighter text-balance sm:text-4xl lg:text-5xl">
              Ask naturally. Hear the source. Continue one step at a time.
            </h2>
          </Reveal>

          <div className="mt-12 grid gap-8 md:grid-cols-3">
            {[
              [
                "01",
                "Speak the question",
                "Use everyday words in the language already spoken at home.",
              ],
              [
                "02",
                "Hear the lookup",
                "The agent says it is checking the documents before the lookup begins.",
              ],
              [
                "03",
                "Get a grounded answer",
                "The agent answers from the selected document and shows which file it used.",
              ],
            ].map(([number, title, body], index) => (
              <Reveal key={title} delay={index * 100}>
                <div className="border-t border-border pt-5">
                  <p className="font-mono text-xs tracking-widest text-brand">
                    {number}
                  </p>
                  <h3 className="mt-4 text-xl font-semibold">{title}</h3>
                  <p className="mt-3 text-sm leading-6 text-muted-foreground">
                    {body}
                  </p>
                </div>
              </Reveal>
            ))}
          </div>
        </Section>

        <Section>
          <div className="grid gap-12 lg:grid-cols-[1fr_0.9fr]">
            <Reveal>
              <div>
                <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
                  Common questions
                </p>
                <h2 className="mt-4 max-w-[680px] text-3xl font-semibold tracking-tighter text-balance sm:text-4xl lg:text-5xl">
                  Useful before the caller reaches a counter.
                </h2>
              </div>
            </Reveal>
            <Reveal direction="right">
              <ul className="divide-y divide-border border-y border-border">
                {QUESTIONS.map((question) => (
                  <li
                    key={question}
                    className="py-5 text-base leading-7 text-foreground/85"
                  >
                    {question}
                  </li>
                ))}
              </ul>
            </Reveal>
          </div>
        </Section>

        <Section className="bg-foreground text-background">
          <Reveal>
            <div className="grid gap-12 lg:grid-cols-[0.8fr_1.2fr]">
              <div>
                <p className="font-mono text-xs uppercase tracking-widest text-background/60">
                  Measured evidence
                </p>
                <h2 className="mt-4 max-w-[680px] text-3xl font-semibold tracking-tighter text-balance sm:text-4xl">
                  A working demo, not a concept slide.
                </h2>
              </div>
              <div className="grid gap-8 sm:grid-cols-3">
                {EVIDENCE.map((item) => (
                  <div
                    key={item.label}
                    className="border-t border-background/20 pt-4"
                  >
                    <p className="font-mono text-2xl font-semibold tabular-nums">
                      {item.value}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-background/70">
                      {item.label}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </Reveal>
        </Section>

        <Section>
          <Reveal>
            <div className="mx-auto max-w-3xl text-center">
              <p className="font-mono text-xs uppercase tracking-widest text-muted-foreground">
                Safety boundary
              </p>
              <h2 className="mt-4 text-3xl font-semibold tracking-tighter text-balance sm:text-4xl">
                Knowledge without account access.
              </h2>
              <p className="mt-6 text-base leading-7 text-muted-foreground">
                Demo Bank is fictional and illustrative. The helper cannot
                access a balance, view transactions or perform an action. It
                never asks for an OTP, PIN, CVV, password or full card number.
                Every answer points back to an allowlisted document.
              </p>
              <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
                <Pill asLink to="/app">
                  Open the Demo Bank Helper
                </Pill>
                <OutlinePill asLink href="/benchmark">
                  View speech benchmark
                </OutlinePill>
              </div>
            </div>
          </Reveal>
        </Section>
      </main>

      <Footer />
    </div>
  );
}
