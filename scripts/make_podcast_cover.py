"""Generate the podcast cover art for ai-learn.

One-shot helper, not part of the build pipeline. Writes a 1400x1400 PNG to
static/podcast-cover.png which is then copied into dist/ by the regular build.

Requires Pillow:
    pip install pillow

Run:
    python scripts/make_podcast_cover.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "static" / "podcast-cover.png"

SIZE = 1400
BG = (3, 7, 18)              # gray-950
FG = (243, 244, 246)         # gray-100
ACCENT = (107, 114, 128)     # gray-500
TEXT = "{ai-learn}"
SUBTITLE = "Tim Jones · Claude · Kokoro"

FONT_CANDIDATES = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
    "/System/Library/Fonts/Courier.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def main() -> None:
    img = Image.new("RGB", (SIZE, SIZE), BG)
    draw = ImageDraw.Draw(img)

    title_font = load_font(220)
    subtitle_font = load_font(48)

    title_bbox = draw.textbbox((0, 0), TEXT, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    title_h = title_bbox[3] - title_bbox[1]
    title_x = (SIZE - title_w) / 2 - title_bbox[0]
    title_y = (SIZE - title_h) / 2 - title_bbox[1] - 40
    draw.text((title_x, title_y), TEXT, font=title_font, fill=FG)

    sub_bbox = draw.textbbox((0, 0), SUBTITLE, font=subtitle_font)
    sub_w = sub_bbox[2] - sub_bbox[0]
    sub_x = (SIZE - sub_w) / 2 - sub_bbox[0]
    sub_y = title_y + title_h + 80
    draw.text((sub_x, sub_y), SUBTITLE, font=subtitle_font, fill=ACCENT)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT_PATH, format="PNG", optimize=True)
    print(f"wrote {OUT_PATH} ({SIZE}x{SIZE})")


if __name__ == "__main__":
    main()
