"""Idea Companion v1 - the voice tutor (Modal web app).

The product (Approach A, proven viable by the mic smoke test): a hands-free, real-time,
bilingual spoken tutor JJ opens in Telegram and talks to while walking.

Reuses the smoke test's proven plumbing. The difference is the SESSION CONFIG: a real
tutor system prompt, turn-taking (barge-in), and input transcription so the page can
show a live transcript.

Endpoints:
  GET  /         -> the tutor page (app/page.py)
  GET  /health   -> liveness + config (no secrets)
  POST /session  -> mints an OpenAI Realtime ephemeral token with the tutor session config

The real OPENAI_API_KEY stays server-side (Modal secret `idea-companion-smoke`, which
already holds it) and never reaches the browser.

Config (env-vars-convention; nothing demo-relevant hardcoded that JJ might want to tune):
  OPENAI_API_KEY          (required)  server-side only
  OPENAI_REALTIME_MODEL   (default "gpt-realtime")
  OPENAI_REALTIME_VOICE   (default "marin")
  IC_TURN_DETECTION       (default "server_vad"; or "semantic_vad")
  IC_TUTOR_PROMPT         (default below; the heart of the product, tunable without code)

Deploy:  MODAL_PROFILE=joydai2026-del modal deploy idea_companion/app/app.py
"""

import os

import modal

from page import PAGE_HTML

OPENAI_CLIENT_SECRETS = "https://api.openai.com/v1/realtime/client_secrets"
DEFAULT_MODEL = "gpt-realtime"
DEFAULT_VOICE = "marin"
DEFAULT_TURN = "server_vad"

DEFAULT_TUTOR_PROMPT = (
    "You are \"Idea Companion,\" a warm, patient personal tutor that JJ talks to out loud "
    "while walking. You teach the FUNDAMENTALS of whatever she is curious about, like a "
    "brilliant friend who explains things clearly.\n\n"
    "VOICE & PACING (this is spoken, on a walk, hands-free):\n"
    "- Keep every turn SHORT: 2 to 4 sentences, then stop and let her respond. Never "
    "lecture or monologue.\n"
    "- Start simple, use a concrete analogy, then check in (\"make sense so far?\" / "
    "\"want me to go deeper?\").\n"
    "- Sound natural and friendly, not formal. You are a companion, not a textbook.\n\n"
    "TEACHING:\n"
    "- Teach fundamentals and intuition live. If she asks for deep detail, research, or "
    "sources, tell her you'll prepare a full illustrated deep-dive in her Notion for after "
    "the walk, and keep the live chat on the core idea.\n"
    "- She is a sharp builder and entrepreneur, so don't over-simplify, but stay accessible.\n"
    "- One idea at a time. If a topic is big, break it into a few steps across turns.\n\n"
    "LANGUAGE:\n"
    "- Bilingual English + Chinese (中文). Match the language she speaks in. If she mixes, "
    "you can mix. You may sprinkle the other language for a key term.\n\n"
    "START:\n"
    "- Greet her warmly in one short English sentence, then one short Chinese sentence, and "
    "ask what she'd like to learn about on her walk today. Keep the greeting under 8 seconds."
)

app = modal.App("idea-companion")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("fastapi[standard]==0.115.12", "httpx==0.28.1")
    .add_local_python_source("page")
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("idea-companion-smoke")],
    timeout=120,
)
@modal.asgi_app()
def web():
    import httpx
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse

    api = FastAPI()
    no_store = {"Cache-Control": "no-store, max-age=0"}

    @api.get("/")
    def index():
        return HTMLResponse(PAGE_HTML, headers=no_store)

    @api.get("/health")
    def health():
        return {
            "ok": True,
            "model": os.environ.get("OPENAI_REALTIME_MODEL", DEFAULT_MODEL),
            "voice": os.environ.get("OPENAI_REALTIME_VOICE", DEFAULT_VOICE),
            "turn_detection": os.environ.get("IC_TURN_DETECTION", DEFAULT_TURN),
            "has_key": bool(os.environ.get("OPENAI_API_KEY")),
        }

    @api.post("/session")
    async def session():
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return JSONResponse({"error": "OPENAI_API_KEY not set on server"}, status_code=500)
        model = os.environ.get("OPENAI_REALTIME_MODEL", DEFAULT_MODEL)
        voice = os.environ.get("OPENAI_REALTIME_VOICE", DEFAULT_VOICE)
        turn = os.environ.get("IC_TURN_DETECTION", DEFAULT_TURN)
        prompt = os.environ.get("IC_TUTOR_PROMPT", DEFAULT_TUTOR_PROMPT)
        payload = {
            "session": {
                "type": "realtime",
                "model": model,
                "instructions": prompt,
                "audio": {
                    "input": {
                        "turn_detection": {"type": turn},
                        "transcription": {"model": "gpt-4o-mini-transcribe"},
                    },
                    "output": {"voice": voice},
                },
            }
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    OPENAI_CLIENT_SECRETS,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
        except Exception as exc:
            return JSONResponse({"error": f"upstream request failed: {exc}"}, status_code=502, headers=no_store)

        if r.status_code >= 400:
            return JSONResponse({"error": r.text[:500]}, status_code=r.status_code, headers=no_store)

        data = r.json()
        return JSONResponse(
            {"value": data.get("value"), "expires_at": data.get("expires_at"), "model": model},
            headers=no_store,
        )

    return api
