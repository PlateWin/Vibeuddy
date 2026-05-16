from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image


def color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def sample_border_color(image: Image.Image) -> tuple[int, int, int]:
    width, height = image.size
    pixels = image.convert("RGB").load()
    samples: list[tuple[int, int, int]] = []

    for x in range(width):
        samples.append(pixels[x, 0])
        samples.append(pixels[x, height - 1])
    for y in range(height):
        samples.append(pixels[0, y])
        samples.append(pixels[width - 1, y])

    samples.sort()
    return samples[len(samples) // 2]


def make_background_transparent(
    image: Image.Image,
    threshold: int = 58,
    edge_feather: bool = True,
) -> Image.Image:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    bg = sample_border_color(rgba)
    visited = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def is_removable(x: int, y: int) -> bool:
        r, g, b, a = pixels[x, y]
        if a == 0:
            return True
        return color_distance((r, g, b), bg) <= threshold

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
            index = y * width + x
            if visited[index]:
                pixels[x, y] = (255, 255, 255, 0)
            elif edge_feather:
                r, g, b, a = pixels[x, y]
                if a and color_distance((r, g, b), bg) <= threshold + 18:
                    touches_transparent = False
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if 0 <= nx < width and 0 <= ny < height and visited[ny * width + nx]:
                            touches_transparent = True
                            break
                    if touches_transparent:
                        pixels[x, y] = (r, g, b, min(a, 150))

    return rgba


def save_black_preview(image: Image.Image, output_path: Path) -> None:
    preview = Image.new("RGBA", image.size, (0, 0, 0, 255))
    preview.alpha_composite(image.convert("RGBA"))
    preview.save(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crop a sprite sheet into transparent PNG frames."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="cropped_522x649 (2).png",
        help="Source sprite sheet path.",
    )
    parser.add_argument("--cols", type=int, default=3, help="Frame columns.")
    parser.add_argument("--rows", type=int, default=3, help="Frame rows.")
    parser.add_argument(
        "--threshold",
        type=int,
        default=58,
        help="Background color distance threshold.",
    )
    parser.add_argument(
        "--out-dir",
        default="assets/pet_frames",
        help="Output directory for transparent frame PNG files.",
    )
    parser.add_argument(
        "--sheet-out",
        default="assets/pet-sprite-transparent.png",
        help="Output path for transparent full sprite sheet.",
    )
    parser.add_argument(
        "--preview-out",
        default="assets/pet-sprite-black-preview.png",
        help="Output path for black-background preview.",
    )
    args = parser.parse_args()

    source = Path(args.input)
    out_dir = Path(args.out_dir)
    sheet_out = Path(args.sheet_out)
    preview_out = Path(args.preview_out)

    sheet = Image.open(source).convert("RGBA")
    width, height = sheet.size
    frame_width = width // args.cols
    frame_height = height // args.rows

    if width % args.cols or height % args.rows:
        raise ValueError(
            f"Sheet size {width}x{height} is not divisible by {args.cols}x{args.rows}."
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    sheet_out.parent.mkdir(parents=True, exist_ok=True)
    preview_out.parent.mkdir(parents=True, exist_ok=True)

    transparent_sheet = Image.new("RGBA", sheet.size, (255, 255, 255, 0))

    for row in range(args.rows):
        for col in range(args.cols):
            index = row * args.cols + col + 1
            box = (
                col * frame_width,
                row * frame_height,
                (col + 1) * frame_width,
                (row + 1) * frame_height,
            )
            frame = sheet.crop(box)
            transparent_frame = make_background_transparent(
                frame,
                threshold=args.threshold,
            )
            frame_path = out_dir / f"frame_{index:02d}.png"
            transparent_frame.save(frame_path)
            transparent_sheet.alpha_composite(transparent_frame, (box[0], box[1]))

    transparent_sheet.save(sheet_out)
    save_black_preview(transparent_sheet, preview_out)

    print(f"Saved frames: {out_dir}")
    print(f"Saved transparent sheet: {sheet_out}")
    print(f"Saved black preview: {preview_out}")


if __name__ == "__main__":
    main()
