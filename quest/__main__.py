from __future__ import annotations

import argparse
import sys

from .engine import (
    QuestError,
    advance_level,
    load_level,
    load_state,
    read_task,
    save_state,
    start_quest,
    submit_answer,
)


def cmd_start(_: argparse.Namespace) -> int:
    state = start_quest()
    print("🎮 Quest initialized.")
    print(f"Current level: {state['current_level']}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    state = load_state()
    print(f"Current level: {state['current_level']}")
    print(f"Completed: {', '.join(state['completed']) if state['completed'] else '(none)'}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    state = load_state()
    level_id = args.level or state["current_level"]
    level = load_level(level_id)
    print(f"\n== {level.level_id}: {level.title} ==\n")
    print(read_task(level))
    print(f"\nAnswer format: {level.answer_format}")
    return 0


def cmd_hint(args: argparse.Namespace) -> int:
    state = load_state()
    level_id = args.level or state["current_level"]
    level = load_level(level_id)

    used = state["hints_used"].get(level_id, 0)
    if used >= len(level.hints):
        print("No more hints for this level.")
        return 0

    print(f"Hint {used + 1}: {level.hints[used]}")
    state["hints_used"][level_id] = used + 1
    save_state(state)
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    state = load_state()
    level_id = args.level or state["current_level"]
    if level_id != state["current_level"]:
        print("You can only submit for current level.")
        return 2

    level = load_level(level_id)
    attempts = state["attempts"].get(level_id, 0) + 1
    state["attempts"][level_id] = attempts

    ok, msg = submit_answer(level, args.answer)
    print(msg)

    if not ok:
        save_state(state)
        return 1

    if level_id not in state["completed"]:
        state["completed"].append(level_id)

    nxt = advance_level(level_id)
    if nxt is None:
        print("🏁 You completed all levels!")
    else:
        state["current_level"] = nxt
        print(level.pass_message)
        print(f"➡️ Next level unlocked: {nxt}")

    save_state(state)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m quest", description="Fudan CS Quest CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_start = sub.add_parser("start", help="Initialize or reset quest progress")
    p_start.set_defaults(func=cmd_start)

    p_status = sub.add_parser("status", help="Show quest progress")
    p_status.set_defaults(func=cmd_status)

    p_run = sub.add_parser("run", help="Show current level task")
    p_run.add_argument("level", nargs="?", help="Optional level id")
    p_run.set_defaults(func=cmd_run)

    p_hint = sub.add_parser("hint", help="Show next hint")
    p_hint.add_argument("level", nargs="?", help="Optional level id")
    p_hint.set_defaults(func=cmd_hint)

    p_submit = sub.add_parser("submit", help="Submit level answer")
    p_submit.add_argument("--answer", required=True, help="Answer string")
    p_submit.add_argument("--level", help="Optional level id")
    p_submit.set_defaults(func=cmd_submit)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except QuestError as e:
        print(f"Quest error: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
