# Idea Companion

Voice tutor plus Notion learning vault for JJ's Notion demo.

## Demo Story

Idea Companion turns a walk into a structured Notion learning system:

1. JJ opens the Telegram Mini App and asks a topic out loud.
2. The realtime tutor teaches the basics hands-free in English or Chinese.
3. JJ asks for a report, infographic, or saved insight by voice.
4. The app saves the conversation to Notion.
5. A Modal worker fills the Notion report page with a study-ready artifact: summary, walking explanation, concept cards, quiz questions, citations, and optional images.
6. Telegram pings JJ when the Notion page is ready.

For the demo, the product is not just the voice interface. The product is the loop from voice capture to Notion memory to finished learning artifact.

## Live App

- Tutor: `https://joydai2026-del--idea-companion-web.modal.run/`
- Tutor health: `https://joydai2026-del--idea-companion-web.modal.run/health`
- Smoke test: `https://joydai2026-del--idea-companion-smoke-web.modal.run/`
- Smoke health: `https://joydai2026-del--idea-companion-smoke-web.modal.run/health`

## Repo State

- Demo branch: `feat/idea-companion`
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
8. Open the finished report page and point out the summary, concept cards, quiz, sources, and image.

The key line: "Notion is where the product remembers, organizes, and turns a walk into a reusable learning asset."
