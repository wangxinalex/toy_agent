from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from agent import run_agent

load_dotenv()

MAX_STEPS = 16
DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "deepseek-v4-pro")
DEFAULT_BASE_URL = os.getenv(
    "ANTHROPIC_BASE_URL",
    "https://api.deepseek.com/anthropic/v1/messages",
)

# session 文件统一放在这个目录下，不和源码混在一起。
SESSIONS_DIR = Path(__file__).resolve().parent / "sessions"


def generate_session_id() -> str:
    """按当前 UTC 时间生成 session ID。"""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def save_session(session_id: str, history: list[dict[str, Any]]) -> Path:
    """把 history 写入 sessions/<id>.json。

    每次 run_agent 结束就保存一次，避免崩溃丢失。
    """
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / f"{session_id}.json"
    payload = {
        "session_id": session_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "history": history,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def load_session(session_id: str) -> list[dict[str, Any]]:
    """从 sessions/<id>.json 读取 history。"""
    path = SESSIONS_DIR / f"{session_id}.json"
    if not path.exists():
        candidates = sorted(SESSIONS_DIR.glob("*.json"))
        raise SystemExit(
            f"Session '{session_id}' not found.\n"
            f"Available: {', '.join(p.stem for p in candidates) or '(none)'}"
        )
    payload = json.loads(path.read_text())
    return payload["history"]


def list_sessions() -> list[Path]:
    """按修改时间倒序列出所有 session 文件。"""
    if not SESSIONS_DIR.exists():
        return []
    return sorted(
        SESSIONS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minimal coding agent using an Anthropic-compatible API.",
    )
    parser.add_argument("task", nargs="?", help="Optional first task to run.")
    parser.add_argument("--resume", metavar="ID", help="Resume a saved session.")
    parser.add_argument("--list-sessions", action="store_true", help="List saved sessions.")
    parser.add_argument("--session", metavar="NAME", help="Custom session name.")
    return parser.parse_args()


def require_api_key() -> str:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        return api_key
    raise SystemExit("Set ANTHROPIC_API_KEY before running the agent.")


def main() -> None:
    args = parse_args()
    api_key = require_api_key()

    # --list-sessions：打印会话列表后退出
    if args.list_sessions:
        sessions = list_sessions()
        if not sessions:
            print("No saved sessions.")
        else:
            for p in sessions:
                payload = json.loads(p.read_text())
                task_count = sum(1 for e in payload["history"] if "task" in e)
                print(f"  {p.stem}  ({task_count} tasks)")
        return

    # 确定 session_id 和初始 history
    if args.resume:
        history = load_session(args.resume)
        session_id = args.resume
        print(f"Resumed session: {session_id}")
    else:
        history = None  # 新会话
        session_id = args.session or generate_session_id()
        print(f"New session: {session_id}")

    pending_task = args.task

    while True:
        if pending_task is None:
            user_input = input("\nYou> ").strip()
            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit", "q"}:
                print("Bye.")
                break
            pending_task = user_input

        summary, history = run_agent(
            pending_task,
            max_steps=MAX_STEPS,
            api_key=api_key,
            base_url=DEFAULT_BASE_URL,
            model=DEFAULT_MODEL,
            history=history,
        )
        path = save_session(session_id, history)
        print(f"[Session saved: {path.relative_to(Path.cwd())}]")
        pending_task = None


if __name__ == "__main__":
    main()
