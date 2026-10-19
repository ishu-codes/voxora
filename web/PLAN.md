# Ragify Web — Reference Visual Overhaul (Ragify copy, commandcode.ai chrome)

## Goal

Rebuild `/home/ishu/dev/ai/ragify/web` so the **look-and-feel matches `https://commandcode.ai/` exactly** — same dark-first aesthetic, same section order, same dashed-grid hero, same component vocabulary (rounded-full pill buttons, monochrome dark navbar, dashed `.dash-*` borders, `--brand` deep-indigo accent, Geist + Geist Mono typography, mix-blend-overlay noise).

**The page chrome is a verbatim port.** What changes is **all text content** (copy, headlines, button labels, FAQ answers, pricing tier names, footer columns) and the **section composition** where the reference's coding-agent concepts have no Ragify analog. Specifically:

- Replace "Command Code / coding agent / taste-1 / npm i -g command-code / GOAT / Subscribe / Founders" framing with Ragify's grounded-document RAG framing.
- Replace "taste" / "taste-1" / meta neuro-symbolic AI explainer with a **Ragify-specific** explainer: workspace isolation, hybrid retrieval, citations, multi-format ingestion.
- Replace the **Subscribe. Be a GOAT.** pricing section with a **Ragify plans** section (Free / Pro / Enterprise — same visual treatment).
- Replace the **"Hello, taste." 01–07 numbered feature list** with a Ragify-specific numbered capability list (ingestion → retrieval → citation → SDK access).
- Replace the **Changelog** feed with a **Latest from Ragify** feed (typed mock array, swappable for a real backend later).
- Drop or repurpose elements that are coding-agent-only: terminal-demo of `npm i`, Discord link, GitHub link (we keep them only if real assets exist), the "50+ models" chip, the "$1/mo" pricing teaser, the "Command Code raised $5M seed" announcement.
- Add **Ragify equivalents**: announcement strip = "Ragify is in private beta", demo terminal = `curl -X POST /api/v1/workspaces/:id/query` mock, footer columns reflect Ragify's product surface.

All current functionality preserved; the work is visual + structural + copy.

## Reference Design Spec (extracted from the live site)

- **Type**: Geist (400/500/600/700) + Geist Mono (400/500/600/700), loaded via Google Fonts CSS API. Drop the current `@fontsource-variable/inter` import.
- **Color tokens (default = dark)**
  - `--background: #000` — `--foreground: #fafafa`
  - `--card: #09090b` — `--card-foreground: #fafafa`
  - `--popover: #09090b` — `--popover-foreground: #fafafa`
  - `--primary: #fafafa` (inverted on light)
  - `--secondary: #27272a` — `--muted: #18181b`
  - `--muted-foreground: #a1a1aa`
  - `--accent: #27272a` — `--destructive: #d1242f`
  - `--border: #222225` — `--border-muted: #232324` — `--input: #27272a` — `--ring: #d4d4d8`
  - **`--brand: #2e1b9c`** (deep indigo) + `--brand-foreground: #fff` + `--brand-text: #A599E9`
  - `--radius: 0px` (reference uses sharp + pill radii, not rounded-2xl cards). Add `--radius-pill: 100px`.
  - Light mirror: `--background: #fff` / `--foreground: #09090b` / `--primary: #18181b` / `--border: #e4e4e7`.
- **Layout container**: `w-[90vw] md:w-[80vw] max-w-[1189px]` centered, NOT a generic `.container`. The reference uses 1189px max.
- **Navbar**: `fixed top-0 h-[85px] bg-black border-y border-border`. Logo (custom SVG wordmark) left, nav links center, primary pill CTA right. Mobile: hamburger.
- **Hero shell**: `border border-border border-b-0` panel containing
  1. Top announcement strip (icon + announcement link + deals/secondary row on lg)
  2. 10-column `grid-cols-10` with `dash-*` utility classes forming the dashed-grid panel around the headline
  3. Big two-line headline, monospace CTA pill (`npm i …` style command, replaced with `npm i @ragify/cli` OR a `POST /api/v1/workspaces` snippet), secondary outline pill
  4. Mix-blend-overlay noise layer on top (`mix-blend-overlay bg-repeat`)
