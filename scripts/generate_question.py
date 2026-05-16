from __future__ import annotations

import json
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
QL_DIR = BASE_DIR / ".vibeuddy" / "question-loop"
HISTORY_PATH = QL_DIR / "history.jsonl"


def read_file(path: Path, max_chars: int = 5000) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except Exception:
        return ""


def collect_context() -> dict[str, str]:
    readme = read_file(BASE_DIR / "README.md", 3000)
    design = read_file(BASE_DIR / "docs" / "project-core-design.md", 5000)

    prompt_path = QL_DIR / "latest_prompt.json"
    latest_prompt = ""
    if prompt_path.exists():
        try:
            signal = json.loads(prompt_path.read_text(encoding="utf-8"))
            latest_prompt = signal.get("prompt", "")
        except Exception:
            pass

    recent_qa = ""
    if HISTORY_PATH.exists():
        try:
            lines = HISTORY_PATH.read_text(encoding="utf-8").strip().split("\n")
            recent_qa = "\n".join(lines[-3:])
        except Exception:
            pass

    return {
        "readme": readme,
        "design": design,
        "latest_prompt": latest_prompt,
        "recent_qa": recent_qa,
    }


def build_user_prompt(ctx: dict[str, str]) -> str:
    return f"""项目上下文：
<PROJECT_CONTEXT>
README:
{ctx["readme"] or "(暂无 README)"}

核心设计文档:
{ctx["design"] or "(暂无设计文档)"}
</PROJECT_CONTEXT>

用户刚刚在 Claude Code 中提交的输入：
<LATEST_PROMPT>
{ctx["latest_prompt"] or "(暂无输入)"}
</LATEST_PROMPT>

最近问答记录：
<RECENT_QA_HISTORY>
{ctx["recent_qa"] or "(暂无历史记录)"}
</RECENT_QA_HISTORY>

请生成一个项目理解问题。
返回格式必须严格符合：
{{
  "project_summary": "...",
  "thinking_focus": "...",
  "question": {{
    "type": "multiple_choice",
    "text": "...",
    "choices": [
      {{"id": "A", "text": "..."}},
      {{"id": "B", "text": "..."}},
      {{"id": "C", "text": "..."}}
    ],
    "correct_choice": "A|B|C",
    "explanation": "..."
  }},
  "pet_prompt": "...",
  "difficulty": "easy|medium"
}}"""


SYSTEM_PROMPT = """你是 Vibeuddy，一只会陪用户 Vibe Coding 的项目思考教练。

你的任务不是审查代码，而是在用户提交一次 Vibe Coding 输入后，帮助用户重新理解自己的项目。

你需要基于项目上下文：
1. 总结当前项目正在做什么。
2. 找出一个最值得用户思考的问题。
3. 生成一道选择题，帮助用户判断自己是否真的理解项目。

问题应该聚焦项目定位、功能取舍、MVP 范围、用户价值或技术风险。
不要考察琐碎代码细节。
不要替用户做决定，要通过问题把决策权还给用户。

必须只返回 JSON，不要输出 Markdown，不要输出额外解释。"""


def call_model(prompt: str) -> dict[str, Any]:
    api_key = os.environ.get("SILICONFLOW_API_KEY", "")
    if not api_key:
        raise SystemExit(
            "Missing SILICONFLOW_API_KEY. "
            "Please set it before running Vibeuddy question loop."
        )

    import urllib.request

    body = json.dumps(
        {
            "model": "deepseek-ai/DeepSeek-V4-Flash",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1024,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://api.siliconflow.cn/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"API call failed: {exc}") from exc

    content = raw["choices"][0]["message"]["content"]
    return extract_json(content)


def extract_json(text: str) -> dict[str, Any]:
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in markdown code fences
    m = re.search(r"```(?:json)?\s*\n?([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find JSON object boundaries
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Failed to extract JSON from model response:\n{text}")


FALLBACK_QUESTION = {
    "project_summary": "项目目前处于 Vibe Coding 迭代中。",
    "thinking_focus": "用户应该先保证核心闭环能跑通。",
    "question": {
        "type": "multiple_choice",
        "text": "如果明天就要演示，这个项目最需要先保证什么？",
        "choices": [
            {"id": "A", "text": "核心闭环能跑通"},
            {"id": "B", "text": "功能越多越好"},
            {"id": "C", "text": "先做复杂视觉特效"},
        ],
        "correct_choice": "A",
        "explanation": "黑客松演示优先保证核心闭环。",
    },
    "pet_prompt": "如果明天就要演示，先跑通核心闭环！",
    "difficulty": "easy",
}


def write_question(data: dict[str, Any]) -> None:
    QL_DIR.mkdir(parents=True, exist_ok=True)
    question_path = QL_DIR / "current_question.json"
    question_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def log_error(message: str) -> None:
    QL_DIR.mkdir(parents=True, exist_ok=True)
    with (QL_DIR / "errors.log").open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()}\n{message}\n\n")


def main() -> int:
    try:
        ctx = collect_context()
        prompt = build_user_prompt(ctx)
        data = call_model(prompt)
        write_question(data)
        QL_DIR.mkdir(parents=True, exist_ok=True)
        (QL_DIR / "last_generated_at.txt").write_text(
            datetime.now(timezone.utc).isoformat(),
        )
        return 0
    except SystemExit:
        raise
    except Exception:
        log_error(traceback.format_exc())
        write_question(FALLBACK_QUESTION)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
