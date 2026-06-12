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
    "- Treat this like a stateful teaching workspace, not a one-off answer. Tie what you teach "
    "to JJ's real goal, detect what she already understands, and challenge her just enough.\n"
    "- She is a sharp builder and entrepreneur, so don't over-simplify, but stay accessible.\n"
    "- One idea at a time. If a topic is big, break it into a few steps across turns.\n\n"
    "LANGUAGE:\n"
    "- Bilingual English + Chinese (中文). Match the language she speaks in. If she mixes, "
    "you can mix. You may sprinkle the other language for a key term.\n\n"
    "TOOLS (actually call them, do not just say you will):\n"
    "- A report / deep dive / 'save this to Notion' / 'go deep on X' -> call request_report "
    "(set visuals=true if she wants pictures, diagrams, or to be shown it).\n"
    "- A standalone infographic, diagram, or picture -> call make_infographic.\n"
    "- 'Remember this' / 'save this insight' -> call save_insight.\n"
    "Call the tool, then confirm in one short sentence. Never refuse a save; you can always "
    "prepare it for her Notion.\n\n"
    "CONTINUITY & TEACH-BACK:\n"
    "- You may be given a MEMORY list of recent walks. Use it: acknowledge what she has been "
    "exploring and offer to continue an open thread or start fresh.\n"
    "- If she says 'quiz me', 'test me', or 'let me explain', switch to teach-back: pick a concept "
    "from a recent walk, ask her to explain it in her own words, then give warm, specific feedback "
    "on what she nailed and what to sharpen. Keep it conversational.\n\n"
    "NOTION TEACHING WORKSPACE:\n"
    "- When you prepare a report, make it useful for future lessons: mission tie-in, trusted "
    "resources, concept cards, glossary candidates, a learning record, and a quick practice loop.\n"
    "- A learning record should capture what JJ now understands or what misconception changed. "
    "Do not treat mere exposure as learning.\n\n"
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
            "Notion for after the walk. If she also wants pictures, diagrams, or to be shown "
            "it visually, set visuals=true. Call this AT MOST ONCE per report JJ asks for; do "
            "not split one request into several calls. After calling it, briefly confirm out loud."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "What to research and write up."},
                "depth": {"type": "string", "enum": ["quick", "deep"], "description": "quick summary or deep dive"},
                "visuals": {"type": "boolean", "description": "true if JJ wants pictures, diagrams, or illustrations included."},
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


def _detect_lang(transcript):
    """Conversation language from what the USER actually said.

    The tutor mirrors her but may sprinkle the other language (its scripted
    greeting even asks "English or 中文?"), so scanning every turn for any CJK
    character wrongly tags an all-English walk as Chinese. Decide by the
    majority script of the "you" turns; fall back to all turns only if she has
    no captured turns."""
    you = " ".join(t.get("text", "") for t in transcript if t.get("role") == "you")
    text = you if you.strip() else " ".join(t.get("text", "") for t in transcript)
    cjk = sum(1 for ch in text if "一" <= ch <= "鿿")
    latin = sum(1 for ch in text if ch.isascii() and ch.isalpha())
    return "中文" if cjk > latin else "EN"


def _md_to_blocks(md):
    """Minimal Markdown -> Notion blocks (headings, bullets, numbered, paragraphs).
    Parses [label](url) into clickable Notion links so report Sources are tappable."""
    import re

    def rt(text):
        text = (text or "").replace("**", "")
        parts, pos = [], 0
        for m in re.finditer(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", text):
            if m.start() > pos:
                parts.append({"type": "text", "text": {"content": text[pos:m.start()][:1900]}})
            parts.append({"type": "text", "text": {"content": m.group(1)[:1900], "link": {"url": m.group(2)}}})
            pos = m.end()
        if pos < len(text):
            parts.append({"type": "text", "text": {"content": text[pos:][:1900]}})
        return parts or [{"type": "text", "text": {"content": ""}}]

    blocks = []
    for raw in (md or "").split("\n"):
        s = raw.strip()
        if not s:
            continue
        if s.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": rt(s[4:])}})
        elif s.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": rt(s[3:])}})
        elif s.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": rt(s[2:])}})
        elif s[:2] in ("- ", "* "):
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt(s[2:])}})
        elif len(s) > 2 and s[0].isdigit() and s[1] in ".)":
            blocks.append({"object": "block", "type": "numbered_list_item", "numbered_list_item": {"rich_text": rt(s[2:].lstrip(" .)"))}})
        else:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": rt(s)}})
    return blocks[:180]


