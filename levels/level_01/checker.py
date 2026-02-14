def check_answer(answer: str):
    expected = "好了，你可以进入下一关了。"
    ok = answer.strip() == expected
    return {
        "ok": ok,
        "message": "✅ Level 01 passed." if ok else "❌ 答案不正确，请检查 welcome 第一行。",
    }
