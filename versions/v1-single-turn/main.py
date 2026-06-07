from __future__ import annotations

import argparse
import os
from dotenv import load_dotenv

from agent import run_agent

load_dotenv()

MAX_STEPS = 16
DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "deepseek-v4-pro")
DEFAULT_BASE_URL = os.getenv(
    "ANTHROPIC_BASE_URL",
    "https://api.deepseek.com/anthropic/v1/messages",
)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。这个函数只负责收集运行配置，不包含任何 agent 逻辑。"""
    parser = argparse.ArgumentParser(
        description="Minimal coding agent using an Anthropic-compatible API.",
    )
    parser.add_argument("task", help="What the agent should do.")
    return parser.parse_args()


def require_api_key() -> str:
    """读取 API key。

    这里故意做成单独函数，便于你理解：配置校验应该在真正发请求前尽早失败。
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        return api_key
    raise SystemExit("Set ANTHROPIC_API_KEY before running the agent.")


def main() -> None:
    args = parse_args()
    api_key = require_api_key()
    run_agent(
        args.task,
        max_steps=MAX_STEPS,
        api_key=api_key,
        base_url=DEFAULT_BASE_URL,
        model=DEFAULT_MODEL,
    )


if __name__ == "__main__":
    main()