def _no_em_dash(s):
    """Deterministically enforce JJ's no-em-dash rule on generated output (the model
    ignores the instruction sometimes). Em dash -> comma; en dash -> hyphen."""
    s = s or ""
    for dash in ("—", "―"):  # em dash, horizontal bar
        s = s.replace(" " + dash + " ", ", ").replace(dash, ", ")
    s = s.replace("–", "-")  # en dash -> hyphen
    while "  " in s:
        s = s.replace("  ", " ")
    return s.replace(" ,", ",")


def _generate_report(topic, depth, context_text):
    """Write the report body with web-grounded search (gpt-4o-search-preview) so recent facts,
    models, benchmarks, rankings, and numbers are CURRENT and cited, not hallucinated."""
    import httpx

    key = os.environ["OPENAI_API_KEY"]
    model = os.environ.get("IC_REPORT_MODEL", "gpt-4o-search-preview")
    span = "a thorough but accessible learning artifact" if depth == "deep" else "a concise learning artifact"
    system = (
        "You are a sharp tutor writing a follow-up learning report for a smart builder and "
        "entrepreneur after a walking conversation. Search the web for CURRENT, accurate "
        "information, especially recent models, benchmarks, rankings, news, dates, and numbers; "
        "never invent figures or rely on stale memory. The output is going into Notion, so make it "
        "feel like a finished study page, not a chat transcript. Write clear Markdown with this exact "
        "structure: '# <topic>'; a one-line plain-English promise; '## Mission Tie-In' explaining why "
        "this matters to JJ's real work or learning; '## 5-Bullet Summary' with exactly five bullets; "
        "'## Explain It Like I Am Walking' with short spoken-style paragraphs; '## Why This Matters' "
        "with practical implications; '## Concept Cards' with 3 to 5 bullets in the format "
        "'Concept: explanation'; '## Glossary Candidates' with 3 tight definitions that should only be "
        "promoted after JJ can use them; '## Practice Loop' with one tiny exercise and the feedback "
        "criteria; '## Learning Record' with 1 to 3 sentences capturing what this lesson establishes "
        "for future sessions; '## Quiz Me Later' with exactly 3 questions and brief answers; "
        "'## Trusted Resources' listing the best sources to revisit; and '## Next Action' with one "
        "concrete thing JJ can do next. Use bullet lists, not Markdown tables, because tables do not "
        "render well here. Be concrete, use an analogy when it helps, no fluff, no emojis, and never "
        "use em dashes."
    )
    user = f"Topic to write up: {topic}\nLength: {span}.\n"
    if context_text:
        user += f"\nContext from our walk (for relevance, do not quote verbatim):\n{context_text[:1500]}\n"
    user += "\nWrite the report now in Markdown."
    payload = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if "search" not in model:
        payload["temperature"] = 0.6  # search-preview models reject temperature
    r = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=180,
    )
    r.raise_for_status()
    msg = r.json()["choices"][0]["message"]
    text = _no_em_dash(msg.get("content") or "")
    cites, seen = [], set()
    for a in (msg.get("annotations") or []):
        uc = a.get("url_citation") or {}
        url = uc.get("url")
        if url and url not in seen:
            seen.add(url)
            cites.append((uc.get("title") or url, url))
    if cites:
        text += "\n\n## Sources\n" + "\n".join(f"- [{t}]({u})" for t, u in cites[:8])
    return text


