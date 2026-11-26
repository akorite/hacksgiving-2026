# Cupbearer — Frontend & Telegram Surface Specification

Canonical visual, chat-interaction, and motion contract for Cupbearer's **Telegram personal-agent bot** (`src/cupbearer/butler/telegram_bot.py`) and its companion **X-Ray Light-Table deep-link page** (`src/cupbearer/butler/static/index.html`).

## Two-Surface Personal-Agent Model

1. **Primary surface — Telegram Bot (`@CupbearerBot`):** Where the owner lives day to day. Forward any PDF, script, URL, or GitHub repo (or run `/replay invoice`, `/replay skill`, `/replay link`, `/sync`). Cupbearer replies in chat with:
   - An **annotated X-Ray PNG** (for PDFs/links, with crimson hidden-text boxes composited directly inside the Airlock) or a concise canary tripwire breakdown (for scripts/skills).
   - A **2-sentence verdict** in Cupbearer's calm, dry-witted voice plus Pinecone baseline/immune memory findings and exact NVMe checkpoint rollback latency (`v1 restored in 340 ms`).
   - **Inline keyboard buttons:** `Approve and file to Box`, `Discard`, and `Open interactive X-Ray` (deep-linking straight to `{PUBLIC_BASE_URL}/i/{id}`).
   - **Natural reply-to-chat Q&A:** Replying to any Cupbearer verdict message answers scoped questions about that specimen right in Telegram.
