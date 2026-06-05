# Personal Evolver — JJ's input 2026-06-04 (captured verbatim-faithful)

## Rule: the Notion diary is NOT an input
- JJ's Notion weekly journal = her *already-reflected conclusions*. It is what she has already
  processed. It is NOT a source.
- What she wants: **authentic raw INPUT + OUTPUT of hers**, so the AI surfaces **new insights she
  might overlook** (things she did not already write down herself). The value is AI catching what
  she missed, not echoing her own reflection.
- Implication for sources: keep real work (GitHub) + real consumption (what she read/watched/searched).
  Drop the diary as a source.

## Vault → cloud: how it updates today (investigated)
- `/wrapup` commits the vault locally + pushes SKILLS to github, but does **NOT** push the vault repo
  to its github remote.
- `com.jj.vault-automation` (daily launchd) does a **restic backup to B2** + syncs some news/prompts
  to Notion. It does **not** push to the github git remote (and last night the B2 backup errored, exit 3).
- Net: the github remote `jjknowledgevault` updates only on a **manual push** → that is why it is stale.
- **JJ's directive:** pushing non-privacy vault commits to github should be **part of the wrap-up
  process**. (Correct + clean fix. To wire: push the 4 reflection dirs, or the whole private repo,
  at wrap-up so the cloud is always current.)
- GitHub repo vs B2: github = readable git files (a program can read them); B2 = restic ENCRYPTED
  backup for disaster recovery (not readable without restic key + full restore).

## PIVOT: the demo product = "Idea Companion" (a branch of Personal Evolver)
JJ is switching the near-term build to a smaller, demo-able piece. The weekly-review product we
planned today moves to the **roadmap**. This new branch is still PART of Personal Evolver (not a
separate project).

**The product, in her words (faithful):**
- She is walking / on the road. An idea or topic pops up: "oh what is this, I want to know more."
- She drops it to a **Telegram bot** (just for this).
- She does not have time to stop and read. She is a **listener-learner**: learns by listening,
  reasoning, and talking to someone.
- An **OpenAI Realtime voice agent** lets her **listen and speak** to reason through the idea,
  hands-free on the walk.
- The agent **executes research on her behalf** while they talk: pulls together **Google search**,
  builds a **detailed report with pictures**. She **loves pictures**, so the agent could also call
  **GPT-Image (ChatGPT-Image)** to generate **infographics** to help her understand.
- The agent can **quiz her later** (active recall).
- **All conversation history is saved into Notion**, organized properly → it **becomes one of her
  knowledge vaults**.

**Her open questions:**
1. How to use **Notion as a backend** (how to organize that information).
2. How to **interact with the Realtime voice agent through Telegram** (the UI).

**The demo she pictures:** come up with an idea/topic → have a conversation with it → **watch it
execute** on her behalf (Google search + detailed report with pictures) → get **infographics** to
understand → **quiz** her later.

**Scope direction:** build this small branch FIRST = the interface (Telegram bot) + OpenAI Realtime
voice agent + Notion backend + how the info is organized. Weekly-review + Receipts = roadmap.

**She asked Claude to: ask clarifying questions before starting, be critical, and give ideas.**