def _telegram_ping(text):
    import httpx

    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("IC_OWNER_CHAT_ID")
    if not (tok and chat):
        return
    try:
        httpx.post(f"https://api.telegram.org/bot{tok}/sendMessage", json={"chat_id": chat, "text": text}, timeout=20)
    except Exception as exc:
        print("[worker] telegram err:", exc)


def _generate_image(prompt, size="1024x1024"):
    """Generate a PNG with gpt-image-1; returns raw bytes (or None on failure)."""
    import base64

    import httpx

    key = os.environ["OPENAI_API_KEY"]
    model = os.environ.get("IC_IMAGE_MODEL", "gpt-image-1")
    try:
        r = httpx.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "prompt": prompt[:900], "size": size},
            timeout=180,
        )
        r.raise_for_status()
        return base64.b64decode(r.json()["data"][0]["b64_json"])
    except Exception as exc:
        print("[worker] image gen err:", exc)
        return None


def _notion_upload_image(img_bytes, filename="illustration.png"):
    """Upload PNG bytes to Notion (create -> send). Returns a file_upload id (or None)."""
    import httpx

    token = os.environ["NOTION_API_TOKEN"]
    fv = os.environ.get("NOTION_FILE_VERSION", "2026-03-11")
    try:
        c = httpx.post(
            "https://api.notion.com/v1/file_uploads",
            headers={"Authorization": f"Bearer {token}", "Notion-Version": fv, "Content-Type": "application/json"},
            json={"filename": filename, "content_type": "image/png"},
            timeout=30,
        )
        c.raise_for_status()
        fid = c.json()["id"]
        s = httpx.post(
            f"https://api.notion.com/v1/file_uploads/{fid}/send",
            headers={"Authorization": f"Bearer {token}", "Notion-Version": fv},
            files={"file": (filename, img_bytes, "image/png")},
            timeout=120,
        )
        s.raise_for_status()
        return fid
    except Exception as exc:
        print("[worker] notion upload err:", exc)
        return None


def _dispatch_notion_worker(payload):
    """Ask the Notion Worker to build the report. Returns True when accepted.
    Modal remains the fallback until the Worker path is proven live."""
    import httpx

    url = os.environ.get("IC_NOTION_WORKER_WEBHOOK_URL")
    secret = os.environ.get("IC_NOTION_WORKER_SECRET")
    if not (url and secret):
        return False
    try:
        r = httpx.post(
            url,
            headers={"X-IC-Worker-Secret": secret, "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        if 200 <= r.status_code < 300:
            print("[save] notion worker accepted report")
            return True
        print(f"[save] notion worker rejected report {r.status_code}: {r.text[:240]}")
    except Exception as exc:
        print("[save] notion worker dispatch failed:", exc)
    return False


def _image_block(file_upload_id):
    return {"object": "block", "type": "image", "image": {"type": "file_upload", "file_upload": {"id": file_upload_id}}}


def _divider_block():
    return {"object": "block", "type": "divider", "divider": {}}


def _callout_block(text):
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": text[:1900]}}],
            "icon": {"type": "emoji", "emoji": "🧠"},
        },
    }


def _learning_artifact_header(topic):
    return [
        _callout_block(
            "Created from a walking conversation. Notion is now the study surface: skim the summary, "
            "review the concept cards, then use the quiz questions for active recall."
        ),
        _para(f"Topic: {topic}"),
        _divider_block(),
    ]


def _summarize_conversation(transcript_text):
    """One-sentence summary of a walk (topics learned + a hint of what's next), for memory."""
    import httpx

    key = os.environ.get("OPENAI_API_KEY")
    if not key or not transcript_text.strip():
        return ""
    model = os.environ.get("IC_SUMMARY_MODEL", "gpt-4o-mini")
    try:
        r = httpx.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "In ONE sentence, summarize what JJ ASKED about or wanted to learn in this walk (focus on her own questions and requests, name the specific topic; do not just repeat what the tutor lectured on). No emojis, no em dashes."},
                    {"role": "user", "content": transcript_text[:4000]},
                ],
                "temperature": 0.3,
                "max_tokens": 80,
            },
            timeout=30,
        )
        r.raise_for_status()
        return _no_em_dash(r.json()["choices"][0]["message"]["content"].strip())
    except Exception as exc:
        print("[save] summary err:", exc)
        return ""


