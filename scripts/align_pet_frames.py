from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def alpha_bbox(image: Image.Image, alpha_threshold: int) -> tuple[int, int, int, int] | None:
    alpha = image.convert("RGBA").getchannel("A")
    mask = alpha.point(lambda value: 255 if value >= alpha_threshold else 0)
    return mask.getbbox()


def crop_to_subject(image: Image.Image, bbox: tuple[int, int, int, int], padding: int) -> Image.Image:
    width, height = image.size
    left, top, right, bottom = bbox
    left = max(0, left - padding)
    top = max(0, top - padding)
    right = min(width, right + padding)
    bottom = min(height, bottom + padding)
    return image.crop((left, top, right, bottom))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Align transparent pet frames onto a shared centered canvas."
    )
    parser.add_argument(
        "--in-dir",
        default="assets/pet_frames",
        help="Input directory containing frame_XX.png files.",
    )
    parser.add_argument(
        "--out-dir",
        default="assets/pet_frames_aligned",
        help="Output directory for aligned frame PNG files.",
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=18,
        help="Padding kept around each detected subject before alignment.",
    )
    parser.add_argument(
        "--alpha-threshold",
        type=int,
        default=12,
        help="Minimum alpha treated as visible subject.",
    )
    parser.add_argument(
        "--preview-out",
        default="assets/pet_frames_aligned_preview.png",
        help="Output path for a black-background contact sheet preview.",
    )
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    preview_out = Path(args.preview_out)
    frame_paths = sorted(in_dir.glob("frame_*.png"))

    if not frame_paths:
        raise FileNotFoundError(f"No frame_*.png files found in {in_dir}")

    cropped_frames: list[tuple[Path, Image.Image]] = []
    max_width = 0
    max_height = 0

    for path in frame_paths:
        image = Image.open(path).convert("RGBA")
        bbox = alpha_bbox(image, args.alpha_threshold)
        if bbox is None:
            raise ValueError(f"No visible pixels found in {path}")

        cropped = crop_to_subject(image, bbox, args.padding)
        cropped_frames.append((path, cropped))
        max_width = max(max_width, cropped.width)
        max_height = max(max_height, cropped.height)

    # Use even dimensions so scaling/subsampling in Tk remains visually stable.
    canvas_width = max_width + (max_width % 2)
    canvas_height = max_height + (max_height % 2)

    out_dir.mkdir(parents=True, exist_ok=True)

    aligned_frames: list[Image.Image] = []
    for path, cropped in cropped_frames:
        canvas = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 0))
        x = (canvas_width - cropped.width) // 2
        y = (canvas_height - cropped.height) // 2
        canvas.alpha_composite(cropped, (x, y))

        output_path = out_dir / path.name
        canvas.save(output_path)
        aligned_frames.append(canvas)

    cols = min(3, len(aligned_frames))
    rows = (len(aligned_frames) + cols - 1) // cols
    preview = Image.new("RGBA", (canvas_width * cols, canvas_height * rows), (0, 0, 0, 255))
    for index, frame in enumerate(aligned_frames):
        x = (index % cols) * canvas_width
        y = (index // cols) * canvas_height
        preview.alpha_composite(frame, (x, y))

    preview_out.parent.mkdir(parents=True, exist_ok=True)
    preview.save(preview_out)

    print(f"Aligned {len(aligned_frames)} frames")
    print(f"Canvas: {canvas_width}x{canvas_height}")
    print(f"Saved frames: {out_dir}")
    print(f"Saved preview: {preview_out}")


if __name__ == "__main__":
    main()