- **Section vocabulary** (in order):
  1. Navbar
  2. Hero with announcement strip + dashed grid + headline + CTA pills
  3. **"//the frontier RAG agent."** — large statement + subheadline + visual (terminal mockup of a `POST /api/v1/workspaces/:id/query` curl)
  4. **"//stop patching AI hallucinations."** — split compare panel (Without Ragify vs. With Ragify) with quote-flicker animation
  5. **"Hello, Ragify."** — retrieval-engine explainer with numbered capability list (`01 … 07 …`)
  6. **"Plans for every team."** — Free / Pro / Enterprise pricing with pill CTAs
  7. **"//take command of your knowledge."** — 3-up value stack (Citations per answer / Sources per workspace / Latency p50)
  8. **"Questions, answered."** — FAQ accordion (Ragify-specific questions)
  9. **"Latest from Ragify"** feed (v0.9 hybrid retrieval / v0.8 templates / v0.7 Java SDK / v0.6 citation export)
  10. **"Ready to ground your answers?"** — secondary CTA band
  11. Footer (Ragify 4 columns: Product, Developers, Company + brand+social; legal row)
- **Components**: `rounded-[100px]` pill buttons everywhere; dashed-grid panels; mix-blend-overlay noise PNG; monospace `[Thinking]` style; `font-mono` for inline-code chips; `tabular-nums` for prices.
- **Motion**: scroll-reveal, quote-flicker, terminal typing. Lightweight IntersectionObserver + CSS keyframes (no GSAP / framer-motion unless already present).
- **Footer**: 4-col, then bottom legal row, plus social icons (X / LinkedIn / GitHub). Brand wordmark left + social block.

## Copy Translation (reference → Ragify)