2. **Secondary surface — Focused X-Ray Light-Table (`/` and `/i/{id}` on Butler's Sprite URL):** Opens directly onto the requested specimen with the tactile **X-Ray Wipe Curtain** when tapped from Telegram, and provides a compact Attack Replay + intake view at `/` for Hacksgiving judges testing the live demo URL without joining the owner's personal bot.

## Aesthetic Direction: The Forensic Light-Table

Cupbearer is a personal poison-taster, not an enterprise SIEM. The Light-Table reads like an Apple/Braun-grade illuminated inspection bench: warm smoked obsidian surfaces, alabaster ink, subtle translucent glass chrome, and one tactile centerpiece—an interactive **X-Ray Wipe Curtain** dragged directly across a specimen to reveal hidden prompt injections underneath.

### Explicitly Rejected Defaults

- No blue-tinted `#0F172A` SaaS slate cards, no neon `#22C55E` hacker green, no violet/lavender accents.
- No tracked-out `ALL-CAPS` eyebrows, no middle-dot (`A · B · C`) metadata chains, no `→` suffixes on buttons, no emoji icons.
- No card-inside-card nesting deeper than two layers, no `transition: all`, no `scale(0)` entrances, no `ease-in` curves, and no scroll-triggered fades.

## Color & Material Tokens

| Token | Value | Role |
|---|---|---|
| `--bg-canvas` | `#121210` | Warm smoked obsidian desk ground |
| `--bg-surface` | `#1A1917` | Vault feed rail & evidence drawer |
| `--bg-lighttable` | `#22201D` | Calibrated specimen well behind rendered PDFs and screenshots |
| `--border-hairline` | `rgba(243, 239, 230, 0.08)` | Structural separators |
| `--ink-primary` | `#F3EFE6` | Warm alabaster primary copy (14.5:1 on canvas) |
| `--ink-muted` | `#9C968B` | Warm pewter secondary copy (5.8:1 on canvas) |
| `--accent-brass` | `#D4A14B` | Signature Cupbearer accent (focus rings, curtain handle, active selection) |
| `--verdict-hostile` | `#E5484D` | Signal crimson — `Hostile` verdicts, X-Ray injection overlays, tripped canaries |
| `--verdict-suspicious` | `#E5A00D` | Amber — `Suspicious` holds and non-financial baseline drift |
| `--verdict-safe` | `#30A46C` | Botanical emerald — `Safe` / `Verified-Vault` seal |

- **Top Command Bar material:** `background: rgba(26, 25, 23, 0.76); backdrop-filter: blur(20px) saturate(160%);` with a `1px` top/bottom hairline. Under `@media (prefers-reduced-transparency: reduce)`, degrade to solid `#1A1917` with `backdrop-filter: none`.

## Typography

- **UI & Headlines:** `Instrument Sans`, fallback `-apple-system, BlinkMacSystemFont, system-ui, sans-serif`.
  - Verdict headlines: `clamp(1.1875rem, 1.5vw, 1.375rem)`, weight `600`, `line-height: 1.2`, `letter-spacing: -0.025em`.
  - Body & Cupbearer briefs: `15px`, `line-height: 1.5`, `letter-spacing: 0`, measure `<= 68ch`, sentence case everywhere.
- **Forensic Evidence Only:** `JetBrains Mono`, `12.5px`, `font-variant-numeric: tabular-nums` — reserved strictly for canary env/file names, routing diffs, blocked IPs, SHA-256 prefixes, and checkpoint rollback timings.

## Layout & Responsive Breakpoints

- **Desktop (`>= 1100px`):** Sticky `56px` translucent command bar. At `/`, renders a 3-zone grid (`280px` Vault Feed rail | top Verdict Bar over a `60%` Specimen Light-Table and `40%` Evidence & Ask Cupbearer column) with 3 one-click Attack Replays for judges. At `/i/{id}` (deep-linked from Telegram), opens directly onto the requested specimen (`60%` Light-Table + `40%` Evidence & Ask Cupbearer) with a toggleable Vault Feed drawer.
- **Tablet (`768px–1099px`):** Evidence & Ask Cupbearer stacks beneath the Light-Table.
- **Mobile (`<= 767px`, verified at `390px`):** Single column with a collapsible Vault Feed drawer, full-width primary actions, `>= 44×44px` tap targets with `>= 8px` spacing, and zero horizontal overflow.
- Set `scroll-padding-top: 64px` on the scroll container so sticky top chrome never obscures `:focus-visible`.

## Signature Interactions & Motion Contract

- **Custom easings:**
  - `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` (entrances, press feedback, segmented pill)
  - `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)` (X-Ray curtain sweep)
- **X-Ray Wipe Curtain:**
  - Overlay layer clips via direct `element.style.clipPath = "inset(0 <pct>% 0 0)"` (never mutating an inherited CSS variable on a parent container).
  - 1:1 pointer tracking via Pointer Events (`setPointerCapture`), respecting grab offset, with progressive rubber-band damping past boundaries and keyboard control (`ArrowLeft`/`ArrowRight` `5%`, `Home`/`End`).
  - One orchestrated reveal sweep (`0% -> 58%`, `450ms var(--ease-in-out)`) when a detonation completes with hidden injections; instant swap under `prefers-reduced-motion: reduce`.
- **Mode Switch (`Human` / `Split X-Ray` / `Full X-Ray`):** Native `<button aria-pressed>` group with `clip-path` sliding highlight (`180ms var(--ease-out)`).
- **Press, Hover & Keyboard Rules:**
  - Pressable buttons: `transition: transform 140ms var(--ease-out), background-color 140ms ease; :active { transform: scale(0.97); }`.
  - Hover transforms/highlights strictly gated inside `@media (hover: hover) and (pointer: fine)`.
  - Keyboard feed navigation (`ArrowUp`/`ArrowDown`) has `0ms` animation.
  - Banners/toasts enter from `scale(0.96); opacity: 0` (`200ms` enter, `150ms` exit).
  - Live detonation displays a 4-stage pipeline stepper directly on the Light-Table (`Staging in Airlock` → `Running with canaries` → `Rolling back NVMe checkpoint` → `Checking Box & Pinecone`).

## Copy Voice, Accessibility & Security Hygiene

- **Voice:** Calm, concise, dry-witted personal butler. Active verb-object CTAs: `Inspect`, `Sync Box`, `Approve and file to Box`, `Discard`, `Recover Airlock`. Errors state what happened and how to fix it without apologizing.
- **Accessibility:** WCAG AA contrast (`>= 4.5:1`), visible `2px solid var(--accent-brass)` `:focus-visible` rings on every control, bespoke inline SVGs (`stroke-width: 1.75`, `aria-hidden="true"`), and `@media (prefers-reduced-motion: reduce)` cross-fade fallback.
- **Security:** 100% DOM-API / `textContent` rendering from external `static/app.js` and `static/styles.css` (zero inline `<script>` and zero `innerHTML` on untrusted or LLM content), enforced alongside `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; object-src 'none'` and `X-Content-Type-Options: nosniff`.
