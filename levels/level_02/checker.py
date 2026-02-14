def check_answer(answer: str):
    ok = answer.strip() == "iamthebest"
    return {
        "ok": ok,
        "message": "✅ Level 02 passed." if ok else "❌ 密码不正确，请从 git 历史中找。",
    }