| Reference copy | Ragify replacement | Where |
| --- | --- | --- |
| "Command Code — AI coding agent with taste" | "Ragify — Grounded answers from your documents" | `<title>`, meta description, OG tags |
| Logo wordmark "COMMAND CODE" | Logo wordmark "RAGIFY" | Navbar, Footer, Auth pages |
| Nav: Docs / Features / About / Pricing / Contact / GOAT | Nav: Docs / Features / Pricing / Demo / Blog | Navbar |
| Navbar CTA "Sign Up" | Navbar CTA "Get started" | Navbar |
| Hero H1 "Command Code with your taste" / "//the frontier coding agent." | Hero H1 "Grounded answers," / "not hallucinations." + "//the frontier RAG agent." | Hero |
| Hero subhead | "Upload PDFs, Markdown, code, and JSON into isolated workspaces. Ragify retrieves the right context and answers with exact source citations." | Hero |
| Hero CTA pill `npm i -g command-code` | Hero CTA pill `npm i @ragify/cli` | Hero |
| Hero secondary CTA "Docs" | Hero secondary CTA "Read the docs" | Hero |
| Announcement strip "Command Code raised $5M seed." | Announcement strip "Ragify is in private beta — request access." | Hero top strip |
| Deals row (MiMo / Gemini / MiniMax) | Capabilities row ("Citations per answer", "Hybrid retrieval", "Local-first chat") | Hero top strip |
| Section "//the frontier coding agent." + terminal mockup of `npm i -g command-code` | Section "//the frontier RAG agent." + terminal mockup of a `POST /api/v1/workspaces/:id/query` curl returning a cited answer | FrontierSection |
| Section "//stop patching AI slop." Without Taste vs Mmmmm. Taste compare | Section "//stop patching AI hallucinations." Without Ragify vs With Ragify compare (one pane shows a generic LLM answer with no citations, other shows a cited Ragify answer) | SlopSection |
| Section "Hello, taste. The meta neuro-symbolic AI model that pairs LLMs with your coding taste." + 01-07 list | Section "Hello, Ragify. The retrieval engine that grounds every LLM answer in your workspace." + 01-07 numbered capability list: (01) Isolated workspaces, (02) Multi-format ingestion (PDF / Markdown / TS / Python / JSON / CSV), (03) Hybrid dense + sparse retrieval, (04) Exact source citations per claim, (05) Streaming chat with local persistence, (06) REST + Python/Java/TypeScript SDKs, (07) Private by default — never used to train public models | RagifyExplainer |
| Section "Subscribe. Be a GOAT." pricing with $1/mo, "50+ models", "Subscribe to GOAT" | Section "Plans for every team." three-tier pricing (Free / Pro / Enterprise) styled identically — pill CTAs ("Start free", "Start with Pro", "Contact sales"); drop the "50+ models" chip and the "Subscribe to GOAT" wording | PlansPricing |
| Section "//take command of your code." 3-up value stats (Code 10× / Reviews / Speed / Bugs) | Section "//take command of your knowledge." 3-up value stats rewritten for RAG (Citations per answer, Sources per workspace, Latency p50) | ValueStack |
| FAQ "How is Command Code different from Cursor or Copilot?" etc. | FAQ rewritten for Ragify: "How is Ragify different from uploading PDFs to ChatGPT?", "What does 'grounded' actually mean?", "Which file formats are supported?", "Is my data private?", "How do citations work?", "Do I need an API key?" | FAQSection |
| Section "Changelog" latest-feed (1.24.0 / 1.25.0 / 1.26.0 / 1.27.0) | Section "Latest from Ragify" feed driven by `marketing/sections.ts` `LATEST_FEED` (typed `ChangelogEntry[]`); illustrative entries: "Hybrid BM25 + dense retrieval (v0.9)", "Workspace templates (v0.8)", "Java SDK alpha (v0.7)", "Per-workspace citation export (v0.6)" — all marked `type: 'feature' | 'fix' | 'breaking'` | LatestFeed |
| Section "Ready to code with your taste? Join 29K+ developers…" CTA band | Section "Ready to ground your answers? Start your first workspace in under a minute." CTA band | SecondaryCTA |
| Footer columns | Footer columns rewritten for Ragify surface (Product: Demo / Features / Pricing / Changelog / Status) (Developers: Docs / Python SDK / Java SDK / TypeScript SDK / API Reference) (Company: About / Blog / Careers / Brand / Security) (Legal: Privacy / Terms) | Footer |
| Footer social icons (X / LinkedIn / Discord / GitHub) | Keep X / LinkedIn / GitHub; drop Discord unless a real link exists in `prospects.yaml` / repo — placeholder for now | Footer |
| Brand wordmark + social block | Ragify wordmark + social block (X, LinkedIn, GitHub) | Footer |
| Auth page titles (Sign in / Sign up) | Unchanged — Sign in / Sign up. The visual treatment (dashed-grid centered panel, Geist, pill submit) is what matches the reference. | Auth pages |
| DemoConsole (currently in landing) | Drop DemoConsole; replaced by `TerminalMockup` inside FrontierSection (which renders the curl/query response). | Landing composition |

## Current → Target File Mapping