def _trivial_summary(s):
    s = (s or "").strip().lower().rstrip(".!?")
    return len(s) < 12 or s in {"hello", "hi", "hey", "mhm", "mm", "yes", "no", "okay", "ok", "hey hello", "hello hello"}


def _recent_memory(conv_limit=8, topic_limit=14):
    """The tutor's cross-walk memory: the concrete topics JJ has explored (from her Reports,
    the ground truth) plus recent meaningful walk summaries. Reports are the reliable signal
    of 'what did we cover' (conversation summaries can be sparse or circular)."""
    import httpx

    token = os.environ.get("NOTION_API_TOKEN")
    if not token:
        return ""
    nver = os.environ.get("NOTION_VERSION", "2022-06-28")
    hdr = {"Authorization": f"Bearer {token}", "Notion-Version": nver, "Content-Type": "application/json"}
    parts = []

    rep_db = os.environ.get("IC_REPORTS_DB")
    if rep_db:
        try:
            r = httpx.post(
                f"https://api.notion.com/v1/databases/{rep_db}/query",
                headers=hdr,
                json={"page_size": 40, "sorts": [{"timestamp": "created_time", "direction": "descending"}]},
                timeout=15,
            )
            r.raise_for_status()
            topics, seen = [], set()
            for row in r.json().get("results", []):
                t = ((row.get("properties", {}).get("Topic", {}).get("title") or [{}])[0] or {}).get("plain_text", "").strip()
                k = t.lower()
                if t and k not in seen:
                    seen.add(k)
                    topics.append(t)
            if topics:
                parts.append(
                    "Topics JJ has ALREADY explored with you (you DO remember these), most recent first: "
                    + "; ".join(topics[:topic_limit]) + "."
                )
        except Exception as exc:
            print("[memory] reports err:", exc)

    conv_db = os.environ.get("IC_CONVERSATIONS_DB")
    if conv_db:
        try:
            r = httpx.post(
                f"https://api.notion.com/v1/databases/{conv_db}/query",
                headers=hdr,
                json={"page_size": 15, "sorts": [{"timestamp": "created_time", "direction": "descending"}]},
                timeout=15,
            )
            r.raise_for_status()
            lines = []
            for row in r.json().get("results", []):
                props = row.get("properties", {})
                title = ((props.get("Title", {}).get("title") or [{}])[0] or {}).get("plain_text", "")
                summ = ((props.get("Summary", {}).get("rich_text") or [{}])[0] or {}).get("plain_text", "")
                if summ and not _trivial_summary(summ):
                    lines.append(f"- {title.replace('Walk · ', '')}: {summ}")
                if len(lines) >= conv_limit:
                    break
            if lines:
                parts.append("Recent walks:\n" + "\n".join(lines))
        except Exception as exc:
            print("[memory] convs err:", exc)

    return "\n\n".join(parts)


def _validate_init_data(init_data, bot_token):
    """Validate a Telegram Mini App initData string. Returns the user dict if the signature
    is valid (proves it came from this bot), else None. Standard algorithm:
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app"""
    import hashlib
    import hmac
    import json
    from urllib.parse import parse_qsl

    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        received = pairs.pop("hash", None)
        if not received:
            return None
        check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, received):
            return None
        import time

        max_age = int(os.environ.get("IC_AUTH_MAX_AGE", "86400"))
        if max_age and (time.time() - int(pairs.get("auth_date", "0"))) > max_age:
            return None  # replay protection: initData too old
        user = json.loads(pairs.get("user", "{}"))
        if not user.get("id"):
            return None  # signature valid but no user identity
        return user
    except Exception:
        return None


