def normalize(answer: str) -> str:
    digits = [ch for ch in answer if ch.isdigit()]
    return "".join(sorted(set(digits)))


def check_answer(answer: str):
    ok = normalize(answer) == "01356"
    return {
        "ok": ok,
        "message": "✅ Level 03 passed." if ok else "❌ 选项不正确，请继续实验与推断。",
    }
