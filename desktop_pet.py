from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
RAW_FRAME_DIR = BASE_DIR / "assets" / "pet_frames"
FRAME_DIR = BASE_DIR / "assets" / "pet_frames_aligned"
LEGACY_ACTION_DIR = BASE_DIR / "assets" / "pet_actions"
ANSWER_ACTION_DIR = BASE_DIR / "assets" / "pet_answer_actions_v3"
SPRITE_SOURCE = BASE_DIR / "cropped_522x649 (2).png"
CROP_SCRIPT = BASE_DIR / "scripts" / "crop_sprite_to_transparent.py"
ALIGN_SCRIPT = BASE_DIR / "scripts" / "align_pet_frames.py"
ANSWER_ACTION_SCRIPT = BASE_DIR / "scripts" / "build_answer_pet_actions.py"
CLAUDE_EVENTS_DIR = BASE_DIR / ".vibeuddy" / "claude-listener"
QUESTION_LOOP_DIR = BASE_DIR / ".vibeuddy" / "question-loop"
POLL_INTERVAL_MS = 800
GENERATE_SCRIPT = BASE_DIR / "scripts" / "generate_question.py"


class DesktopPet:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Vibeuddy Desktop Pet")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "#010101")
        self.root.configure(bg="#010101")

        self.scale = 0.33
        self.float_step = 0
        self.drag_x = 0
        self.drag_y = 0
        self.base_x = 0
        self.base_y = 0
        self.action = "stand"
        self.frame_index = 0
        self.closed = False
        self.bubble_visible = True
        self.bubble_after_id: str | None = None
        self._last_prompt_mtime = ""
        self._last_result_mtime = ""
        self._generating = False
        self._tw_after_id: str | None = None
        self._tw_text = ""
        self._tw_index = 0
        self._tw_callback: object = None
        self.bubble_width = 400
        self.bubble_height = 150
        self.choice_bubble_width = 420
        self.choice_bubble_height = 220
        self._choice_ids: list[str] = []
        self._question_choices: list[dict] = []
        self._answer_script = BASE_DIR / "scripts" / "answer_question.py"
        self._question_active = False
        self._question_pending = False
        self._showing_result = False
        self._result_after_id: str | None = None

        self.actions = self.load_actions()

        self.label = tk.Label(self.root, bg="#010101", bd=0, highlightthickness=0)
        self.label.pack()
        self.label.bind("<ButtonPress-1>", self.start_drag)
        self.label.bind("<B1-Motion>", self.drag)
        self.label.bind("<Button-3>", self.show_menu)
        self.label.bind("<Double-Button-1>", lambda _event: self.play_once("correct"))
        self.label.bind("<Button-2>", lambda _event: self.play_once("wrong"))

        self.bubble = self.create_bubble()
        self.choice_bubble = self.create_choice_bubble()
        self.choice_bubble.withdraw()

        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="站立", command=lambda: self.set_action("stand"))
        self.menu.add_command(label="答对", command=lambda: self.play_once("correct"))
        self.menu.add_command(label="答错", command=lambda: self.play_once("wrong"))
        self.menu.add_separator()
        self.menu.add_command(label="显示/隐藏气泡", command=self.toggle_bubble)
        self.menu.add_command(label="退出", command=self.close)

        self.place_initially()
        self.say(self._startup_message())
        self.animate()

    def _startup_message(self) -> str:
        config_path = BASE_DIR / ".vibeuddy" / "config.json"
        key_ok = False
        if config_path.exists():
            try:
                config = json.loads(config_path.read_text(encoding="utf-8"))
                if config.get("siliconflow_api_key"):
                    key_ok = True
            except Exception:
                pass
        if os.environ.get("SILICONFLOW_API_KEY"):
            key_ok = True
        return "我准备好啦，API已配置" if key_ok else "我准备好啦，但API未配置"

    def create_bubble(self) -> tk.Toplevel:
        bubble = tk.Toplevel(self.root)
        bubble.overrideredirect(True)
        bubble.attributes("-topmost", True)
        bubble.attributes("-transparentcolor", "#010101")
        bubble.configure(bg="#010101")

        self.bubble_canvas = tk.Canvas(
            bubble,
            width=self.bubble_width,
            height=self.bubble_height,
            bg="#010101",
            bd=0,
            highlightthickness=0,
        )
        self.bubble_canvas.pack(fill="both", expand=True)
        self._draw_bubble_background()
        tw = int(self.bubble_width * 0.84)
        self.bubble_text_id = self.bubble_canvas.create_text(
            self.bubble_width // 2,
            int(self.bubble_height * 0.42),
            text="",
            width=tw,
            fill="#1b2240",
            font=("Microsoft YaHei UI", 10, "bold"),
            justify="center",
        )
        return bubble

    def create_choice_bubble(self) -> tk.Toplevel:
        bubble = tk.Toplevel(self.root)
        bubble.overrideredirect(True)
        bubble.attributes("-topmost", True)
        bubble.attributes("-transparentcolor", "#010101")
        bubble.configure(bg="#010101")

        self.choice_canvas = tk.Canvas(
            bubble,
            width=self.choice_bubble_width,
            height=self.choice_bubble_height,
            bg="#010101",
            bd=0,
            highlightthickness=0,
        )
        self.choice_canvas.pack(fill="both", expand=True)
        self._draw_choice_bubble_background()
        return bubble

    def _draw_bubble_background(self) -> None:
        canvas = self.bubble_canvas
        canvas.delete("bubble_bg")
        W, H = self.bubble_width, self.bubble_height
        fill = "#ffffff"
        outline = "#151949"
        accent = "#35dfe7"
        shade = "#dfe8ff"

        # Pixel speech bubble: clean body, stepped corners, small tail.
        canvas.create_rectangle(24, 18, W - 16, H - 28, fill=outline, outline=outline, tags="bubble_bg")
        canvas.create_rectangle(16, 26, W - 24, H - 36, fill=outline, outline=outline, tags="bubble_bg")
        canvas.create_rectangle(28, 24, W - 28, H - 40, fill=fill, outline=fill, tags="bubble_bg")
        canvas.create_rectangle(22, 32, W - 34, H - 44, fill=fill, outline=fill, tags="bubble_bg")
        canvas.create_rectangle(34, 10, W - 44, 18, fill=outline, outline=outline, tags="bubble_bg")
        canvas.create_rectangle(38, 16, W - 48, 24, fill=fill, outline=fill, tags="bubble_bg")

        tail_x = W // 2
        for box in [
            (tail_x - 30, H - 40, tail_x + 30, H - 24, outline),
            (tail_x - 22, H - 40, tail_x + 22, H - 28, fill),
            (tail_x - 18, H - 24, tail_x + 18, H - 14, outline),
            (tail_x - 12, H - 24, tail_x + 12, H - 18, fill),
            (tail_x - 8, H - 14, tail_x + 8, H - 6, outline),
        ]:
            canvas.create_rectangle(*box[:4], fill=box[4], outline=box[4], tags="bubble_bg")

        canvas.create_rectangle(34, 44, 40, 50, fill=accent, outline=accent, tags="bubble_bg")
        canvas.create_rectangle(W - 44, 44, W - 38, 50, fill=accent, outline=accent, tags="bubble_bg")
        canvas.create_rectangle(52, 36, 58, 42, fill=shade, outline=shade, tags="bubble_bg")

        if hasattr(self, "bubble_text_id"):
            canvas.lift(self.bubble_text_id)

    def _draw_choice_bubble_background(self) -> None:
        canvas = self.choice_canvas
        canvas.delete("choice_bg")
        W, H = self.choice_bubble_width, self.choice_bubble_height
        fill = "#ffffff"
        outline = "#151949"
        accent = "#35dfe7"
        shadow = "#cbd6ff"

        canvas.create_rectangle(22, 12, W - 14, H - 12, fill=outline, outline=outline, tags="choice_bg")
        canvas.create_rectangle(14, 20, W - 22, H - 20, fill=outline, outline=outline, tags="choice_bg")
        canvas.create_rectangle(20, 26, W - 28, H - 26, fill=fill, outline=fill, tags="choice_bg")
        canvas.create_rectangle(28, 18, W - 36, 28, fill=fill, outline=fill, tags="choice_bg")
        canvas.create_rectangle(28, 26, W - 36, 50, fill=outline, outline=outline, tags="choice_bg")
        canvas.create_rectangle(34, 30, W - 42, 46, fill="#1b2240", outline="#1b2240", tags="choice_bg")
        canvas.create_text(
            W // 2, 38, text="选择一个答案", fill="#ffffff",
            font=("Microsoft YaHei UI", 9, "bold"), tags="choice_bg"
        )
        canvas.create_rectangle(36, H - 26, W - 44, H - 20, fill=shadow, outline=shadow, tags="choice_bg")
        canvas.create_rectangle(W - 42, 58, W - 36, 64, fill=accent, outline=accent, tags="choice_bg")
        canvas.create_rectangle(W - 42, 72, W - 36, 78, fill=accent, outline=accent, tags="choice_bg")

    def load_numbered_frames(self, directory: Path) -> list[tk.PhotoImage]:
        paths = sorted(directory.glob("frame_*.png"))
        return [self.load_image(path) for path in paths]

    def load_action_or_fallback(self, action: str, frame_numbers: list[int]) -> list[tk.PhotoImage]:
        for root in (ANSWER_ACTION_DIR, LEGACY_ACTION_DIR):
            action_frames = self.load_numbered_frames(root / action)
            if action_frames:
                return action_frames
        return self.load_frames(frame_numbers)

    def load_actions(self) -> dict[str, list[tk.PhotoImage]]:
        stand = self.load_action_or_fallback("stand", [1, 2, 5, 6, 5, 2])
        correct = self.load_action_or_fallback("correct", [1, 5, 2, 6, 2, 1])
        wrong = self.load_action_or_fallback("wrong", [2, 3, 4, 3, 2, 1])
        return {
            "stand": stand,
            "correct": correct,
            "wrong": wrong,
            "idle": stand,
            "happy": correct,
            "confused": wrong,
        }

    def load_frames(self, frame_numbers: list[int]) -> list[tk.PhotoImage]:
        missing = [n for n in frame_numbers if not (FRAME_DIR / f"frame_{n:02d}.png").exists()]
        if missing:
            raise FileNotFoundError(
                "Missing pet frame PNG files. Run: python scripts\\crop_sprite_to_transparent.py"
            )
        return [self.load_image(FRAME_DIR / f"frame_{number:02d}.png") for number in frame_numbers]

    def load_image(self, path: Path) -> tk.PhotoImage:
        image = tk.PhotoImage(file=str(path))
        if self.scale < 1:
            divisor = max(1, round(1 / self.scale))
            image = image.subsample(divisor, divisor)
        return image

    def place_initially(self) -> None:
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        pet_w = self.actions["stand"][0].width()
        pet_h = self.actions["stand"][0].height()
        x = screen_w - pet_w - 64
        y = screen_h - pet_h - 96
        self.base_x = x
        self.base_y = y
        self.root.geometry(f"+{x}+{y}")
        self.update_bubble_position()
        for name in ("latest_prompt.json", "latest_result.json", "current_question.json"):
            stale = QUESTION_LOOP_DIR / name
            if stale.exists():
                stale.unlink()
        self._poll_question_loop()

    def _poll_question_loop(self) -> None:
        self._check_prompt()
        self._check_result()
        if not self.closed:
            self.root.after(POLL_INTERVAL_MS, self._poll_question_loop)

    def _check_prompt(self) -> None:
        """Detect new prompts and trigger question generation."""
        if self._generating:
            return
        prompt_path = QUESTION_LOOP_DIR / "latest_prompt.json"
        if not prompt_path.exists():
            self._last_prompt_mtime = ""
            return
        try:
            mtime = prompt_path.stat().st_mtime_ns
        except OSError:
            return
        if self._last_prompt_mtime and mtime <= self._last_prompt_mtime:
            return
        self._last_prompt_mtime = mtime
        self._generating = True
        self.say("让我想想...")
        threading.Thread(target=self._generate_question, daemon=True).start()

    def _generate_question(self) -> None:
        """Run generate_question.py in background, then update UI."""
        try:
            result = subprocess.run(
                [sys.executable, str(GENERATE_SCRIPT)],
                capture_output=True,
                text=True,
                timeout=45,
                cwd=str(BASE_DIR),
                env=os.environ.copy(),
            )
        except Exception:
            self.root.after(0, lambda: self._on_question_failed("生成超时或异常"))
            return
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()[:80]
            self.root.after(0, lambda d=detail: self._on_question_failed(d))
            return
        q_path = QUESTION_LOOP_DIR / "current_question.json"
        if not q_path.exists():
            self.root.after(0, lambda: self._on_question_failed("问题文件未生成"))
            return
        self.root.after(0, lambda: self._show_question())

    def _on_question_failed(self, detail: str = "") -> None:
        self._generating = False
        msg = f"我没想好问题…({detail})" if detail else "我没想好问题，再试一次?"
        self.say(msg)

    def _show_question(self) -> None:
        q_path = QUESTION_LOOP_DIR / "current_question.json"
        if not q_path.exists():
            self._generating = False
            self.say("我没想好问题，再试一次?")
            return
        try:
            data = json.loads(q_path.read_text(encoding="utf-8"))
        except Exception:
            self.root.after(300, self._show_question)
            return
        q = data.get("question", {})
        choices = q.get("choices", [])
        if not q.get("text") or len(choices) < 2:
            self._generating = False
            self.say("问题格式有点乱，我换个问法...")
            return
        self._generating = False
        self.say(q.get("text", "?"), on_done=lambda: self._draw_choice_buttons())
        self._question_pending = True
        self._question_choices = choices[:3]

    def _check_result(self) -> None:
        """Detect new answer results and play animation."""
        if self._generating or self._question_pending or self._question_active:
            return
        result_path = QUESTION_LOOP_DIR / "latest_result.json"
        if not result_path.exists():
            return
        try:
            mtime = result_path.stat().st_mtime_ns
        except OSError:
            return
        if self._last_result_mtime and mtime <= self._last_result_mtime:
            return
        self._last_result_mtime = mtime
        try:
            data = json.loads(result_path.read_text(encoding="utf-8"))
        except Exception:
            return
        action = data.get("pet_action", "stand")
        bubble = data.get("bubble_text", "")
        self._showing_result = True
        self.play_once(action)
        if bubble:
            self.root.after(900, lambda b=bubble: self._show_result_message(b))

    def start_drag(self, event: tk.Event) -> None:
        self.drag_x = event.x
        self.drag_y = event.y

    def drag(self, event: tk.Event) -> None:
        x = self.root.winfo_x() + event.x - self.drag_x
        y = self.root.winfo_y() + event.y - self.drag_y
        self.base_x = x
        self.base_y = y
        self.root.geometry(f"+{x}+{y}")
        self.update_bubble_position()

    def show_menu(self, event: tk.Event) -> None:
        self.menu.tk_popup(event.x_root, event.y_root)

    def set_action(self, action: str) -> None:
        if self.closed or action not in self.actions:
            return
        if action == "stand" and self.action != "stand":
            self.root.geometry(f"+{self.base_x}+{self.base_y}")
        self.action = action
        self.frame_index = 0
        self.say_for_action(action)

    def play_once(self, action: str) -> None:
        self.set_action(action)

    def say_for_action(self, action: str) -> None:
        if self._generating or self._question_active or self._question_pending or self._showing_result:
            return
        text = {
            "stand": "我准备好啦",
            "idle": "我准备好啦",
            "correct": "答对啦!",
            "happy": "答对啦!",
            "wrong": "再想想?",
            "confused": "再想想?",
        }.get(action, "")
        if text:
            self.say(text, typewriter=False)

    def _measure_text_height(self, text: str, width: int) -> int:
        tid = self.bubble_canvas.create_text(
            0, 0, text=text, width=width, anchor="nw",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        bbox = self.bubble_canvas.bbox(tid)
        self.bubble_canvas.delete(tid)
        if bbox:
            return bbox[3] - bbox[1]
        return 40

    def _resize_bubble(self, text: str) -> None:
        text_width = int(self.bubble_width * 0.84)
        needed = self._measure_text_height(text, text_width)
        target_h = max(130, min(500, int(needed + 96)))
        if target_h == self.bubble_height:
            return
        self.bubble_height = target_h
        self.bubble_canvas.config(width=self.bubble_width, height=self.bubble_height)
        self._draw_bubble_background()
        tw = int(self.bubble_width * 0.84)
        text_y = 34 + (self.bubble_height - 34 - 58) // 2
        self.bubble_canvas.coords(self.bubble_text_id, self.bubble_width // 2, text_y)
        self.bubble_canvas.itemconfigure(self.bubble_text_id, width=tw)

    def _clear_choice_buttons(self) -> None:
        for tid in self._choice_ids:
            self.choice_canvas.delete(tid)
        self._choice_ids.clear()
        self._question_choices.clear()
        self._question_active = False
        self._question_pending = False
        if hasattr(self, "choice_bubble"):
            self.choice_bubble.withdraw()

    def _draw_choice_buttons(self) -> None:
        for tid in self._choice_ids:
            self.choice_canvas.delete(tid)
        self._choice_ids.clear()
        self._question_active = True
        self._question_pending = False
        choices = self._question_choices
        if not choices:
            self._question_active = False
            return
        canvas = self.choice_canvas
        self._resize_choice_bubble(choices[:3])
        self._draw_choice_bubble_background()
        btn_w = min(372, self.choice_bubble_width - 48)
        gap = 8
        heights = self._choice_card_heights(choices[:3], btn_w - 56)
        y = 62
        left = (self.choice_bubble_width - btn_w) // 2

        for i, c in enumerate(choices[:3]):
            btn_h = heights[i]
            tag = f"choice_{c['id']}"
            rect = canvas.create_rectangle(
                left, y, left + btn_w, y + btn_h,
                fill="#f7fbff", outline="#151949", width=2, tags=(tag, "choice_btn"),
            )
            inner = canvas.create_rectangle(
                left + 4, y + 4, left + btn_w - 4, y + btn_h - 4,
                outline="#35dfe7", width=2, tags=(tag, "choice_btn"),
            )
            badge = canvas.create_rectangle(
                left + 8, y + 8, left + 30, y + 30,
                fill="#1b2240", outline="#1b2240", tags=(tag, "choice_btn"),
            )
            badge_text = canvas.create_text(
                left + 19, y + 19,
                text=c["id"],
                fill="#ffffff", font=("Microsoft YaHei UI", 9, "bold"),
                tags=(tag, "choice_btn"),
            )
            label = canvas.create_text(
                left + 38, y + btn_h // 2,
                text=self._display_choice_text(c),
                anchor="w",
                width=btn_w - 62,
                fill="#1b2240", font=("Microsoft YaHei UI", 9, "bold"),
                tags=(tag, "choice_btn"),
            )
            canvas.tag_bind(tag, "<Button-1>", lambda e, cid=c['id']: self._on_answer_click(cid))
            canvas.tag_bind(tag, "<Enter>", lambda e, r=rect: canvas.itemconfigure(r, fill="#d8efff"))
            canvas.tag_bind(tag, "<Leave>", lambda e, r=rect: canvas.itemconfigure(r, fill="#f7fbff"))
            self._choice_ids.append(rect)
            self._choice_ids.append(inner)
            self._choice_ids.append(badge)
            self._choice_ids.append(badge_text)
            self._choice_ids.append(label)
            y += btn_h + gap
        if self.bubble_visible:
            self.choice_bubble.deiconify()
        self.update_bubble_position()

    def _measure_choice_text_height(self, text: str, width: int) -> int:
        tid = self.choice_canvas.create_text(
            0, 0, text=text, width=width, anchor="nw",
            font=("Microsoft YaHei UI", 9, "bold"),
        )
        bbox = self.choice_canvas.bbox(tid)
        self.choice_canvas.delete(tid)
        if bbox:
            return bbox[3] - bbox[1]
        return 20

    def _choice_card_heights(self, choices: list[dict], text_width: int) -> list[int]:
        heights = []
        for choice in choices:
            text_h = self._measure_choice_text_height(self._display_choice_text(choice), text_width)
            heights.append(max(48, min(104, text_h + 24)))
        return heights

    def _display_choice_text(self, choice: dict) -> str:
        text = str(choice.get("text", "")).strip()
        for marker in ("，因为", "。因为", "；因为", ", because", ". because", "; because"):
            if marker in text:
                text = text.split(marker, 1)[0].strip()
        if len(text) > 34:
            text = text[:33].rstrip() + "..."
        return text

    def _resize_choice_bubble(self, choices: list[dict]) -> None:
        btn_w = min(372, self.choice_bubble_width - 48)
        heights = self._choice_card_heights(choices, btn_w - 56)
        target_h = max(220, min(430, 78 + sum(heights) + max(0, len(choices) - 1) * 8))
        if target_h == self.choice_bubble_height:
            return
        self.choice_bubble_height = target_h
        self.choice_canvas.config(width=self.choice_bubble_width, height=self.choice_bubble_height)

    def _on_answer_click(self, choice_id: str) -> None:
        self._clear_choice_buttons()
        q_path = QUESTION_LOOP_DIR / "current_question.json"
        if not q_path.exists():
            return
        try:
            data = json.loads(q_path.read_text(encoding="utf-8"))
        except Exception:
            return
        q = data.get("question", {})
        correct = q.get("correct_choice", "").strip().upper()
        user = choice_id.strip().upper()
        is_correct = user == correct

        # Write result for polling fallback
        result = {
            "result": "correct" if is_correct else "wrong",
            "pet_action": "correct" if is_correct else "wrong",
            "bubble_text": f"答对啦！{q.get('explanation', '')}" if is_correct
            else f"再想想。正确答案是 {correct}。{q.get('explanation', '')}",
        }
        QL_DIR = QUESTION_LOOP_DIR
        QL_DIR.mkdir(parents=True, exist_ok=True)
        result_path = QL_DIR / "latest_result.json"
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if hasattr(self, "_last_result_mtime"):
            try:
                self._last_result_mtime = result_path.stat().st_mtime_ns
            except OSError:
                pass

        # Immediate animation
        self._showing_result = True
        self.play_once("correct" if is_correct else "wrong")
        self.root.after(900, lambda: self._show_result_message(result["bubble_text"]))

        # Background: append history
        def _append() -> None:
            try:
                subprocess.run(
                    [sys.executable, str(self._answer_script), choice_id],
                    capture_output=True, text=True, timeout=10,
                    cwd=str(BASE_DIR),
                )
            except Exception:
                pass
        threading.Thread(target=_append, daemon=True).start()

    def _show_result_message(self, text: str) -> None:
        if self.closed:
            return
        if self._result_after_id:
            self.root.after_cancel(self._result_after_id)
            self._result_after_id = None
        self._showing_result = True
        self.say(text, typewriter=True)
        self._result_after_id = self.root.after(7600, self._finish_result_message)

    def _finish_result_message(self) -> None:
        self._result_after_id = None
        self._showing_result = False

    def _cancel_typewriter(self) -> None:
        if self._tw_after_id:
            self.root.after_cancel(self._tw_after_id)
            self._tw_after_id = None

    def _typewriter_tick(self) -> None:
        if self.closed:
            return
        self._tw_index += 1
        partial = self._tw_text[:self._tw_index]
        self.bubble_canvas.itemconfigure(self.bubble_text_id, text=partial)
        if self._tw_index < len(self._tw_text):
            delay = 18 if self._tw_text[self._tw_index - 1] <= "ÿ" else 35
            self._tw_after_id = self.root.after(delay, self._typewriter_tick)
        else:
            self._tw_after_id = None
            cb = self._tw_callback
            self._tw_callback = None
            if cb is not None:
                cb()

    def say(self, text: str, duration_ms: int | None = None, typewriter: bool = True, on_done: object = None) -> None:
        if self.closed:
            return
        self._cancel_typewriter()
        self._clear_choice_buttons()
        if self.bubble_after_id:
            self.root.after_cancel(self.bubble_after_id)
            self.bubble_after_id = None
        if self.bubble_visible:
            self.bubble.deiconify()

        self._resize_bubble(text)
        if typewriter:
            self.update_bubble_position()
            self._tw_text = text
            self._tw_index = 0
            self.bubble_canvas.itemconfigure(self.bubble_text_id, text="")

            def _on_done() -> None:
                if duration_ms:
                    self.bubble_after_id = self.root.after(duration_ms, self.bubble.withdraw)
                if on_done is not None:
                    on_done()

            self._tw_callback = _on_done
            self._tw_after_id = self.root.after(50, self._typewriter_tick)
        else:
            self.bubble_canvas.itemconfigure(self.bubble_text_id, text=text)
            self.update_bubble_position()
            if duration_ms:
                self.bubble_after_id = self.root.after(duration_ms, self.bubble.withdraw)

    def toggle_bubble(self) -> None:
        self.bubble_visible = not self.bubble_visible
        if self.bubble_visible:
            self.bubble.deiconify()
            if self._question_active:
                self.choice_bubble.deiconify()
            self.update_bubble_position()
        else:
            self.bubble.withdraw()
            self.choice_bubble.withdraw()

    def update_bubble_position(self) -> None:
        if self.closed or not self.bubble_visible:
            return
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        pet_w = max(1, self.label.winfo_width())
        x = self.base_x + max(0, (pet_w - self.bubble_width) // 2)
        stack_gap = 6 if self._question_active else 0
        choice_h = self.choice_bubble_height if self._question_active else 0
        y = max(8, self.base_y - self.bubble_height - choice_h - stack_gap - 2)
        x = max(8, min(x, screen_w - self.bubble_width - 8))
        self.bubble.geometry(f"{self.bubble_width}x{self.bubble_height}+{x}+{y}")
        if self._question_active:
            cx = self.base_x + max(0, (pet_w - self.choice_bubble_width) // 2)
            cx = max(8, min(cx, screen_w - self.choice_bubble_width - 8))
            cy = y + self.bubble_height + stack_gap
            self.choice_bubble.geometry(f"{self.choice_bubble_width}x{self.choice_bubble_height}+{cx}+{cy}")

    def animate(self) -> None:
        if self.closed:
            return

        frames = self.actions[self.action]
        frame = frames[self.frame_index % len(frames)]
        self.label.configure(image=frame)
        self.label.image = frame

        self.apply_motion()
        self.update_bubble_position()
        self.frame_index += 1

        if self.action in {"correct", "wrong", "happy", "confused"} and self.frame_index >= len(frames):
            if self._showing_result:
                self.action = "stand"
                self.frame_index = 0
            else:
                self.set_action("stand")

        delay = {
            "stand": 520,
            "correct": 135,
            "wrong": 170,
            "idle": 520,
            "happy": 135,
            "confused": 170,
        }.get(self.action, 220)
        self.root.after(delay, self.animate)

    def apply_motion(self) -> None:
        if self.action in {"stand", "idle"}:
            if (
                not self._generating
                and not self._question_active
                and not self._question_pending
                and not self._showing_result
                and random.random() < 0.018
            ):
                self.set_action("wrong")
                return
            offset = -1 if self.float_step % 2 else 1
            self.float_step += 1
            self.root.geometry(f"+{self.base_x}+{self.base_y + offset}")
            return

        if self.action in {"correct", "happy"}:
            bounce_pattern = (0, -4, -9, -12, -8, -4, -1)
            bounce = bounce_pattern[self.frame_index % len(bounce_pattern)]
            self.root.geometry(f"+{self.base_x}+{self.base_y + bounce}")
            return

        if self.action in {"wrong", "confused"}:
            shake = -4 if self.frame_index % 2 else 4
            self.root.geometry(f"+{self.base_x + shake}+{self.base_y}")

    def close(self) -> None:
        self.closed = True
        if self._result_after_id:
            self.root.after_cancel(self._result_after_id)
        self.choice_bubble.destroy()
        self.bubble.destroy()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def ensure_frames() -> None:
    required_dirs = [ANSWER_ACTION_DIR / action for action in ("stand", "correct", "wrong")]
    if all(path.exists() and any(path.glob("frame_*.png")) for path in required_dirs):
        return

    for path, label in (
        (CROP_SCRIPT, "Crop script"),
        (ALIGN_SCRIPT, "Align script"),
        (ANSWER_ACTION_SCRIPT, "Answer action script"),
    ):
        if not path.exists():
            raise FileNotFoundError(f"{label} not found: {path}")

    if not FRAME_DIR.exists() or not any(FRAME_DIR.glob("frame_*.png")):
        if not SPRITE_SOURCE.exists():
            raise FileNotFoundError(
                f"Action frames are missing and source sprite sheet was not found: {SPRITE_SOURCE}"
            )
        if not RAW_FRAME_DIR.exists() or not any(RAW_FRAME_DIR.glob("frame_*.png")):
            subprocess.run([sys.executable, str(CROP_SCRIPT)], cwd=BASE_DIR, check=True)
        subprocess.run([sys.executable, str(ALIGN_SCRIPT)], cwd=BASE_DIR, check=True)

    if any(not path.exists() or not any(path.glob("frame_*.png")) for path in required_dirs):
        subprocess.run([sys.executable, str(ANSWER_ACTION_SCRIPT)], cwd=BASE_DIR, check=True)


if __name__ == "__main__":
    ensure_frames()
    DesktopPet().run()