def _authorized(request):
    """(ok, reason). Validates Telegram identity and, if IC_OWNER_USER_ID is set, restricts
    to the owner. Enforced only when IC_REQUIRE_AUTH is truthy (so it can roll out safely)."""
    import os as _os

    user = _validate_init_data(request.headers.get("x-telegram-init-data", ""), _os.environ.get("TELEGRAM_BOT_TOKEN"))
    if user is None:
        return False, "invalid or missing Telegram initData"
    owner = _os.environ.get("IC_OWNER_USER_ID")
    if not owner:
        return False, "owner not configured"  # fail closed: never allow when owner unset
    if str(user.get("id")) != str(owner):
        return False, "not the owner"
    return True, "ok"


def _auth_gate(request, where, JSONResponse, no_store):
    """Returns a 401 response if auth is required and the request is not authorized; else None."""
    require = os.environ.get("IC_REQUIRE_AUTH", "0").lower() not in ("", "0", "false", "no")
    ok, reason = _authorized(request)
    print(f"[auth] {where}: {reason} (enforced={require})")
    if require and not ok:
        return JSONResponse({"error": "unauthorized"}, status_code=401, headers=no_store)
    return None


app = modal.App("idea-companion")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("fastapi[standard]==0.115.12", "httpx==0.28.1")
    .add_local_python_source("page")
)


SECRETS = [
    modal.Secret.from_name("idea-companion-smoke"),
    modal.Secret.from_name("idea-companion-notion"),
    modal.Secret.from_name("idea-companion-telegram"),
    modal.Secret.from_name("idea-companion-worker"),
]


