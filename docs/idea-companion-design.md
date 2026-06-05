# Design: Idea Companion (a voice tutor on a walk)

Generated via office-hours, 2026-06-04. Mode: Builder. A branch of Personal Evolver.
Status: DRAFT (feasibility-gated, see The Assignment).

## What it is (one line)
A hands-free, real-time spoken tutor you talk to while walking. An idea pops up, you tap
once in Telegram, and you have a live bilingual (EN + 中文) conversation that teaches you the
fundamentals. It shows you a picture, saves what you learned to your Notion knowledge vault, and
(later) drops a deep illustrated report + quizzes you so it sticks.

## The wow (LOCKED, JJ picked this)
**The format is the product: a hands-free voice tutor on a walk.** Talking and listening, no screen,
no typing, while moving. That is the moment Hermes / OpenClaw cannot serve (they are text, you can't
text-chat mid-walk). Everything else (research, images, quiz, vault) is a supporting layer, NOT the
wow. Nail the live voice conversation first.

## Why this is NOT Hermes (the differentiation JJ pressure-tested)
- Hermes is a *doing* assistant (text, run tasks). This is a *learning* tutor (voice, teach + retain).
- "Conversation + backend research" alone = Hermes, no wow. Rejected.
- The wedge = **voice-first, hands-free, real-time, while walking** + it makes knowledge stick and
  compound. Different category, different job-to-be-done ("teach me while I walk," not "do a task").

## Locked decisions (office-hours)
| # | Decision | Choice |
|---|---|---|
| 1 | Voice mode | **True real-time** (OpenAI Realtime, barge-in), via a **Telegram Mini App** |
| 2 | Live depth | **Fundamentals only** live (basic concepts, in/outs). Snappy, low latency. |
| 3 | Deep research | **Async, after the walk.** A full illustrated report lands in Notion later. |
| 4 | Language | Bilingual EN + 中文 |
| 5 | The wow | Hands-free voice tutor on a walk (the format) |
| 6 | Scope home | A branch of Personal Evolver (weekly-review + Receipts → roadmap) |

## Premises (agree before building)
1. The single hardest, must-prove-first assumption is **live microphone + a Realtime voice session
   working inside a Telegram Mini App on JJ's iPhone.** If that fails, the whole real-time path fails.
2. The live conversation must feel low-latency and natural, or there is no wow. Tutoring quality +
   responsiveness is the product, not the feature checklist.
3. Deep research, images, quiz, and Notion saving are LAYERS added after the voice loop works. They
   do not gate the wow.

## Approaches
### Approach A: Telegram Mini App + OpenAI Realtime (RECOMMENDED, the wow path)
- Bot (BotFather) opens a Mini App (small web page on Modal) hosting the Realtime WebRTC client.
- Ephemeral-token endpoint mints short-lived Realtime sessions (OpenAI key never in the browser).
- Tutor system prompt: patient, explains fundamentals, adapts to follow-ups, bilingual.
- Effort: M. Risk: **High (the Telegram-web-view mic on iOS).**
- Pros: true hands-free barge-in, native in Telegram, the full wow.
- Cons: mic in Telegram's in-app browser is historically finicky on iOS. Must smoke-test first.

### Approach B: Telegram voice notes + fast STT/TTS (the FALLBACK)
- Turn-based: send a voice note, get a spoken reply. Whisper + GPT + TTS.
- Effort: S. Risk: Low.
- Pros: definitely works, robust on spotty signal.
- Cons: not interruptible, less "live." The safety net if A's mic fails.

### Approach C: Standalone PWA voice tutor (sidesteps the Telegram mic risk)
- A tiny web app JJ adds to her iPhone home screen; pure Safari WebRTC mic (rock-solid). Telegram
  used only to drop the topic + receive the report link.
- Effort: M. Risk: Low-Med.
- Pros: reliable mic + full real-time, no Telegram-web-view limitation.
- Cons: not "inside Telegram" (JJ wanted Telegram as the UI). Consider only if A's mic fails.

## Recommended approach
**A, gated on the mic smoke test. B is the pre-built fallback. C is the escape hatch if Telegram's
mic is the blocker.** Do not build the full thing until A's riskiest assumption is proven.

## Phasing (slow but sure)
1. **Smoke test (FIRST, go/no-go):** prove mic + a basic Realtime session in a Telegram Mini App on
   JJ's iPhone. ~30-60 min. If it fails → fall back to B or C before investing more.
2. **The wow (v1):** Mini App + Realtime bilingual tutor. Just the live conversation. Walk and talk.
3. **Layer: capture** each topic/conversation to a Notion "Learning Vault" page.
4. **Layer: visuals** a GPT-Image infographic on request / at key moments.
5. **Layer: deep report** async deep research → illustrated Notion report after the walk.
6. **Layer: quiz** spaced-recall pings via the bot.

## The walk → desk handoff (JJ's insight 2026-06-04)
The live voice tutor and the deep research are two halves of one flow, joined by a **handoff to a
research worker that lives inside Notion** (a Notion Worker, the `ntn ... Workers` foundation JJ
already set up). Concretely:
- **On the walk (voice):** ask for fundamentals AND issue async commands by voice, e.g. "draft a
  graph infographic on X in Notion," "go deep on Y." The tutor confirms and **dispatches a task to
  the Notion research worker.**
- **Async (Notion Worker):** the worker continues the deep research, compiles the detailed report,
  and builds the infographics IN Notion, while JJ keeps walking.
- **At the desk / on the phone (read):** when JJ is ready, the report is already compiled in Notion,
  waiting to be read. That is the transition: walk = listen + direct; desk = read the finished work.

This means the deep-research layer is not a Modal cron job; it is a **Notion-resident worker** the
voice agent commands. Stand on shoulders (Notion Workers), do not rebuild. Wire at Phase 5.

## Open questions
- Does this REPLACE Receipts as the demo, or run alongside? (affects timeline pressure)
- Notion structure: one "Learning Vault" DB, one page per topic (transcript + key points + report +
  images + quiz status). Confirm at build time.

## Success criteria (the wow)
JJ walks, taps the bot, and has a real, low-latency, hands-free bilingual spoken conversation that
teaches her a topic she was curious about. She did not touch the keyboard. It felt like a tutor.

## The Assignment (the one concrete next step)
Run the **mic smoke test** before any real build: a minimal Telegram Mini App that opens, asks for
mic permission, and runs a 30-second live OpenAI Realtime "say hello and chat" session on JJ's
iPhone. This single test decides A vs B/C and de-risks the entire product. Needs: a Telegram bot
token (BotFather) + an OpenAI API key.

## What I noticed about how you think
- You caught the real risk yourself: "what's the difference compared to OpenClaw or Hermes... there
  is no wow-ing effect." That's the question that kills bad products early. You asked it unprompted.
- You know your own learning style cold: "I learn more when I listen and reason and talk to someone."
  The product is shaped around a real need of yours, not a hypothetical user.
- "I just don't want to complicate it." You keep pulling toward the simplest thing that works. That
  instinct is why the wow got sharper, not bigger.
