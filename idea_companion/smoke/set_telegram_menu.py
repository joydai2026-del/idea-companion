"""Wire the Telegram bot so JJ can open the smoke-test Mini App from her phone.

Primary path: set the bot's chat Menu Button (the button next to the message box)
to launch the Mini App. This is global, needs no chat_id, and always works once
JJ opens the bot chat.

Best-effort extra: if JJ has already messaged the bot, also DM her a tappable
"Open voice test" button plus the raw URL (handy for opening in Safari too).

Nothing hardcoded: token from .env / env, URL from argv or IC_WEBAPP_URL.

Usage:
  python idea_companion/smoke/set_telegram_menu.py https://<app>.modal.run
"""

import json
import os
import sys
import urllib.request
from pathlib import Path


def load_env() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


def api(token: str, method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def main() -> int:
    load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set (.env)")
        return 1

    url = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("IC_WEBAPP_URL")
    if not url or not url.startswith("https://"):
        print("ERROR: pass the HTTPS Mini App URL as the first argument")
        return 1

    # 1) Global menu button -> launches the Mini App
    res = api(
        token,
        "setChatMenuButton",
        {"menu_button": {"type": "web_app", "text": "Voice test", "web_app": {"url": url}}},
    )
    print("setChatMenuButton:", res.get("ok"), res.get("description", ""))

    # 2) Best-effort: DM JJ a tappable button if she's messaged the bot
    try:
        updates = api(token, "getUpdates", {"timeout": 0})
        chat_ids = set()
        for u in updates.get("result", []):
            msg = u.get("message") or u.get("edited_message") or {}
            chat = msg.get("chat") or {}
            if chat.get("type") == "private" and chat.get("id"):
                chat_ids.add(chat["id"])
        for cid in chat_ids:
            api(
                token,
                "sendMessage",
                {
                    "chat_id": cid,
                    "text": (
                        "Idea Companion mic test is ready.\n\n"
                        "Tap the button below (opens inside Telegram), or open this link "
                        f"in Safari to compare:\n{url}\n\n"
                        "Then: tap Start, allow the mic, say hello, and listen for a reply."
                    ),
                    "reply_markup": {
                        "inline_keyboard": [[{"text": "Open voice test", "web_app": {"url": url}}]]
                    },
                },
            )
            print(f"DM sent to chat {cid}")
        if not chat_ids:
            print("No private chats found yet. Open @idea_companion_bot and tap the Voice test menu button.")
    except Exception as exc:
        print(f"(DM step skipped: {exc})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
