"""Idea Companion - mic smoke test (Modal web app).

Cloud-first, phone-first: a tiny HTTPS web app that JJ opens on her iPhone (inside
Telegram as a Mini App, or in Safari). It proves the one risky assumption before we
build anything: does a live OpenAI Realtime voice session work, with a working mic,
inside Telegram's in-app browser on iOS.

Endpoints:
  GET  /         -> the Mini App page (self-diagnosing; see page.py)
  GET  /health   -> liveness + which model is configured (no secrets)
  POST /session  -> mints a short-lived OpenAI Realtime ephemeral token

The real OPENAI_API_KEY stays server-side (Modal secret) and is never sent to the
browser. The browser only ever receives a ~60s ephemeral token.

Config (env-vars-convention: nothing hardcoded that might change):
  OPENAI_API_KEY          (required)  the standard OpenAI key, server-side only
  OPENAI_REALTIME_MODEL   (optional)  default "gpt-realtime"
  OPENAI_REALTIME_VOICE   (optional)  default "marin"

Deploy:  MODAL_PROFILE=<ws> modal deploy idea_companion/smoke/app.py
"""

import os

import modal

from page import PAGE_HTML

OPENAI_CLIENT_SECRETS = "https://api.openai.com/v1/realtime/client_secrets"
DEFAULT_MODEL = "gpt-realtime"
DEFAULT_VOICE = "marin"

app = modal.App("idea-companion-smoke")

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
            "has_key": bool(os.environ.get("OPENAI_API_KEY")),
        }

    @api.post("/session")
    async def session():
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return JSONResponse({"error": "OPENAI_API_KEY not set on server"}, status_code=500)
        model = os.environ.get("OPENAI_REALTIME_MODEL", DEFAULT_MODEL)
        voice = os.environ.get("OPENAI_REALTIME_VOICE", DEFAULT_VOICE)
        payload = {
            "session": {
                "type": "realtime",
                "model": model,
                "audio": {"output": {"voice": voice}},
            }
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    OPENAI_CLIENT_SECRETS,
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                )
        except Exception as exc:  # network/timeout to OpenAI
            return JSONResponse({"error": f"upstream request failed: {exc}"}, status_code=502, headers=no_store)

        if r.status_code >= 400:
            # Surface OpenAI's error to the page so a failure is diagnosable, not silent.
            return JSONResponse({"error": r.text[:500]}, status_code=r.status_code, headers=no_store)

        data = r.json()
        # Return ONLY the ephemeral token + meta. Never the real key.
        return JSONResponse(
            {"value": data.get("value"), "expires_at": data.get("expires_at"), "model": model},
            headers=no_store,
        )

    return api