| Current file | Action |
| --- | --- |
| `web/src/index.css` | Rewrite theme tokens to reference palette; add Geist + Geist Mono @import; add `.dash-*` utilities; add `.noise-overlay`, `.marquee`, `[data-shimmer]` keyframes; remove `@fontsource-variable/inter` |
| `web/src/main.tsx` | No structural change; default theme becomes `dark` (ThemeProvider init) |
| `web/src/components/theme-provider.tsx` | Default to `"dark"` (storage key still `"theme"`), keep light/dark/system cycle |
| `web/src/components/Logo.tsx` | Replace Lucide brain + text with **inline SVG wordmark** for "Ragify" (mirror reference wordmark proportions). Reusable as `<Logo size="sm\|md\|lg" />` |
| `web/src/components/navbar.tsx` | Rebuild as **fixed black navbar** matching reference (`h-[85px]`, `bg-black`, `border-y`, max-w-1189 inner, pill CTA on right). **Copy: nav links = `Docs / Features / Pricing / Demo / Blog`**, CTA = `Get started`. |
| `web/src/components/marketing/` | New directory of section components — see below |
| `web/src/pages/LandingPage.tsx` | Compose sections from `components/marketing/*` in the reference's 11-section order. **All section copy sourced from `marketing/sections.ts`** (single source of truth). |
| `web/src/pages/PrivacyPage.tsx`, `pages/TermsPage.tsx` | Restyle card to match reference (dashed-grid panel); copy is Ragify-specific legal text (placeholder if not finalized) |
| `web/src/pages/auth/{Layout,SignIn,SignUp}.tsx` | Centered dashed-grid panel, pill buttons, Geist typography, **Ragify brand**. Form labels/copy unchanged. |
| `web/src/components/workspaces/AppSidebar.tsx` | Restyle to reference sidebar (dark bg, hover-foreground, monospace shortcuts). Keep Base UI sidebar primitives. |
| `web/src/components/workspaces/Navbar.tsx` | Match reference inner navbar (`h-[57px]`, border-b, `SidebarTrigger` slot, pill avatar). |
| `web/src/pages/workspaces/{Layout,Workspaces,Overview,Chat,Upload,Settings}.tsx` | Apply reference tokens; replace rounded-2xl cards with dashed-grid panels; pill buttons; new heading style; preserve all functionality (queries, mutations, polling, optimistic UI, abort, streaming). |
| `web/src/components/ui/button.tsx` | Add `pill` variant + `outline-pill` variant; keep existing `default/outline/secondary/ghost/destructive/link`. |
| `web/src/components/ui/card.tsx` | Add dashed-grid variant (`<Card variant="dashed">`) using `.dash-*` utilities; default becomes sharp-edged. |
| `web/src/components/marketing/Reveal.tsx` | Upgrade to match reference behavior (single observer, supports `delayMs`, `direction="up\|left\|right"`, prefers-reduced-motion). |

## New Files to Add

```
web/src/components/marketing/
  Pill.tsx                    # Pill + OutlinePill + AnimatedButton (mirror-shell with noise)
  NoiseOverlay.tsx            # mix-blend-overlay repeating noise layer
  DashedPanel.tsx             # Dashed-grid panel (uses .dash-* utilities)
  Wordmark.tsx                # inline SVG wordmark "RAGIFY" used in nav + footer
  Reveal.tsx                  # upgraded reveal (replaces current)
  Section.tsx                 # shared section container (max-w-1189 inner, dashed-grid bg opt)
  Hero.tsx                    # announcement strip + dashed grid hero + headline + CTAs
  FrontierSection.tsx         # "//the frontier RAG agent." statement + TerminalMockup
  SlopSection.tsx             # "//stop patching AI hallucinations." without/with Ragify compare
  RagifyExplainer.tsx         # "Hello, Ragify." + numbered capability list (01-07)
  PlansPricing.tsx            # "Plans for every team." Free / Pro / Enterprise (replaces old pricing toggle)
  ValueStack.tsx              # "//take command of your knowledge." 3-up stats
  FAQSection.tsx              # "Questions, answered." accordion (rewritten for Ragify)
  LatestFeed.tsx              # "Latest from Ragify" feed driven by LATEST_FEED
  SecondaryCTA.tsx            # "Ready to ground your answers?" CTA band
  Footer.tsx                  # reference footer (4 cols + bottom row)
  TerminalMockup.tsx          # terminal visual used in FrontierSection (typing animation)
  QuoteFlicker.tsx            # quote flicker animation used in SlopSection
  sections.ts                 # exported copy/data (FEATURES_NUM, FAQ_ITEMS, PRICING, LATEST_FEED, VALUE_PROPS, FOOTER_COLUMNS)
```

## Theme + Tokens (single source of truth)

`web/src/index.css` rewrites the `:root`/`.dark` block:

