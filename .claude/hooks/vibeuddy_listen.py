from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def project_root() -> Path:
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[2]


def _ensure_utf8_io() -> None:
    for stream in (sys.stdin, sys.stdout):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def read_hook_payload() -> dict[str, Any]:
    _ensure_utf8_io()
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        return {
            "parse_error": str(exc),
            "raw": raw,
        }
    return payload if isinstance(payload, dict) else {"payload": payload}


def compact_event(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = payload.get("prompt")
    if isinstance(prompt, str):
        prompt_preview = prompt.strip().replace("\r\n", "\n")[:240]
    else:
        prompt_preview = ""

    return {
        "received_at": datetime.now(timezone.utc).isoformat(),
        "source": "claude-code",
        "hook_event": payload.get("hook_event_name") or payload.get("event") or "UserPromptSubmit",
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd") or str(project_root()),
        "transcript_path": payload.get("transcript_path"),
        "prompt_preview": prompt_preview,
        "raw": payload,
    }


def write_event(event: dict[str, Any]) -> None:
    out_dir = project_root() / ".vibeuddy" / "claude-listener"
    out_dir.mkdir(parents=True, exist_ok=True)

    latest_path = out_dir / "latest.json"
    events_path = out_dir / "events.jsonl"
    event_path = out_dir / f"event-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    payload = json.dumps(event, ensure_ascii=False, indent=2) + "\n"

    event_path.write_text(payload, encoding="utf-8")
    latest_path.write_text(payload, encoding="utf-8")
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def main() -> int:
    try:
        payload = read_hook_payload()
        event = compact_event(payload)
        write_event(event)
        return 0
    except Exception:
        out_dir = project_root() / ".vibeuddy" / "claude-listener"
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "errors.log").open("a", encoding="utf-8") as handle:
            handle.write(datetime.now(timezone.utc).isoformat() + "\n")
            handle.write(traceback.format_exc() + "\n")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
