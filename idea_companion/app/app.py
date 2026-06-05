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

from page import PAGE_HTML, VERSION

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
    "- Open warmly and briefly. Tell her you can speak as many languages as she likes, then "
    "ask which she'd prefer for today: English or 中文 (Zhongwen)? Keep it under 8 seconds and "
    "inviting. Once she picks, continue in that language (still switch whenever she does), and "
    "ask what she'd like to learn about on her walk."
)

# Voice-issued commands become tool calls, so they are captured reliably mid-walk
# (hands-free) instead of parsed out of the transcript afterward.
TOOLS = [
    {
        "type": "function",
        "name": "request_report",
        "description": (
            "Call this when JJ asks for a written report, a deep dive, or to 'go deep' / "
            "'do a detailed report' on a topic to read later. It saves the request to her "
            "Notion for after the walk. After calling it, briefly confirm out loud."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "What to research and write up."},
                "depth": {"type": "string", "enum": ["quick", "deep"], "description": "quick summary or deep dive"},
            },
            "required": ["topic"],
        },
    },
    {
        "type": "function",
        "name": "make_infographic",
        "description": (
            "Call this when JJ asks for an infographic, diagram, chart, or picture explaining "
            "a topic to save for later. It saves the request to her Notion. Then briefly confirm."
        ),
        "parameters": {
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
    },
    {
        "type": "function",
        "name": "save_insight",
        "description": (
            "Call this when JJ says something is important, an action item, or 'remember this' / "
            "'save this'. It saves the note to her Notion. Then briefly confirm."
        ),
        "parameters": {
            "type": "object",
            "properties": {"note": {"type": "string"}},
            "required": ["note"],
        },
    },
]

def _para(text):
    """A Notion paragraph block (capped under the 2000-char rich-text limit)."""
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": (text or "")[:1900]}}]}}


def _has_cjk(text):
    return any("一" <= ch <= "鿿" for ch in (text or ""))


app = modal.App("idea-companion")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("fastapi[standard]==0.115.12", "httpx==0.28.1")
    .add_local_python_source("page")
)


@app.function(
    image=image,
    secrets=[
        modal.Secret.from_name("idea-companion-smoke"),
        modal.Secret.from_name("idea-companion-notion"),
    ],
    timeout=120,
)
@modal.asgi_app()
def web():
    import httpx
    from fastapi import FastAPI, Request
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
            "version": VERSION,
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
                "tools": TOOLS,
                "tool_choice": "auto",
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

    @api.post("/save")
    async def save(request: Request):
        """Persist a finished walk: one Conversations row (transcript in the page body)
        + one Reports row per voice-issued request (Status=Requested, which the worker
        turns into a finished report)."""
        from datetime import datetime, timezone

        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "bad json"}, status_code=400, headers=no_store)
        transcript = body.get("transcript") or []
        reqs = body.get("requests") or []
        started_at = body.get("started_at")
        print(f"[save] turns={len(transcript)} requests={len(reqs)}")

        token = os.environ.get("NOTION_API_TOKEN")
        conv_db = os.environ.get("IC_CONVERSATIONS_DB")
        rep_db = os.environ.get("IC_REPORTS_DB")
        if not (token and conv_db):
            return JSONResponse(
                {"ok": True, "notion": "pending (token/db not set yet)", "turns": len(transcript), "requests": len(reqs)},
                headers=no_store,
            )

        nver = os.environ.get("NOTION_VERSION", "2022-06-28")
        nheaders = {"Authorization": f"Bearer {token}", "Notion-Version": nver, "Content-Type": "application/json"}
        try:
            dt = datetime.fromtimestamp(started_at / 1000, tz=timezone.utc) if started_at else datetime.now(timezone.utc)
        except Exception:
            dt = datetime.now(timezone.utc)
        date_str = dt.strftime("%Y-%m-%d")
        title = "Walk · " + dt.strftime("%Y-%m-%d %H:%M UTC")
        first_user = next((t.get("text", "") for t in transcript if t.get("role") == "you"), "")
        summary = first_user[:180] or f"{len(transcript)} turns"
        lang = "中文" if any(_has_cjk(t.get("text", "")) for t in transcript) else "EN"
        blocks = [_para(("You: " if t.get("role") == "you" else "Tutor: ") + t.get("text", "")) for t in transcript[:90]]

        conv_props = {
            "Title": {"title": [{"text": {"content": title}}]},
            "Date": {"date": {"start": date_str}},
            "Summary": {"rich_text": [{"text": {"content": summary}}]},
            "Requests": {"number": len(reqs)},
            "Language": {"select": {"name": lang}},
        }
        conv_url, report_urls, errors = None, [], []
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.notion.com/v1/pages",
                headers=nheaders,
                json={"parent": {"database_id": conv_db}, "properties": conv_props, "children": blocks},
            )
            if r.status_code >= 400:
                errors.append("conversation: " + r.text[:300])
            else:
                conv_url = r.json().get("url")
            if rep_db:
                for rq in reqs:
                    typ = rq.get("type", "report")
                    topic = (rq.get("topic") or rq.get("note") or "(untitled)")[:200]
                    props = {
                        "Topic": {"title": [{"text": {"content": topic}}]},
                        "Type": {"select": {"name": typ if typ in ("report", "infographic", "insight") else "report"}},
                        "Status": {"select": {"name": "Requested"}},
                        "Created": {"date": {"start": date_str}},
                    }
                    if rq.get("depth") in ("quick", "deep"):
                        props["Depth"] = {"select": {"name": rq["depth"]}}
                    rr = await client.post(
                        "https://api.notion.com/v1/pages",
                        headers=nheaders,
                        json={"parent": {"database_id": rep_db}, "properties": props},
                    )
                    if rr.status_code >= 400:
                        errors.append(f"report '{topic[:30]}': " + rr.text[:200])
                    else:
                        report_urls.append(rr.json().get("url"))

        return JSONResponse(
            {
                "ok": not errors,
                "notion": "written" if not errors else "partial/failed",
                "conversation_url": conv_url,
                "reports": report_urls,
                "errors": errors,
            },
            headers=no_store,
        )

    return api