@app.function(image=image, secrets=SECRETS, timeout=120, min_containers=1)
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
        require_auth = os.environ.get("IC_REQUIRE_AUTH", "0").lower() not in ("", "0", "false", "no")
        return {
            "ok": True,
            "version": VERSION,
            "model": os.environ.get("OPENAI_REALTIME_MODEL", DEFAULT_MODEL),
            "voice": os.environ.get("OPENAI_REALTIME_VOICE", DEFAULT_VOICE),
            "turn_detection": os.environ.get("IC_TURN_DETECTION", DEFAULT_TURN),
            "has_key": bool(os.environ.get("OPENAI_API_KEY")),
            "has_notion_token": bool(os.environ.get("NOTION_API_TOKEN")),
            "has_conversations_db": bool(os.environ.get("IC_CONVERSATIONS_DB")),
            "has_reports_db": bool(os.environ.get("IC_REPORTS_DB")),
            "has_owner_user": bool(os.environ.get("IC_OWNER_USER_ID")),
            "has_notion_worker": bool(os.environ.get("IC_NOTION_WORKER_WEBHOOK_URL")),
            "auth_enforced": require_auth,
            "artifact_template": "teaching-workspace-v3",
        }

    @api.post("/session")
    async def session(request: Request):
        denied = _auth_gate(request, "session", JSONResponse, no_store)
        if denied is not None:
            return denied
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return JSONResponse({"error": "OPENAI_API_KEY not set on server"}, status_code=500)
        model = os.environ.get("OPENAI_REALTIME_MODEL", DEFAULT_MODEL)
        voice = os.environ.get("OPENAI_REALTIME_VOICE", DEFAULT_VOICE)
        turn = os.environ.get("IC_TURN_DETECTION", DEFAULT_TURN)
        prompt = os.environ.get("IC_TUTOR_PROMPT", DEFAULT_TUTOR_PROMPT)
        memory = _recent_memory()
        if memory:
            prompt += (
                "\n\nMEMORY (what you have already covered with JJ):\n" + memory +
                "\n\nYou DO remember these. If she asks whether you covered a topic before, check this "
                "list and answer truthfully; do NOT say no if it is listed here. In your greeting, "
                "briefly acknowledge what she has been exploring and offer to continue or start new."
            )
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
            print(f"[session] openai error {r.status_code}: {r.text[:300]}")
            return JSONResponse({"error": "tutor temporarily unavailable, please retry"}, status_code=502, headers=no_store)

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

        denied = _auth_gate(request, "save", JSONResponse, no_store)
        if denied is not None:
            return denied
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "bad json"}, status_code=400, headers=no_store)
        transcript = (body.get("transcript") or [])[:200]
        reqs = (body.get("requests") or [])[:10]  # bound fan-out: cap report requests per walk
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
        transcript_text = "\n".join(("You: " if t.get("role") == "you" else "Tutor: ") + t.get("text", "") for t in transcript)
        summary = (
            _summarize_conversation(transcript_text)
            or next((t.get("text", "") for t in transcript if t.get("role") == "you"), "")[:180]
            or f"{len(transcript)} turns"
        )
        lang = _detect_lang(transcript)
        blocks = [_para(("You: " if t.get("role") == "you" else "Tutor: ") + t.get("text", "")) for t in transcript[:90]]

        conv_props = {
            "Title": {"title": [{"text": {"content": title}}]},
            "Date": {"date": {"start": date_str}},
            "Summary": {"rich_text": [{"text": {"content": summary}}]},
            "Requests": {"number": len(reqs)},
            "Language": {"select": {"name": lang}},
        }
        conv_url, conv_id, report_urls, errors = None, None, [], []
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.notion.com/v1/pages",
                headers=nheaders,
                json={"parent": {"database_id": conv_db}, "properties": conv_props, "children": blocks},
            )
            if r.status_code >= 400:
                errors.append("conversation: " + r.text[:300])
            else:
                cj = r.json()
                conv_url = cj.get("url")
                conv_id = cj.get("id")  # link each report back to this walk
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
                    if conv_id:
                        props["Conversation"] = {"relation": [{"id": conv_id}]}
                    rr = await client.post(
                        "https://api.notion.com/v1/pages",
                        headers=nheaders,
                        json={"parent": {"database_id": rep_db}, "properties": props},
                    )
                    if rr.status_code >= 400:
                        errors.append(f"report '{topic[:30]}': " + rr.text[:200])
                    else:
                        rj = rr.json()
                        rid = rj.get("id")
                        report_urls.append(rj.get("url"))
                        if not rid:
                            errors.append(f"report '{topic[:30]}': created but no id returned")
                        else:
                            ctx = "\n".join(
                                ("You: " if t.get("role") == "you" else "Tutor: ") + t.get("text", "") for t in transcript
                            )[:1800]
                            try:
                                worker_payload = {
                                    "report_id": rid,
                                    "report_url": rj.get("url"),
                                    "topic": topic,
                                    "depth": rq.get("depth") or "deep",
                                    "type": props["Type"]["select"]["name"],
                                    "context_text": ctx,
                                    "visuals": bool(rq.get("visuals")),
                                    # Forward the owner chat id so the Worker can ping the link even if
                                    # its own env is not configured. This is the bug that dropped the link.
                                    "owner_chat_id": os.environ.get("IC_OWNER_CHAT_ID"),
                                }
                                if not _dispatch_notion_worker(worker_payload):
                                    process_report.spawn(
                                        report_id=rid,
                                        report_url=rj.get("url"),
                                        topic=topic,
                                        depth=rq.get("depth") or "deep",
                                        typ=props["Type"]["select"]["name"],
                                        context_text=ctx,
                                        visuals=bool(rq.get("visuals")),
                                    )
                            except Exception as exc:
                                print("[save] spawn failed:", exc)

        # Immediate reassurance ping so JJ knows the report is on its way (she is not looking
        # at the screen on a walk). The worker pings again with the link when it is ready.
        pending = [
            (rq.get("topic") or rq.get("note") or "your topic")
            for rq in reqs
            if rq.get("type", "report") in ("report", "infographic")
        ]
        if pending:
            if len(pending) == 1:
                _telegram_ping(f"📝 Got it. I'm preparing your report on “{pending[0]}” now. It'll be in your Notion in about a minute. Sit tight, I'll ping you the moment it's ready.")
            else:
                _telegram_ping("📝 Got it. I'm preparing " + str(len(pending)) + " reports now (" + "; ".join(pending[:5]) + "). They'll be in your Notion shortly. I'll ping you as each one is ready.")

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


