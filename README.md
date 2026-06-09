# Idea Companion

Voice tutor plus Notion learning vault for JJ's Notion demo.

## Demo Story

Idea Companion turns a walk into a structured Notion learning system:

1. JJ opens the Telegram Mini App and asks a topic out loud.
2. The realtime tutor teaches the basics hands-free in English or Chinese.
3. JJ asks for a report, infographic, or saved insight by voice.
4. The app saves the conversation to Notion.
5. A Modal worker fills the Notion report page with a teaching workspace: mission tie-in, summary, walking explanation, concept cards, glossary candidates, practice loop, learning record, quiz questions, citations, and optional images.
6. Telegram pings JJ when the Notion page is ready.

For the demo, the product is not just the voice interface. The product is the loop from voice capture to Notion memory to finished learning artifact.

## Live App

- Tutor: `https://joydai2026-del--idea-companion-web.modal.run/`
- Tutor health: `https://joydai2026-del--idea-companion-web.modal.run/health`
- Smoke test: `https://joydai2026-del--idea-companion-smoke-web.modal.run/`
- Smoke health: `https://joydai2026-del--idea-companion-smoke-web.modal.run/health`

## Notion Worker Split

Modal still owns the realtime Mini App because Telegram needs a public HTML page and WebRTC audio. Notion Worker owns the lesson-building step.

Current flow on `feat/notion-worker-reports`:

1. Modal creates the Conversation row.
2. Modal creates the Report row.
3. If `IC_NOTION_WORKER_WEBHOOK_URL` is configured, Modal dispatches the report payload to Notion Worker.
4. Notion Worker builds the teaching workspace and flips the Report to `Ready`.
5. If Worker dispatch fails, Modal falls back to the existing report builder.

Worker code lives in `notion_worker/`.

## Repo State

- Demo branch: `feat/idea-companion`
- Worker migration branch: `feat/notion-worker-reports`
- Roadmap branch: `feat/phase-1-weekly-review`
- Default branch: `feat/idea-companion`

`feat/idea-companion` is the branch to use for the Notion demo. `feat/phase-1-weekly-review` contains the earlier weekly-review core and tests, but it is roadmap scope for this demo.

## Run Checks

```bash
python3 -m py_compile idea_companion/app/app.py idea_companion/app/page.py idea_companion/smoke/app.py idea_companion/smoke/page.py idea_companion/smoke/set_telegram_menu.py
curl -sS https://joydai2026-del--idea-companion-web.modal.run/health
curl -sS https://joydai2026-del--idea-companion-smoke-web.modal.run/health
```

## Deploy

```bash
MODAL_PROFILE=joydai2026-del modal deploy idea_companion/app/app.py
MODAL_PROFILE=joydai2026-del modal deploy idea_companion/smoke/app.py
```

Required Modal secrets:

- `idea-companion-smoke`: OpenAI realtime config.
- `idea-companion-notion`: Notion token plus Conversations and Reports database IDs.
- `idea-companion-telegram`: Telegram bot token, owner user ID, owner chat ID, and auth setting.

## Demo Script

Use the live Notion page as the center of the demo:

1. Open the Notion dashboard first and say: "This is the learning vault."
2. Open Telegram and start Idea Companion.
3. Ask: "Explain why Notion is useful as a personal product backend."
4. Ask: "Save a deep report with pictures to my Notion."
5. End the walk.
6. Show the Conversation row created in Notion.
7. Show the Report row moving from Requested to Ready.
8. Open the finished report page and point out the mission tie-in, concept cards, glossary candidates, practice loop, learning record, quiz, sources, and image.

The key line: "Notion is where the product turns a walk into a teaching workspace that can compound over time."
