"""Contact sheets for Claude's review gates.

- reference sheet: evenly spaced frames (plus cut points) with timestamp labels  -> Gate 1
- image sheet: candidate images with #index and resolution labels                -> Gate 2
- compare sheet: reference vs generated frames side-by-side at equal timestamps  -> Gate 3
"""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from memegen.video.ffmpeg import extract_frame, probe

TILE_W = 480
LABEL_H = 34
BG = (18, 18, 18)
FG = (255, 255, 255)
ACCENT = (255, 214, 0)


def _font(size: int = 22) -> ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _fit(img: Image.Image, width: int) -> Image.Image:
    ratio = width / img.width
    return img.convert("RGB").resize((width, max(1, round(img.height * ratio))), Image.LANCZOS)


def grid(tiles: list[tuple[Image.Image, str]], cols: int, out: Path, title: str | None = None,
         tile_w: int = TILE_W) -> Path:
    """Lay out (image, label) tiles in a grid with a label bar above each tile."""
    if not tiles:
        raise ValueError("no tiles")
    fitted = [(_fit(img, tile_w), label) for img, label in tiles]
    cell_h = max(img.height for img, _ in fitted) + LABEL_H
    rows = math.ceil(len(fitted) / cols)
    title_h = 44 if title else 0
    sheet = Image.new("RGB", (cols * tile_w, rows * cell_h + title_h), BG)
    draw = ImageDraw.Draw(sheet)
    font = _font()
    if title:
        draw.text((12, 10), title, fill=ACCENT, font=_font(26))
    for i, (img, label) in enumerate(fitted):
        x, y = (i % cols) * tile_w, title_h + (i // cols) * cell_h
        draw.text((x + 8, y + 6), label, fill=FG, font=font)
        sheet.paste(img, (x, y + LABEL_H))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=88)
    return out


def sample_times(duration: float, n: int, cuts: list[float] | None = None) -> list[float]:
    """n evenly spaced timestamps; cut points replace their nearest sample so every shot is visible."""
    if duration <= 0 or n <= 0:
        return []
    step = duration / n
    times = [round(step * (i + 0.5), 3) for i in range(n)]
    for cut in cuts or []:
        t = min(cut + 0.1, duration - 0.05)
        nearest = min(range(len(times)), key=lambda i: abs(times[i] - t))
        times[nearest] = round(t, 3)
    return sorted(set(times))


def reference_sheet(video: Path, out: Path, n: int = 16, cols: int = 4, cuts: list[float] | None = None) -> Path:
    info = probe(video)
    times = sample_times(info.duration, n, cuts)
    cut_set = {round(c + 0.1, 3) for c in cuts or []}
    with tempfile.TemporaryDirectory() as tmp:
        tiles = []
        for i, t in enumerate(times):
            frame = extract_frame(video, t, Path(tmp) / f"{i:03d}.jpg", TILE_W)
            mark = "  CUT" if t in cut_set else ""
            tiles.append((Image.open(frame).copy(), f"#{i + 1}  t={t:.2f}s{mark}"))
    title = f"{Path(video).name}  {info.width}x{info.height}  {info.duration:.2f}s  {info.fps:g}fps"
    return grid(tiles, cols, out, title)


def image_sheet(paths: list[Path], out: Path, cols: int = 4, title: str | None = None) -> Path:
    tiles = []
    for i, path in enumerate(paths):
        img = Image.open(path)
        tiles.append((img.copy(), f"#{i + 1}  {img.width}x{img.height}  {Path(path).name[:22]}"))
    return grid(tiles, cols, out, title)


def compare_sheet(reference: Path, generated: Path, out: Path, n: int = 6) -> Path:
    """Rows of [reference | generated] frames at the same timestamps."""
    ref_info, gen_info = probe(reference), probe(generated)
    duration = min(ref_info.duration, gen_info.duration)
    times = sample_times(duration, n)
    with tempfile.TemporaryDirectory() as tmp:
        tiles = []
        for i, t in enumerate(times):
            ref = extract_frame(reference, t, Path(tmp) / f"r{i}.jpg", TILE_W)
            gen = extract_frame(generated, t, Path(tmp) / f"g{i}.jpg", TILE_W)
            tiles.append((Image.open(ref).copy(), f"REF  t={t:.2f}s"))
            tiles.append((Image.open(gen).copy(), f"OUT  t={t:.2f}s"))
    title = (f"REF {ref_info.duration:.2f}s {ref_info.width}x{ref_info.height}  vs  "
             f"OUT {gen_info.duration:.2f}s {gen_info.width}x{gen_info.height}")
    return grid(tiles, 2, out, title)