@app.function(image=image, secrets=SECRETS, timeout=600)
def process_report(report_id, report_url, topic, depth, typ, context_text, visuals=False):
    """Background worker: research the request, write the finished report into the Notion
    page body, flip Status to Ready, and ping JJ on Telegram. Spawned by /save the moment a
    walk ends, so the report is ready by the time she sits down. This is the reliable Modal
    floor; the native Notion agent is validated in parallel."""
    import httpx

    token = os.environ["NOTION_API_TOKEN"]
    nver = os.environ.get("NOTION_VERSION", "2022-06-28")
    nh = {"Authorization": f"Bearer {token}", "Notion-Version": nver, "Content-Type": "application/json"}

    def set_status(s):
        try:
            httpx.patch(
                f"https://api.notion.com/v1/pages/{report_id}",
                headers=nh,
                json={"properties": {"Status": {"select": {"name": s}}}},
                timeout=30,
            )
        except Exception as exc:
            print("[worker] status err:", exc)

    fv = os.environ.get("NOTION_FILE_VERSION", "2026-03-11")
    fheaders = {"Authorization": f"Bearer {token}", "Notion-Version": fv, "Content-Type": "application/json"}

    def append(blocks):
        ok = True
        for i in range(0, len(blocks), 90):
            ar = httpx.patch(
                f"https://api.notion.com/v1/blocks/{report_id}/children",
                headers=fheaders,
                json={"children": blocks[i:i + 90]},
                timeout=60,
            )
            if ar.status_code >= 400:
                ok = False
                print("[worker] append err:", ar.text[:200])
        return ok

    print(f"[worker] {typ} '{topic}' depth={depth} visuals={visuals}")
    set_status("In progress")
    try:
        if typ == "insight":
            blocks = _learning_artifact_header("Saved insight") + [_para(topic)]
        elif typ == "infographic":
            img = _generate_image(
                f"A clean, friendly flat-illustration infographic explaining '{topic}' for a curious "
                "learner. Simple labeled diagram, soft colors, minimal text, educational, no watermark."
            )
            fid = _notion_upload_image(img, "infographic.png") if img else None
            md = _generate_report(topic, "quick", context_text)
            head = [_image_block(fid)] if fid else [_para("(Could not generate the image this time; here is the explanation.)")]
            blocks = _learning_artifact_header(topic) + head + _md_to_blocks(md)
        else:
            md = _generate_report(topic, depth, context_text)
            blocks = _learning_artifact_header(topic) + _md_to_blocks(md)
            if visuals:
                img = _generate_image(
                    f"A clean, friendly flat-illustration diagram that visually explains '{topic}' for a "
                    "curious learner. Labeled, soft colors, minimal text, educational, no watermark."
                )
                fid = _notion_upload_image(img, "illustration.png") if img else None
                if fid:
                    blocks = blocks[:3] + [_image_block(fid)] + blocks[3:]
        appended_ok = append(blocks)
        if appended_ok:
            set_status("Ready")
            label = "deep dive" if depth == "deep" else "summary"
            _telegram_ping(f"\U0001f4d3 Ready: your {label} on “{topic}” is in your Notion.\n{report_url}")
        else:
            # The write was incomplete; do NOT claim Ready (a green status must mean the body is there).
            set_status("Requested")
            _telegram_ping(f"⚠️ I saved partial notes on “{topic}” but the Notion write was incomplete. Ask me to redo it.")
    except Exception as exc:
        print("[worker] error:", exc)
        set_status("Requested")
        _telegram_ping(f"⚠️ I couldn't finish “{topic}” this time. Ask me again and I'll retry it.")
