"""Draw the placeholder default cover: a dark square with the bot's name.

Run once, then commit the image: ``uv run python scripts/make_default_cover.py``.
The bot only reads the file; an image the owner provides can replace it, as long as it
stays a JPEG of at most 320x320 px under 200 kB (``tests/providers/test_covers.py``).
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIDE = 320
BACKGROUND = "#16161d"
TEXT = "#e8e8ee"
NAME = "xemo music"
TARGET = Path(__file__).resolve().parent.parent / "src/xemo_music_bot/assets/default_cover.jpg"


def main() -> None:
    """Write the default cover to ``TARGET``."""
    image = Image.new("RGB", (SIDE, SIDE), BACKGROUND)
    # Pillow's bundled font, so the result does not depend on the fonts installed.
    font = ImageFont.load_default(size=40)
    ImageDraw.Draw(image).text((SIDE / 2, SIDE / 2), NAME, fill=TEXT, font=font, anchor="mm")
    image.save(TARGET, "JPEG", quality=90, optimize=True)


if __name__ == "__main__":
    main()
