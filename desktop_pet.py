from __future__ import annotations

import json
import random
import subprocess
import sys
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
POLL_INTERVAL_MS = 800


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
        self._last_event_at = ""

        self.actions = self.load_actions()

        self.label = tk.Label(self.root, bg="#010101", bd=0, highlightthickness=0)
        self.label.pack()
        self.label.bind("<ButtonPress-1>", self.start_drag)
        self.label.bind("<B1-Motion>", self.drag)
        self.label.bind("<Button-3>", self.show_menu)
        self.label.bind("<Double-Button-1>", lambda _event: self.play_once("correct"))
        self.label.bind("<Button-2>", lambda _event: self.play_once("wrong"))

        self.bubble = self.create_bubble()

        self.menu = tk.Menu(self.root, tearoff=False)
        self.menu.add_command(label="站立", command=lambda: self.set_action("stand"))
        self.menu.add_command(label="答对", command=lambda: self.play_once("correct"))
        self.menu.add_command(label="答错", command=lambda: self.play_once("wrong"))
        self.menu.add_separator()
        self.menu.add_command(label="显示/隐藏气泡", command=self.toggle_bubble)
        self.menu.add_command(label="退出", command=self.close)

        self.place_initially()
        self.say("我准备好啦")
        self.animate()

    def create_bubble(self) -> tk.Toplevel:
        bubble = tk.Toplevel(self.root)
        bubble.overrideredirect(True)
        bubble.attributes("-topmost", True)
        bubble.attributes("-transparentcolor", "#010101")
        bubble.configure(bg="#010101")

        self.bubble_canvas = tk.Canvas(
            bubble,
            width=150,
            height=60,
            bg="#010101",
            bd=0,
            highlightthickness=0,
        )
        self.bubble_canvas.pack()
        self.draw_bubble_shape()
        self.bubble_text_id = self.bubble_canvas.create_text(
            75,
            25,
            text="",
            width=116,
            fill="#1b2240",
            font=("Microsoft YaHei UI", 9, "bold"),
            justify="center",
        )
        return bubble

    def draw_bubble_shape(self) -> None:
        canvas = self.bubble_canvas
        fill = "#ffffff"
        outline = "#151949"
        accent = "#35dfe7"

        # Pixel bubble: draw blocky stepped rectangles instead of antialiased curves.
        blocks = [
            (24, 6, 126, 10),
            (16, 10, 134, 16),
            (12, 16, 138, 40),
            (20, 40, 130, 48),
            (62, 48, 84, 52),
            (70, 52, 76, 58),
        ]
        for box in blocks:
            canvas.create_rectangle(*box, fill=outline, outline=outline)

        inner_blocks = [
            (26, 10, 124, 14),
            (18, 14, 132, 20),
            (16, 20, 134, 38),
            (24, 38, 126, 44),
            (66, 44, 80, 48),
            (72, 48, 74, 54),
        ]
        for box in inner_blocks:
            canvas.create_rectangle(*box, fill=fill, outline=fill)

        for box in ((24, 18, 28, 22), (122, 18, 126, 22), (30, 40, 34, 44), (116, 40, 120, 44)):
            canvas.create_rectangle(*box, fill="#dfe8ff", outline="#dfe8ff")
        for box in ((128, 24, 132, 28), (128, 32, 132, 36), (18, 26, 22, 30)):
            canvas.create_rectangle(*box, fill=accent, outline=accent)

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
        self._poll_events()

    def _poll_events(self) -> None:
        self.check_events()
        if not self.closed:
            self.root.after(POLL_INTERVAL_MS, self._poll_events)

    def check_events(self) -> None:
        latest_path = CLAUDE_EVENTS_DIR / "latest.json"
        if not latest_path.exists():
            return
        try:
            mtime = latest_path.stat().st_mtime_ns
        except OSError:
            return
        if self._last_event_at and mtime <= self._last_event_at:
            return
        try:
            data = json.loads(latest_path.read_text(encoding="utf-8"))
        except Exception:
            return
        self._last_event_at = mtime
        preview = data.get("prompt_preview", "")
        text = preview.strip().split("\n")[-1][:36] if preview.strip() else ""
        self.say(text or "收到啦！")
        self.play_once("correct")

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
        text = {
            "stand": "我准备好啦",
            "idle": "我准备好啦",
            "correct": "答对啦!",
            "happy": "答对啦!",
            "wrong": "再想想?",
            "confused": "再想想?",
        }.get(action, "")
        if text:
            self.say(text)

    def say(self, text: str, duration_ms: int | None = None) -> None:
        if self.closed:
            return
        self.bubble_canvas.itemconfigure(self.bubble_text_id, text=text)
        if self.bubble_visible:
            self.bubble.deiconify()
            self.update_bubble_position()
        if self.bubble_after_id:
            self.root.after_cancel(self.bubble_after_id)
            self.bubble_after_id = None
        if duration_ms:
            self.bubble_after_id = self.root.after(duration_ms, self.bubble.withdraw)

    def toggle_bubble(self) -> None:
        self.bubble_visible = not self.bubble_visible
        if self.bubble_visible:
            self.bubble.deiconify()
            self.update_bubble_position()
        else:
            self.bubble.withdraw()

    def update_bubble_position(self) -> None:
        if self.closed or not self.bubble_visible:
            return
        self.root.update_idletasks()
        pet_w = max(1, self.label.winfo_width())
        x = self.base_x + max(0, (pet_w - 150) // 2)
        y = max(8, self.base_y - 62)
        self.bubble.geometry(f"+{x}+{y}")

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
            if random.random() < 0.018:
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