```css
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";
@import url("https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600;700&display=swap");
@import "katex/dist/katex.min.css";

@custom-variant dark (&:is(.dark *));

@theme inline {
  --font-sans: "Geist", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  --font-heading: var(--font-sans);
  --color-brand: var(--brand);
  --color-brand-foreground: var(--brand-foreground);
  --color-brand-text: var(--brand-text);
  --color-border-muted: var(--border-muted);
  /* …all existing mappings… */
  --radius: 0px;
  --radius-pill: 100px;
}

:root {
  --background: #fff;
  --foreground: #09090b;
  --card: #fff;
  --card-foreground: #09090b;
  --popover: #fff;
  --popover-foreground: #09090b;
  --primary: #18181b;
  --primary-foreground: #fafafa;
  --secondary: #f4f4f5;
  --secondary-foreground: #18181b;
  --muted: #f4f4f5;
  --muted-foreground: #71717a;
  --accent: #f4f4f5;
  --accent-foreground: #18181b;
  --destructive: #f85149;
  --warning: #d1aa24;
  --warning-foreground: #070907;
  --border: #e4e4e7;
  --border-muted: #eaeaec;
  --input: #e4e4e7;
  --ring: #18181b;
  --sidebar: #fafafa;
  --brand: #2e1b9c;
  --brand-foreground: #fff;
  --brand-text: #2e1b9c;
}

.dark {
  --background: #000;
  --foreground: #fafafa;
  --card: #09090b;
  --card-foreground: #fafafa;
  --popover: #09090b;
  --popover-foreground: #fafafa;
  --primary: #fafafa;
  --primary-foreground: #18181b;
  --secondary: #27272a;
  --secondary-foreground: #fafafa;
  --muted: #18181b;
  --muted-foreground: #a1a1aa;
  --accent: #27272a;
  --accent-foreground: #fafafa;
  --destructive: #d1242f;
  --border: #222225;
  --border-muted: #232324;
  --input: #27272a;
  --ring: #d4d4d8;
  --sidebar: #18181b;
  --brand: #2e1b9c;
  --brand-foreground: #fff;
  --brand-text: #A599E9;
}
```

Add `.dash-*` utilities (extracted from reference CSS), `.noise-overlay`, `[data-shimmer]`, marquee keyframes, `font-mono` defaults, and `body { font-feature-settings: "ss01","cv11"; }` for Geist polish. `motion-safe:` reveal keyframes (`fade-up`, `fade-left`, `fade-right`).

## Code Reusability Strategy (taste-aligned)

1. **One button family** — `<Pill>` and `<OutlinePill>` (in `marketing/Pill.tsx`) wrap `Button` with `rounded-[100px]` and brand styling. All CTAs across landing + auth + dashboard go through these two. `asLink` prop composes with `Link` or `<a>`.
2. **One panel** — `<DashedPanel>` wraps `<div>` with `.dash-*` classes; props for `as`, `className`, `children`. Used by Hero, Slop compare panels, auth cards, workspace cards.
3. **One reveal** — single `Reveal` with `direction` + `delayMs` props, used everywhere.
4. **One section container** — `Section` (vertical padding, dashed-grid background option, max-width-1189 inner). All landing sections + workspace sections reuse it.
5. **One wordmark** — `Wordmark` SVG used by Navbar, Footer, SignIn/SignUp.
6. **One copy source** — `marketing/sections.ts` exports all Ragify-specific text: `FEATURES_NUM`, `FAQ_ITEMS`, `PRICING`, `LATEST_FEED`, `VALUE_PROPS`, `FOOTER_COLUMNS`, `HERO_COPY`, `FRONTIER_COPY`, `SLOP_COPY`, `EXPLAINER_COPY`, `TERMINAL_DEMO`, `ANNOUNCEMENT_STRIP`. **No marketing copy lives in JSX except as `data.label` references.**
7. **Marketing copy is domain-general** (per taste: "RAG prompts and graph logic to remain domain-general") — copy in `sections.ts` describes Ragify's grounded-RAG value prop without locking the brand voice.

## Page-by-Page Changes

### Landing (`pages/LandingPage.tsx`)
Composes sections in reference order, reading copy from `marketing/sections.ts`:
`<Navbar/> <Hero/> <FrontierSection/> <SlopSection/> <RagifyExplainer/> <PlansPricing/> <ValueStack/> <FAQSection/> <LatestFeed/> <SecondaryCTA/> <Footer/>`. Removes the old Hero/Formats/Features/How-it-works/Pricing toggle/FAQ/CTA-band code. Removes `DemoConsole` import (replaced by `TerminalMockup` inside `FrontierSection`).

