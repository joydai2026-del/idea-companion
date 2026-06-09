# Idea Companion Notion Worker

This Worker moves the report builder into Notion's hosted runtime while keeping the live voice Mini App on Modal.

## What It Does

`buildLessonArtifact` is a Notion Worker webhook. Modal sends it a Report request after creating the Report row. The Worker:

1. Verifies `X-IC-Worker-Secret`.
2. Sets the Report row to `In progress`.
3. Generates a teaching workspace with OpenAI.
4. Optionally generates and uploads an image.
5. Appends the finished lesson blocks to the Report page.
6. Sets the Report row to `Ready`.
7. Pings JJ in Telegram with the Notion link.

## Why Modal Still Exists

Notion Workers are excellent for tools, syncs, and webhooks. They are not the right place to host the realtime Telegram Mini App because that path needs a public `GET /` page and WebRTC audio. Modal stays as the live capture layer. Notion Worker becomes the Notion-native lesson builder.

## Deploy

Install or use the Notion CLI:

```bash
curl -fsSL https://ntn.dev | bash
ntn login
cd notion_worker
ntn workers deploy
ntn workers webhooks list
```

Set Worker secrets:

```bash
ntn workers env set OPENAI_API_KEY=...
ntn workers env set NOTION_API_TOKEN=...
ntn workers env set TELEGRAM_BOT_TOKEN=...
ntn workers env set IC_OWNER_CHAT_ID=...
ntn workers env set IC_NOTION_WORKER_SECRET=...
```

Then put the webhook URL and the same secret into the existing Modal Notion secret:

```bash
MODAL_PROFILE=joydai2026-del modal secret create idea-companion-notion \
  NOTION_API_TOKEN="$NOTION_API_TOKEN" \
  IC_CONVERSATIONS_DB="$IC_CONVERSATIONS_DB" \
  IC_REPORTS_DB="$IC_REPORTS_DB" \
  IC_NOTION_WORKER_WEBHOOK_URL="https://www.notion.so/webhooks/worker/..." \
  IC_NOTION_WORKER_SECRET="..." \
  --force
```

The Modal app is already coded to use the Worker first when those env vars exist. If the Worker dispatch fails, Modal falls back to the existing report builder.
