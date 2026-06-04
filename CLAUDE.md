# Personal Evolver

> Gather everything you consume and produce, and each week turn it into a review you can read, hear, and ask questions of out loud.
> Entry point for any Claude Code session in this repo. Global conventions live in `~/.claude/CLAUDE.md`.

## What this is
A cloud, phone-first personal "evolution" platform. It aggregates JJ's **inputs** (YouTube/article links she drops to a Telegram bot, her Notion weekly journal) and **outputs** (GitHub commits, her knowledge vault via private git), synthesizes a **weekly review** into Notion, and turns it into **audio she can listen to on a walk and interrogate by voice** (bilingual EN + 中文). Built in parallel with Spendetector; **NOT a demo requirement.**

## The idea
Instead of doing the weekly reflection by hand, the system hands back a synthesis she can read in Notion, hear as a NotebookLM podcast, and question by voice while walking. Closest comparable is Exist.io (aggregates GitHub + read-later + media into weekly correlations), but none has Notion output, AI-coding-session capture, or an interrogatable audio review. That is the white space.

## Architecture
`Sources` → `Modal weekly cron` → `synthesis` → `Notion + audio layer`.

- **Inputs:** drop YouTube/article links to the Telegram bot (Google has NO search/YouTube-history API, so drop-link is the real, real-time method) → Notion (Entertainment/Reading DB). Plus JJ's **Notion weekly journal** (Notion API).
- **Outputs:** GitHub Events API (poll hourly; 30-day/300-event window). Vault via a **PRIVATE git repo** Modal clones (NOT Backblaze B2: that bucket is a restic-encrypted backup, not readable files; keep B2 for recovery).
- **Synthesis:** cluster → 2 to 6 themes + one recurring-lesson callback (the "3+ occurrences = a pattern" rule). Weekly mirror (A) + proactive just-in-time coach (C).
- **Listen:** NotebookLM Audio Overview via the **connected NotebookLM MCP** (`studio_create` audio → `download_artifact`). Supports Chinese. "Press play on a walk."
- **Ask:** an **OpenAI Realtime voice agent** grounded on the same synthesis (WebRTC, barge-in, bilingual, ~$0.05-0.10/min cached). NotebookLM's "Join" is English-only, manual, and has no API, so the Realtime agent is the dependable ask-layer.
- **Store + viz:** Notion (weekly review pages, sessions gallery + timeline, patterns DB, shareable Wrapped cards).

## The plan
Full plan with diagrams, the audio-layer design, and the roadmap: **`docs/plan.html`**. Decision record: `~/Documents/jj-knowledge-vault/agents/claude-code-m4/decisions/2026-06-04-notion-personal-products.md`.

## How to build
1. `/memory-loader` (mandatory).
2. `/planning-pipeline` **before any code**.
3. Build with Claude Code on `feat/` branches; Codex + context-free review gate.
4. Phase 1 = weekly review (read in Notion + NotebookLM listen). Phase 2 = the Realtime voice ask-layer. Cross-source insight needs a few weeks of data before it is meaningful.

## Open decisions (office-hours)
- Vault-to-git scope: the whole vault, or just `agents/claude-code-m4/{learning-journals, patterns, corrections.md, session-logs}`? (lean: just those.)
- Point to JJ's Notion weekly journal page and share it with the integration.
- Audio default language: EN / 中文 / per week?
- Listen tools: NotebookLM podcast + Realtime agent (both), or Realtime-only to start? (Realtime is the must.)

## Non-negotiables
- **Cloud-first (Modal), phone-first.** Never Mac-tethered.
- **Read the vault from a private git repo, not B2 restic.**
- **Privacy:** this is the most personal data; nothing sold; JJ's keys; stays in her Notion + cloud.
- No hardcoding. Cut a branch before the first edit. No em dashes in output.