### Navbar (`components/navbar.tsx`)
- Fixed top, `h-[85px] px-8 bg-black border-y border-border`, inner `w-[90vw] md:w-[80vw] max-w-[1189px] mx-auto`.
- Left: `<Wordmark/>`. Center: nav links (`Docs`, `Features`, `Pricing`, `Demo`, `Blog`) styled as reference pill nav (`rounded-full px-4 h-9 text-sm font-medium text-muted-foreground/80 hover:text-background hover:bg-foreground`).
- Right: `<Pill asLink href="/sign-up" variant="primary">Get started</Pill>` plus theme toggle and avatar popover.
- Mobile: hamburger + slide-down sheet (`<Sheet>` from existing `ui/sheet.tsx`).

### Hero (`marketing/Hero.tsx`)
- Container: `<DashedPanel className="border-b-0">`.
- Announcement strip: top bar with brand-styled icon + "Ragify is in private beta — request access." link + secondary row (lg+) showing capabilities ("Citations per answer", "Hybrid retrieval", "Local-first chat").
- 10-col dashed grid + headline ("Grounded answers," / "not hallucinations." + "//the frontier RAG agent.") + subhead + CTAs (`Pill` "Start free" + `OutlinePill` "See how it works"). Primary CTA pill command is `npm i @ragify/cli`.
- `NoiseOverlay` layered on top with `mix-blend-overlay`.

### FrontierSection (`marketing/FrontierSection.tsx`)
- Heading "//the frontier RAG agent."
- Subhead: "Stop uploading documents to a model that forgets them. Ragify indexes your workspace once, retrieves the right context every time, and cites every claim."
- Right pane: `<TerminalMockup script="terminal-demo-script">` (defined in `sections.ts`) — animates a `curl -X POST /api/v1/workspaces/:id/query` + streaming JSON response with citation chips.

### SlopSection (`marketing/SlopSection.tsx`)
- Heading "//stop patching AI hallucinations."
- Two-column compare panel:
  - **Without Ragify** (left, muted): a generic LLM answer paragraph with a "no citations" badge.
  - **With Ragify** (right, brand border): the same question answered with `[file.pdf:page 12]` citation chips inline.
- `<QuoteFlicker>` animates the With-Ragify answer to suggest typing in.

### RagifyExplainer (`marketing/RagifyExplainer.tsx`)
- Heading "Hello, Ragify." + subhead "The retrieval engine that grounds every LLM answer in your workspace."
- 01–07 numbered capability rows:
  01. **Isolated workspaces** — `npx ragify workspace create`
  02. **Multi-format ingestion** — PDFs, Markdown, TypeScript, Python, JSON, CSV
  03. **Hybrid dense + sparse retrieval** — BM25 + vector recall
  04. **Exact source citations** — every claim linked to file + page
  05. **Streaming chat, local-first** — sessions persist in the browser
  06. **REST + Python / Java / TypeScript SDKs** — programmatic access
  07. **Private by default** — your documents are never used to train public models
- Each row uses `<DashedPanel>` with monospace shortcut on the right.

### PlansPricing (`marketing/PlansPricing.tsx`)
- Heading "Plans for every team." + subhead "Start free. Upgrade when your team needs more. Every plan includes grounded citations."
- Three tier cards (Free / Pro / Enterprise) styled identically to reference pricing blocks.
- Pricing values from `sections.ts::PRICING`:
  - Free — `$0` — "For individuals exploring grounded AI."
  - Pro — `$29 / mo` — "For professionals managing deep knowledge bases." (highlight: "Most popular" pill)
  - Enterprise — `Custom` — "For organizations with dedicated vector clusters."
- CTAs: `Start free`, `Start with Pro`, `Contact sales`. All pill buttons.

### ValueStack (`marketing/ValueStack.tsx`)
- Heading "//take command of your knowledge."
- Three stats from `sections.ts::VALUE_PROPS`:
  - **Citations per answer** — `5–10`
  - **Sources per workspace** — `1k+`
  - **Latency p50** — `<1.2s`
- Stat row uses dashed-grid panels with tabular-nums and Geist-Mono labels.

### FAQSection (`marketing/FAQSection.tsx`)
- Heading "Questions, answered."
- FAQ_ITEMS from `sections.ts`:
  - "How is Ragify different from uploading PDFs to ChatGPT?"
  - "What does 'grounded' actually mean?"
  - "Which file formats are supported?"
  - "Is my data private? Is it used for training?"
  - "How do citations work?"
  - "Do I need my own LLM API key?"
  - "Can I query multiple workspaces at once?"
