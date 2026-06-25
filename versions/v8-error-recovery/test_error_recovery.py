from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from agent import RETRY_LIMIT_MSG, run_agent


WORKSPACE_ROOT = Path(__file__).resolve().parent


def test_same_action_fails_three_times_triggers_skip() -> None:
    """同一操作连续失败 3 次后，注入跳过提示，agent 继续运行。"""
    decisions = iter(
        [
            {"action": "read_file", "path": "nonexistent.txt"},
            {"action": "read_file", "path": "nonexistent.txt"},
            {"action": "read_file", "path": "nonexistent.txt"},
            {"action": "finish", "summary": "gave up after retries"},
        ]
    )

    with patch("agent.call_model", side_effect=lambda **_: next(decisions)):
        summary, history = run_agent(
            "test retry limit",
            max_steps=5,
            api_key="x",
            base_url="x",
            model="x",
        )

    retry_entry = [e for e in history if e.get("result", {}).get("error", "").startswith("This action has failed")]
    assert len(retry_entry) == 1
    assert "3 consecutive times" in retry_entry[0]["result"]["error"]


def test_success_resets_failure_counter() -> None:
    """失败后成功，计数器重置。"""
    probe = WORKSPACE_ROOT / "counter_probe.tmp"
    decisions = iter(
        [
            {"action": "read_file", "path": "nonexistent.txt"},   # fail 1
            {"action": "write_file", "path": "counter_probe.tmp", "content": "ok"},  # success → reset
            {"action": "run_command", "command": "echo ok"},      # success → clear needs_verification
            {"action": "read_file", "path": "nonexistent.txt"},   # fail 1 again (counter reset)
            {"action": "finish", "summary": "done"},
        ]
    )

    try:
        with patch("agent.call_model", side_effect=lambda **_: next(decisions)):
            summary, history = run_agent(
                "test counter reset",
                max_steps=5,
                api_key="x",
                base_url="x",
                model="x",
            )
    finally:
        probe.unlink(missing_ok=True)

    retry_entries = [e for e in history if "consecutive times" in e.get("result", {}).get("error", "")]
    assert len(retry_entries) == 0


def test_different_paths_count_independently() -> None:
    """不同 path 的同一 action 独立计数。"""
    decisions = iter(
        [
            {"action": "read_file", "path": "a.txt"},   # fail 1 for a.txt
            {"action": "read_file", "path": "b.txt"},   # fail 1 for b.txt
            {"action": "read_file", "path": "a.txt"},   # fail 2 for a.txt
            {"action": "read_file", "path": "b.txt"},   # fail 2 for b.txt
            {"action": "read_file", "path": "a.txt"},   # fail 3 for a.txt → skip
            {"action": "finish", "summary": "done"},
        ]
    )

    with patch("agent.call_model", side_effect=lambda **_: next(decisions)):
        summary, history = run_agent(
            "test independent counting",
            max_steps=7,
            api_key="x",
            base_url="x",
            model="x",
        )

    retry_entries = [e for e in history if "consecutive times" in e.get("result", {}).get("error", "")]
    assert len(retry_entries) == 1
    assert "a.txt" in retry_entries[0]["result"]["error"]
