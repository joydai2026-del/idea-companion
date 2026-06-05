# Idea Companion - mic smoke test

The one test that decides the whole product: **does a live OpenAI Realtime voice
session work, with a real mic, inside Telegram's in-app browser on iOS?**

If yes -> build the Telegram Mini App voice tutor (Approach A, the wow).
If no  -> fall back to voice notes (B) or a Safari home-screen PWA (C).

The same page also runs in plain Safari, so one deploy tests A (Telegram) and
C (PWA) at once.

## What it does
A tiny HTTPS web app:
- `GET /` serves a self-diagnosing page (`page.py`). On Start it asks for the mic,
  mints a token, opens a 30s WebRTC voice session, and asks the bot to greet you
  bilingually. It shows ten live checks + a mic level meter so a single screenshot
  tells us exactly what worked.
- `POST /session` mints a ~60s OpenAI Realtime ephemeral token. The real
  `OPENAI_API_KEY` stays server-side and never reaches the browser.
- `GET /health` reports config (no secrets).

## Config (Modal secret `idea-companion-smoke`)
Nothing hardcoded that might change:
- `OPENAI_API_KEY`        (required) server-side only
- `OPENAI_REALTIME_MODEL` (default `gpt-realtime`)
- `OPENAI_REALTIME_VOICE` (default `marin`)

## Deploy
```bash
# 1) one-time: create the Modal secret from .env values
set -a && source .env && set +a
MODAL_PROFILE=joydai2026-del modal secret create idea-companion-smoke \
  OPENAI_API_KEY="$OPENAI_API_KEY" \
  OPENAI_REALTIME_MODEL=gpt-realtime \
  OPENAI_REALTIME_VOICE=marin

# 2) deploy -> prints the https://<app>.modal.run URL
MODAL_PROFILE=joydai2026-del modal deploy idea_companion/smoke/app.py

# 3) wire the Telegram bot menu button to that URL
python idea_companion/smoke/set_telegram_menu.py https://<app>.modal.run
```

## Run the test (on the iPhone)
1. Open **@idea_companion_bot** in Telegram, tap the **Voice test** menu button
   (next to the message box). The Mini App opens inside Telegram.
2. Tap **Start 30s voice test**, allow the mic when asked, then **say hello**.
3. Watch the checks. Tap **Copy diagnostics** (or screenshot) and send it back.
4. To compare, open the same URL in **Safari** and run it again.

## Reading the result
- **GO** (green): "Mic permission" granted AND "Bot audio in" received. Telegram
  voice tutor is viable -> build Approach A.
- **NO-GO** (red): "Mic permission" failed (e.g. `NotAllowedError`). The mic is
  blocked in Telegram's WebView -> if Safari works, ship Approach C (PWA); if Safari
  also fails, ship Approach B (voice notes).
