from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image


ACTION_NAMES = ("idle", "walk", "confused", "roll")


def color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def make_key_transparent(image: Image.Image, key: tuple[int, int, int], threshold: int) -> Image.Image:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    visited = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def is_key(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        return a == 0 or color_distance((r, g, b), key) <= threshold

    def push(x: int, y: int) -> None:
        if 0 <= x < width and 0 <= y < height:
            idx = y * width + x
            if not visited[idx] and is_key(x, y):
                visited[idx] = 1
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
            else:
                r, g, b, a = pixels[x, y]
                # Remove chroma-key antialias halos without touching cyan pet markings.
                green_dominant = g > 150 and g > r + 45 and g > b + 45
                near_key = color_distance((r, g, b), key) <= threshold + 72
                if green_dominant and near_key:
                    pixels[x, y] = (255, 255, 255, 0)
    return rgba


def alpha_bbox(image: Image.Image, alpha_threshold: int = 12) -> tuple[int, int, int, int] | None:
    alpha = image.getchannel("A")
    mask = alpha.point(lambda value: 255 if value >= alpha_threshold else 0)
    return mask.getbbox()


def center_on_canvas(image: Image.Image, canvas_size: tuple[int, int]) -> Image.Image:
    canvas = Image.new("RGBA", canvas_size, (255, 255, 255, 0))
    bbox = alpha_bbox(image)
    if bbox is None:
        return canvas

    subject = image.crop(bbox)
    x = (canvas_size[0] - subject.width) // 2
    y = (canvas_size[1] - subject.height) // 2
    canvas.alpha_composite(subject, (x, y))
    return canvas


def split_sheet(
    source: Image.Image,
    out_root: Path,
    rows: int,
    cols: int,
    key_rgb: tuple[int, int, int],
    threshold: int,
) -> None:
    width, height = source.size

    if width % cols or height % rows:
        raise ValueError(f"Sheet size {width}x{height} is not divisible by {cols}x{rows}")

    cell_w = width // cols
    cell_h = height // rows

    for row, action in enumerate(ACTION_NAMES):
        action_dir = out_root / action
        action_dir.mkdir(parents=True, exist_ok=True)
        for old in action_dir.glob("frame_*.png"):
            old.unlink()

        raw_frames: list[Image.Image] = []
        max_w = 0
        max_h = 0

        for col in range(cols):
            box = (col * cell_w, row * cell_h, (col + 1) * cell_w, (row + 1) * cell_h)
            frame = make_key_transparent(source.crop(box), key_rgb, threshold)
            bbox = alpha_bbox(frame)
            if bbox:
                subject = frame.crop(bbox)
                raw_frames.append(subject)
                max_w = max(max_w, subject.width)
                max_h = max(max_h, subject.height)
            else:
                raw_frames.append(frame)
                max_w = max(max_w, frame.width)
                max_h = max(max_h, frame.height)

        canvas_size = (max_w + max_w % 2, max_h + max_h % 2)
        for index, frame in enumerate(raw_frames, start=1):
            aligned = center_on_canvas(frame, canvas_size)
            aligned.save(action_dir / f"frame_{index:02d}.png")


def split_action_strip(
    action: str,
    source: Image.Image,
    out_root: Path,
    cols: int,
    key_rgb: tuple[int, int, int],
    threshold: int,
) -> None:
    width, height = source.size
    if width % cols:
        raise ValueError(f"{action} strip size {width}x{height} is not divisible by {cols} columns")

    cell_w = width // cols
    action_dir = out_root / action
    action_dir.mkdir(parents=True, exist_ok=True)
    for old in action_dir.glob("frame_*.png"):
        old.unlink()

    raw_frames: list[Image.Image] = []
    max_w = 0
    max_h = 0

    for col in range(cols):
        box = (col * cell_w, 0, (col + 1) * cell_w, height)
        frame = make_key_transparent(source.crop(box), key_rgb, threshold)
        bbox = alpha_bbox(frame)
        if bbox:
            subject = frame.crop(bbox)
            raw_frames.append(subject)
            max_w = max(max_w, subject.width)
            max_h = max(max_h, subject.height)
        else:
            raw_frames.append(frame)
            max_w = max(max_w, frame.width)
            max_h = max(max_h, frame.height)

    canvas_size = (max_w + max_w % 2, max_h + max_h % 2)
    for index, frame in enumerate(raw_frames, start=1):
        aligned = center_on_canvas(frame, canvas_size)
        aligned.save(action_dir / f"frame_{index:02d}.png")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split a 4-row pet action spritesheet into desktop-pet action folders."
    )
    parser.add_argument("input", nargs="?", help="4-row action spritesheet path.")
    parser.add_argument("--idle", help="Single-row idle action strip path.")
    parser.add_argument("--walk", help="Single-row walk action strip path.")
    parser.add_argument("--confused", help="Single-row confused action strip path.")
    parser.add_argument("--roll", help="Single-row roll action strip path.")
    parser.add_argument("--cols", type=int, default=6, help="Frame columns per action row.")
    parser.add_argument("--rows", type=int, default=4, help="Action rows. Expected: 4.")
    parser.add_argument("--out-dir", default="assets/pet_actions", help="Output action root.")
    parser.add_argument("--key", default="#00ff00", help="Chroma key color, e.g. #00ff00.")
    parser.add_argument("--threshold", type=int, default=24, help="Chroma key threshold.")
    args = parser.parse_args()

    if args.rows != len(ACTION_NAMES):
        raise ValueError(f"Expected {len(ACTION_NAMES)} rows: {', '.join(ACTION_NAMES)}")

    key = args.key.lstrip("#")
    key_rgb = tuple(int(key[i : i + 2], 16) for i in (0, 2, 4))
    out_root = Path(args.out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    separate_inputs = {
        "idle": args.idle,
        "walk": args.walk,
        "confused": args.confused,
        "roll": args.roll,
    }
    provided_separate = {name: path for name, path in separate_inputs.items() if path}

    if provided_separate:
        missing = [name for name in ACTION_NAMES if not separate_inputs[name]]
        if missing:
            raise ValueError(f"Missing separate action strip(s): {', '.join(missing)}")
        for action in ACTION_NAMES:
            source = Image.open(separate_inputs[action]).convert("RGBA")
            split_action_strip(action, source, out_root, args.cols, key_rgb, args.threshold)
    else:
        if not args.input:
            raise ValueError("Provide either a 4-row input sheet or --idle --walk --confused --roll.")
        source = Image.open(args.input).convert("RGBA")
        split_sheet(source, out_root, args.rows, args.cols, key_rgb, args.threshold)

    print(f"Saved action frames to {out_root}")
    print("Actions: idle, walk, confused, roll")


if __name__ == "__main__":
    main()
