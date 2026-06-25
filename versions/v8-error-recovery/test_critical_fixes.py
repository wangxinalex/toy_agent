from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from agent import VERIFY_REQUIRED_MSG, run_agent
from tools import validate_command


WORKSPACE_ROOT = Path(__file__).resolve().parent


def test_write_after_successful_command_requires_new_verification() -> None:
    probe = WORKSPACE_ROOT / "review_probe.tmp"
    decisions = iter(
        [
            {"action": "run_command", "command": "python -m compileall agent.py"},
            {"action": "write_file", "path": "review_probe.tmp", "content": "not verified"},
            {"action": "finish", "summary": "finished after stale verification"},
        ]
    )

    try:
        with patch("agent.call_model", side_effect=lambda **_: next(decisions)):
            summary, history = run_agent(
                "prove stale verification",
                max_steps=3,
                api_key="x",
                base_url="x",
                model="x",
            )
    finally:
        probe.unlink(missing_ok=True)

    assert summary == "Agent stopped: reached max steps."
    assert history[-1]["result"] == {"ok": False, "error": VERIFY_REQUIRED_MSG}


def test_command_validation_rejects_shell_chaining() -> None:
    assert validate_command("git status; python -c 'print(1)'") is not None