- Accordion UI matches reference: `<DashedPanel>` row, chevron rotates, content fades in.

### LatestFeed (`marketing/LatestFeed.tsx`)
- Heading "Latest from Ragify."
- Feeds from `LATEST_FEED` (typed `ChangelogEntry[]`):
  - v0.9 — Hybrid BM25 + dense retrieval (feature)
  - v0.8 — Workspace templates (feature)
  - v0.7 — Java SDK alpha (feature)
  - v0.6 — Per-workspace citation export (feature)
- Each entry row: version chip, title, date, `type` badge.

### SecondaryCTA (`marketing/SecondaryCTA.tsx`)
- Heading "Ready to ground your answers?" + subhead "Start your first workspace in under a minute. No credit card required."
- Two pill CTAs: `Get started` (primary), `Sign in` (outline).

### Footer (`marketing/Footer.tsx`)
- 4-col grid (md+):
  - **Ragify** — wordmark + one-liner + social icons (X / LinkedIn / GitHub).
  - **Product** — Demo, Features, Pricing, Changelog, Status.
  - **Developers** — Docs, Python SDK, Java SDK, TypeScript SDK, API Reference.
  - **Company** — About, Blog, Careers, Brand, Security.
  - **Legal** — Privacy, Terms (placed in bottom row).
- Bottom row: © year + small tagline + Privacy / Terms links.

### Auth pages
- `Layout.tsx`: full-screen dark with centered dashed-grid panel containing children + footer wordmark.
- `SignIn.tsx`: form using shadcn `Form` + zod (already in use). Submit button becomes `<Pill>`. Demo-credential button becomes `<OutlinePill>`. Copy unchanged.
- `SignUp.tsx`: same; keep `?plan=` chip but restyle.

### Workspaces shell
- `Layout.tsx`: top navbar (reference inner navbar), sidebar (reference dark sidebar with monospace shortcuts).
- `Workspaces.tsx`: page header + tag pills + search + card grid (cards become `DashedPanel` with hover lift). Empty state and create dialog restyled.
- `Overview.tsx`: dashed-grid header + 4-stat strip + action grid (uses existing TanStack queries).
- `Chat.tsx`: keep all data flow; only visual — pill send button, dashed-grid thread panel, monospace `[Thinking]` labels, Geist-Mono code blocks.
- `Upload.tsx`: dashed-grid dropzone, dashed-grid pending list.
- `Settings.tsx`: tabs restyled to reference's tab strip; "Save" buttons become `<Pill>`.

### Components to add/upgrade
- `components/ui/button.tsx`: add `pill` and `outlinePill` variants (radius-100px, brand colors).
- `components/ui/card.tsx`: add `variant="dashed"` that applies `.dash-*` borders and sharp corners.
- `components/ui/input.tsx`, `textarea.tsx`: keep but switch focus ring to `--brand`.

## Implementation Order

1. **Theme + tokens** — rewrite `index.css`, switch font import, add `.dash-*`/`.noise-overlay`/reveal keyframes. Verify tokens work in both modes.
2. **Shared primitives** — `Pill`, `OutlinePill`, `DashedPanel`, `Wordmark`, upgraded `Reveal`, `Section`, `NoiseOverlay`. Add `pill` variant to `Button`. Add `dashed` variant to `Card`.
3. **Theme provider default** — set dark as default; keep cycle.
4. **`marketing/sections.ts`** — author all Ragify copy in one typed module. **No JSX file should contain literal marketing copy** (per code-reusability strategy).
5. **Navbar** — rebuild top navbar (Ragify wordmark, nav links = Docs / Features / Pricing / Demo / Blog, CTA = Get started).
6. **Landing sections** — implement each marketing section component in order using the primitives; compose `LandingPage.tsx`.
7. **Footer** — new `marketing/Footer.tsx`.
8. **Auth pages** — restyle Layout + SignIn + SignUp using primitives.
9. **Workspace shell** — `Navbar` + `AppSidebar` + `Layout` + `Workspaces` + `Overview`. Preserve functionality.
10. **Workspace interior** — `Chat`, `Upload`, `Settings`. Visual-only changes; queries/mutations untouched.
11. **Legal pages** — restyle Privacy/Terms to match (copy remains Ragify-specific; placeholder if not finalized).
12. **Polish pass** — keyboard focus rings, prefers-reduced-motion, dark/light sweep, responsive sweep at `sm`/`md`/`lg`/`xl`.

