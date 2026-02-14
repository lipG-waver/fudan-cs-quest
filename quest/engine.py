from __future__ import annotations

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LEVELS_DIR = ROOT / "levels"
STATE_DIR = ROOT / ".quest"
STATE_FILE = STATE_DIR / "state.json"


@dataclass
class Level:
    level_id: str
    title: str
    task_file: str
    checker_file: str
    answer_format: str
    hints: list[str]
    pass_message: str


class QuestError(Exception):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise QuestError(f"Missing file: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry() -> list[str]:
    data = _load_json(LEVELS_DIR / "registry.json")
    return data["levels"]


def load_level(level_id: str) -> Level:
    data = _load_json(LEVELS_DIR / level_id / "manifest.json")
    return Level(
        level_id=data["level_id"],
        title=data["title"],
        task_file=data["task_file"],
        checker_file=data["checker_file"],
        answer_format=data["answer_format"],
        hints=data["hints"],
        pass_message=data["pass_message"],
    )


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {
            "current_level": "level_01",
            "completed": [],
            "attempts": {},
            "hints_used": {},
        }
    return _load_json(STATE_FILE)


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def start_quest() -> dict[str, Any]:
    state = {
        "current_level": "level_01",
        "completed": [],
        "attempts": {},
        "hints_used": {},
    }
    save_state(state)
    return state


def _load_checker(level_id: str, checker_file: str):
    checker_path = LEVELS_DIR / level_id / checker_file
    spec = importlib.util.spec_from_file_location(f"checker_{level_id}", checker_path)
    if spec is None or spec.loader is None:
        raise QuestError(f"Unable to load checker for {level_id}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def submit_answer(level: Level, answer: str) -> tuple[bool, str]:
    module = _load_checker(level.level_id, level.checker_file)
    result = module.check_answer(answer)
    return bool(result.get("ok", False)), str(result.get("message", ""))


def advance_level(current_level: str) -> str | None:
    levels = load_registry()
    idx = levels.index(current_level)
    if idx + 1 >= len(levels):
        return None
    return levels[idx + 1]


def read_task(level: Level) -> str:
    task_path = LEVELS_DIR / level.level_id / level.task_file
    if not task_path.exists():
        raise QuestError(f"Task file missing for {level.level_id}")
    return task_path.read_text(encoding="utf-8")
