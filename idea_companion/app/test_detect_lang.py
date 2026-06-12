"""Deterministic test for _detect_lang (conversation language tagging).

app.py imports `modal`, which isn't installed locally, so we extract just the
_detect_lang function from the source via AST and exercise it in isolation.
Run: python3 idea_companion/app/test_detect_lang.py
"""
import ast
import os
import sys

APP = os.path.join(os.path.dirname(__file__), "app.py")


def load_fn(name):
    src = open(APP, encoding="utf-8").read()
    tree = ast.parse(src)
    defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    assert defs, f"{name} not found in app.py"
    ns = {}
    exec(compile(ast.Module(body=defs, type_ignores=[]), APP, "exec"), ns)
    return ns[name]


detect = load_fn("_detect_lang")


def t(role, text):
    return {"role": role, "text": text}


CASES = [
    # The actual bug: all-English walk, but the tutor's greeting contains 中文.
    ("english walk, tutor greeting has 中文", [
        t("tutor", "Hi! I can speak many languages. English or 中文 (Zhongwen)?"),
        t("you", "English is great. Let's talk about vector databases."),
        t("tutor", "Great choice. A vector database stores embeddings."),
    ], "EN"),
    # A genuine Chinese walk.
    ("chinese walk", [
        t("tutor", "你好！我们今天聊什么？"),
        t("you", "我想了解一下向量数据库的原理。"),
        t("tutor", "好的，向量数据库把文本变成向量。"),
    ], "中文"),
    # English user who drops a single Chinese term -> still English.
    ("english user, one stray chinese term", [
        t("you", "I was reading about the 道 concept but mostly in English here."),
    ], "EN"),
    # No captured user turns -> fall back to all turns.
    ("fallback: only tutor, chinese", [t("tutor", "你好，今天想聊些什么有趣的想法？")], "中文"),
    ("fallback: only tutor, english", [t("tutor", "Hello, what would you like to explore today?")], "EN"),
    # Degenerate input.
    ("empty transcript", [], "EN"),
]


def main():
    fails = 0
    for name, tr, exp in CASES:
        got = detect(tr)
        ok = got == exp
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}: {name} -> {got!r} (expected {exp!r})")
    print()
    if fails:
        print(f"{fails} test(s) FAILED")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    main()