## Critical Files to Modify

- `web/src/index.css` (full token rewrite + utility additions)
- `web/src/components/theme-provider.tsx` (default dark)
- `web/src/components/Logo.tsx` (replace with `Wordmark` SVG — "RAGIFY" wordmark)
- `web/src/components/navbar.tsx` (rebuild — Ragify nav links)
- `web/src/components/ui/button.tsx` (add pill variants)
- `web/src/components/ui/card.tsx` (add dashed variant)
- `web/src/pages/LandingPage.tsx` (compose new sections — copy from `sections.ts`)
- `web/src/pages/PrivacyPage.tsx`, `TermsPage.tsx` (Ragify-specific copy, dashed-panel visual)
- `web/src/pages/auth/{Layout,SignIn,SignUp}.tsx`
- `web/src/components/workspaces/{Navbar,AppSidebar,Logout}.tsx`
- `web/src/pages/workspaces/{Layout,Workspaces,Overview,Chat,Upload,Settings}.tsx`
- `web/src/components/marketing/Reveal.tsx` (upgrade)
- **All new files under `web/src/components/marketing/`** listed above
- **Add** `web/public/noise.webp` (small 200×200 tiled noise texture; can be generated programmatically — see below)
- **Add** `web/src/components/marketing/sections.ts` (the single copy source)

### Generating the noise.webp asset

```bash
python3 -c "
from PIL import Image
import random
img = Image.new('L', (200,200), 0)
px = img.load()
for y in range(200):
    for x in range(200):
        px[x,y] = random.randint(0,255)
img.save('web/public/noise.webp', 'WEBP', quality=70, method=6)
"
```

## Verification

1. **Visual parity sweep**: open `/` in light + dark, scroll through all 11 sections, compare side-by-side with reference. Confirm dashed-grid panel renders, brand pill CTA is `#2e1b9c`, noise overlay is visible on hero, footer is 4-col with bottom legal row. **Confirm zero literal "Command Code" / "taste-1" / "GOAT" copy remains** in any rendered section.
2. **Build**: `pnpm -C web build` — must complete without TS or oxlint errors.
3. **Lint**: `pnpm -C web lint` — fix any new oxlint complaints.
4. **Type check**: `pnpm -C web exec tsc -b`.
5. **Dev server smoke**: `pnpm -C web dev` — visit `/`, `/sign-in`, `/sign-up`, `/workspaces` (after seeding a session), `/workspaces/:id/chat`, `/workspaces/:id/upload`, `/workspaces/:id/settings`. Confirm:
   - Chat still streams + aborts
   - Upload still polls status
   - Settings tabs still mutate
   - Theme toggle cycles correctly
6. **Copy audit**: `grep -RIn "command code\|taste-1\|GOAT\|Subscribe to GOAT\|npm i -g command-code" web/src` returns no marketing-page matches.
7. **Reduced motion**: enable OS reduced-motion and confirm reveals, marquees, quote-flicker fall back to instant.
8. **Responsive**: at 375 / 768 / 1024 / 1280 / 1536 px — confirm dashed-grid panels collapse cleanly, mobile menu opens, no horizontal scroll.
9. **Contrast**: spot-check `[Thinking]` label, pill CTA, link colors against WCAG AA in both modes.
10. **Bundle**: confirm `pnpm -C web build` does not balloon (no GSAP added; framer-motion only if already present).

## Out of Scope

- Backend / API changes
- Functional changes to queries, mutations, polling, streaming
- Adding new features (real billing, real changelog CMS, real status page) — copy uses illustrative placeholders bound to `marketing/sections.ts`
- E2E test suite additions (existing tests, if any, are kept)
