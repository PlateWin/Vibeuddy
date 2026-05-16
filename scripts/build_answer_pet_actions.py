from __future__ import annotations

import argparse
from collections import deque
import json
import shutil
from pathlib import Path

from PIL import Image


DEFAULT_CORRECT_SHEET = Path("assets/Gemini_Generated_Image_lbj5g2lbj5g2lbj5.png")

ACTION_SEQUENCES: dict[str, list[int]] = {
    "stand": [1, 2, 5, 6, 5, 2],
    "correct": [1, 5, 2, 6, 2, 1],
    "wrong": [2, 3, 4, 3, 2, 1],
}

ACTION_ALIASES: dict[str, str] = {
    "idle": "stand",
    "happy": "correct",
    "confused": "wrong",
}


def color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def sample_border_color(image: Image.Image) -> tuple[int, int, int]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    pixels = rgb.load()
    samples: list[tuple[int, int, int]] = []

    for x in range(width):
        samples.append(pixels[x, 0])
        samples.append(pixels[x, height - 1])
    for y in range(height):
        samples.append(pixels[0, y])
        samples.append(pixels[width - 1, y])

    samples.sort()
    return samples[len(samples) // 2]


def make_background_transparent(image: Image.Image, threshold: int = 58) -> Image.Image:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    bg = sample_border_color(rgba)
    visited = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def is_removable(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        return a == 0 or color_distance((r, g, b), bg) <= threshold

    def push(x: int, y: int) -> None:
        if 0 <= x < width and 0 <= y < height:
            index = y * width + x
            if not visited[index] and is_removable(x, y):
                visited[index] = 1
                queue.append((x, y))

    for x in range(width):
        push(x, 0)
        push(x, height - 1)
    for y in range(height):
        push(0, y)
        push(width - 1, y)

    while queue:
        x, y = queue.popleft()
        push(x + 1, y)
        push(x - 1, y)
        push(x, y + 1)
        push(x, y - 1)

    for y in range(height):
        for x in range(width):
            if visited[y * width + x]:
                pixels[x, y] = (255, 255, 255, 0)
    return rgba


def alpha_bbox(image: Image.Image, alpha_threshold: int = 12) -> tuple[int, int, int, int] | None:
    alpha = image.convert("RGBA").getchannel("A")
    mask = alpha.point(lambda value: 255 if value >= alpha_threshold else 0)
    return mask.getbbox()


def collect_sequence_frames(frame_dir: Path, sequence: list[int]) -> list[Image.Image]:
    frames: list[Image.Image] = []
    missing: list[Path] = []

    for number in sequence:
        path = frame_dir / f"frame_{number:02d}.png"
        if not path.exists():
            missing.append(path)
            continue
        frames.append(Image.open(path).convert("RGBA"))

    if missing:
        names = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Missing source frame(s): {names}")
    return frames


def collect_sheet_frames(
    sheet_path: Path,
    cols: int,
    rows: int,
    limit: int,
    background_threshold: int,
) -> list[Image.Image]:
    sheet = Image.open(sheet_path).convert("RGBA")
    frames: list[Image.Image] = []

    for index in range(limit):
        row = index // cols
        col = index % cols
        if row >= rows:
            raise ValueError(f"Requested {limit} frames but sheet only has {cols * rows} slots.")

        left = round(col * sheet.width / cols)
        top = round(row * sheet.height / rows)
        right = round((col + 1) * sheet.width / cols)
        bottom = round((row + 1) * sheet.height / rows)
        frames.append(make_background_transparent(sheet.crop((left, top, right, bottom)), background_threshold))

    return frames


def collect_sheet_frame(
    sheet_path: Path,
    cols: int,
    rows: int,
    slot: int,
    background_threshold: int,
) -> Image.Image:
    if slot < 1 or slot > cols * rows:
        raise ValueError(f"Slot {slot} is outside the {cols}x{rows} sheet.")

    return collect_sheet_frames(sheet_path, cols, rows, slot, background_threshold)[slot - 1]


def normalize_frames(frames: list[Image.Image], padding: int) -> list[Image.Image]:
    subjects: list[Image.Image] = []
    max_width = 0
    max_height = 0

    for frame in frames:
        bbox = alpha_bbox(frame)
        if bbox is None:
            raise ValueError("Source frame has no visible pixels.")

        left, top, right, bottom = bbox
        left = max(0, left - padding)
        top = max(0, top - padding)
        right = min(frame.width, right + padding)
        bottom = min(frame.height, bottom + padding)
        subject = frame.crop((left, top, right, bottom))
        subjects.append(subject)
        max_width = max(max_width, subject.width)
        max_height = max(max_height, subject.height)

    canvas_size = (max_width + max_width % 2, max_height + max_height % 2)
    normalized: list[Image.Image] = []
    for subject in subjects:
        canvas = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
        x = (canvas_size[0] - subject.width) // 2
        y = (canvas_size[1] - subject.height) // 2
        canvas.alpha_composite(subject, (x, y))
        normalized.append(canvas)
    return normalized


def normalize_frame_to_canvas(image: Image.Image, canvas_size: tuple[int, int], padding: int) -> Image.Image:
    bbox = alpha_bbox(image)
    if bbox is None:
        raise ValueError("Source frame has no visible pixels.")

    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(image.width, right + padding)
    bottom = min(image.height, bottom + padding)
    subject = image.crop((left, top, right, bottom))

    if subject.width > canvas_size[0] or subject.height > canvas_size[1]:
        scale = min(canvas_size[0] / subject.width, canvas_size[1] / subject.height)
        new_size = (
            max(1, round(subject.width * scale)),
            max(1, round(subject.height * scale)),
        )
        subject = subject.resize(new_size, Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
    x = (canvas_size[0] - subject.width) // 2
    y = (canvas_size[1] - subject.height) // 2
    canvas.alpha_composite(subject, (x, y))
    return canvas


def save_action(action_dir: Path, frames: list[Image.Image]) -> None:
    action_dir.mkdir(parents=True, exist_ok=True)
    for old in action_dir.glob("frame_*.png"):
        old.unlink()
    for index, frame in enumerate(frames, start=1):
        frame.save(action_dir / f"frame_{index:02d}.png")


def append_correct_restore_frame(
    out_dir: Path,
    sheet_path: Path,
    cols: int,
    rows: int,
    slot: int,
    source_frame: int,
    background_threshold: int,
    padding: int,
) -> None:
    correct_dir = out_dir / "correct"
    if source_frame:
        shutil.copy2(correct_dir / f"frame_{source_frame:02d}.png", correct_dir / "frame_07.png")
    else:
        first_frame = Image.open(correct_dir / "frame_01.png").convert("RGBA")
        restore = collect_sheet_frame(sheet_path, cols, rows, slot, background_threshold)
        normalized = normalize_frame_to_canvas(restore, first_frame.size, padding)
        normalized.save(correct_dir / "frame_07.png")

    happy_dir = out_dir / "happy"
    happy_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(correct_dir / "frame_07.png", happy_dir / "frame_07.png")


def mirror_aliases(out_dir: Path, aliases: dict[str, str]) -> None:
    for alias, target in aliases.items():
        alias_dir = out_dir / alias
        target_dir = out_dir / target
        alias_dir.mkdir(parents=True, exist_ok=True)
        for old in alias_dir.glob("frame_*.png"):
            old.unlink()
        for source in sorted(target_dir.glob("frame_*.png")):
            shutil.copy2(source, alias_dir / source.name)


def save_manifest(out_dir: Path) -> None:
    manifest = {
        "pet": "cyber-kitten",
        "source_frames": "assets/pet_frames_aligned/frame_XX.png",
        "actions": {
            action: {
                "frames": sequence,
                "description": description,
            }
            for action, sequence, description in (
                ("stand", ACTION_SEQUENCES["stand"], "Idle standing loop with light breathing and blink variation."),
                ("correct", [1, 2, 3, 4, 5, 6, 7], "Answer-correct loop with frame 7 as a recovery pose between frame 6 and the initial pose."),
                ("wrong", ACTION_SEQUENCES["wrong"], "Answer-wrong loop with confused and closed-eye frames."),
            )
        },
        "correct_source_sheet": str(DEFAULT_CORRECT_SHEET),
        "correct_saved_frames": 7,
        "aliases": ACTION_ALIASES,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def make_preview(out_dir: Path, output: Path) -> None:
    actions = list(ACTION_SEQUENCES)
    loaded: list[tuple[str, list[Image.Image]]] = []
    max_width = 0
    max_height = 0

    for action in actions:
        frames = [Image.open(path).convert("RGBA") for path in sorted((out_dir / action).glob("frame_*.png"))]
        loaded.append((action, frames))
        for frame in frames:
            max_width = max(max_width, frame.width)
            max_height = max(max_height, frame.height)

    max_cols = max((len(frames) for _action, frames in loaded), default=0)
    cell_w = max_width
    cell_h = max_height
    preview = Image.new("RGBA", (cell_w * max_cols, cell_h * len(loaded)), (0, 0, 0, 255))

    for row, (_action, frames) in enumerate(loaded):
        for col, frame in enumerate(frames):
            x = col * cell_w + (cell_w - frame.width) // 2
            y = row * cell_h + (cell_h - frame.height) // 2
            preview.alpha_composite(frame, (x, y))

    output.parent.mkdir(parents=True, exist_ok=True)
    preview.save(output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build stand/correct/wrong desktop-pet actions from aligned cyber kitten frames."
    )
    parser.add_argument("--frame-dir", default="assets/pet_frames_aligned")
    parser.add_argument("--out-dir", default="assets/pet_answer_actions_v2")
    parser.add_argument("--preview-out", default="assets/pet_answer_actions_v2_preview.png")
    parser.add_argument("--correct-sheet", default=str(DEFAULT_CORRECT_SHEET))
    parser.add_argument("--correct-cols", type=int, default=3)
    parser.add_argument("--correct-rows", type=int, default=3)
    parser.add_argument("--correct-frame-limit", type=int, default=6)
    parser.add_argument("--correct-restore-slot", type=int, default=7)
    parser.add_argument("--correct-restore-source-frame", type=int, default=2)
    parser.add_argument("--background-threshold", type=int, default=58)
    parser.add_argument("--padding", type=int, default=18)
    parser.add_argument(
        "--only",
        choices=("all", "stand", "correct", "wrong", "correct-restore"),
        default="all",
        help="Limit rebuild to one primary action. Aliases are still refreshed when relevant.",
    )
    args = parser.parse_args()

    frame_dir = Path(args.frame_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.only in {"all", "stand"}:
        frames = collect_sequence_frames(frame_dir, ACTION_SEQUENCES["stand"])
        save_action(out_dir / "stand", normalize_frames(frames, args.padding))

    if args.only in {"all", "wrong"}:
        frames = collect_sequence_frames(frame_dir, ACTION_SEQUENCES["wrong"])
        save_action(out_dir / "wrong", normalize_frames(frames, args.padding))

    if args.only in {"all", "correct"}:
        correct_sheet = Path(args.correct_sheet)
        if correct_sheet.exists():
            correct_frames = collect_sheet_frames(
                correct_sheet,
                args.correct_cols,
                args.correct_rows,
                args.correct_frame_limit,
                args.background_threshold,
            )
        else:
            correct_frames = collect_sequence_frames(frame_dir, ACTION_SEQUENCES["correct"])
        save_action(out_dir / "correct", normalize_frames(correct_frames, args.padding))
        append_correct_restore_frame(
            out_dir,
            Path(args.correct_sheet),
            args.correct_cols,
            args.correct_rows,
            args.correct_restore_slot,
            args.correct_restore_source_frame,
            args.background_threshold,
            args.padding,
        )

    if args.only == "correct-restore":
        append_correct_restore_frame(
            out_dir,
            Path(args.correct_sheet),
            args.correct_cols,
            args.correct_rows,
            args.correct_restore_slot,
            args.correct_restore_source_frame,
            args.background_threshold,
            args.padding,
        )

    aliases_to_refresh = ACTION_ALIASES
    if args.only == "correct-restore":
        aliases_to_refresh = {}
    elif args.only != "all":
        aliases_to_refresh = {alias: target for alias, target in ACTION_ALIASES.items() if target == args.only}
    mirror_aliases(out_dir, aliases_to_refresh)
    save_manifest(out_dir)
    make_preview(out_dir, Path(args.preview_out))

    print(f"Saved actions: {', '.join(ACTION_SEQUENCES)}")
    print(f"Saved aliases: {', '.join(ACTION_ALIASES)}")
    print(f"Saved manifest: {out_dir / 'manifest.json'}")
    print(f"Saved preview: {args.preview_out}")


if __name__ == "__main__":
    main()
