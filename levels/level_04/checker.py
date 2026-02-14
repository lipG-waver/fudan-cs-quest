def check_answer(answer: str):
    text = answer.strip()
    ok = text.lower().startswith("reflect:") and len(text) >= 24
    return {
        "ok": ok,
        "message": "✅ Level 04 passed." if ok else "❌ 请按 REFLECT: 开头提交不少于 24 字符的反思。",
    }
