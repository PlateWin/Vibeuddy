from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
QL_DIR = BASE_DIR / ".vibeuddy" / "question-loop"
QUESTION_PATH = QL_DIR / "current_question.json"
RESULT_PATH = QL_DIR / "latest_result.json"
HISTORY_PATH = QL_DIR / "history.jsonl"


def read_question() -> dict:
    if not QUESTION_PATH.exists():
        print("No current question found. Run generate_question.py first.")
        raise SystemExit(1)
    return json.loads(QUESTION_PATH.read_text(encoding="utf-8"))


def judge(question: dict, user_answer: str) -> dict:
    q = question.get("question", {})
    correct = q.get("correct_choice", "").strip().upper()
    user = user_answer.strip().upper()

    if user == correct:
        result = "correct"
        bubble_text = f"答对啦！{q.get('explanation', '你抓住了项目核心。')}"
    else:
        result = "wrong"
        bubble_text = f"再想想。正确答案是 {correct}。{q.get('explanation', '')}"

    return {
        "result": result,
        "pet_action": result,
        "bubble_text": bubble_text,
    }


def write_result(result: dict) -> None:
    QL_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def append_history(question: dict, user_answer: str, result: dict) -> None:
    QL_DIR.mkdir(parents=True, exist_ok=True)
    q = question.get("question", {})
    choices = [f"{c['id']}. {c['text']}" for c in q.get("choices", [])]
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_summary": question.get("project_summary", ""),
        "question": q.get("text", ""),
        "choices": choices,
        "correct_choice": q.get("correct_choice", ""),
        "user_answer": user_answer.strip().upper(),
        "result": result["result"],
    }
    with HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/answer_question.py <A|B|C>")
        print("Example: python scripts/answer_question.py B")
        return 1

    user_answer = sys.argv[1]
    if user_answer.upper() not in ("A", "B", "C"):
        print(f"Invalid answer '{user_answer}'. Expected A, B, or C.")
        return 1

    question = read_question()
    result = judge(question, user_answer)
    write_result(result)
    append_history(question, user_answer, result)

    q = question.get("question", {})
    print(f"Q: {q.get('text', '?')}")
    print(f"Your answer: {user_answer.upper()}")
    print(f"Correct answer: {q.get('correct_choice', '?')}")
    print(f"Result: {result['result'].upper()}")
    print(f"Pet says: {result['bubble_text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
