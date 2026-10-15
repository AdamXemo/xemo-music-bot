"""Audio thumbnails that meet Telegram's rules, made from cover images (ADR 0006)."""

import asyncio
import logging
from io import BytesIO
from pathlib import Path
from typing import Final

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Bot API sendAudio: the thumbnail is a JPEG under 200 kB, at most 320 px a side. The
# decimal reading of "kB" is the safe one.
THUMBNAIL_SIDE: Final = 320
THUMBNAIL_MAX_BYTES: Final = 200_000

# Tried in order until the JPEG fits. A 320 px JPEG almost always fits at the first.
_QUALITIES: Final = (85, 70, 55, 40, 25)

# Sent when a track has no usable cover. It already meets the rules above, so a
# replacement image must too (tests check the file).
DEFAULT_COVER: Final = Path(__file__).resolve().parent.parent / "assets" / "default_cover.jpg"


class CoverError(Exception):
    """An image cannot be made into a thumbnail that fits Telegram's limit."""


def make_thumbnail(source: Path) -> bytes:
    """Turn an image file into a Telegram audio thumbnail. Blocks; run it in a thread.

    The image is centre-cropped to a square of at most ``THUMBNAIL_SIDE`` (smaller images
    are not scaled up), transparency is flattened onto white, and the JPEG is re-encoded
    at lower quality until it is under ``THUMBNAIL_MAX_BYTES``.

    Args:
        source: Any image file Pillow can read.

    Returns:
        The thumbnail as JPEG bytes.

    Raises:
        CoverError: If the JPEG is too large even at the lowest quality.
        Exception: Pillow's errors for unreadable, corrupt or oversized images
            (``DecompressionBombError``); they come in many types.
    """
    with Image.open(source) as image:
        rgb = _to_rgb(image)
    side = min(*rgb.size, THUMBNAIL_SIDE)
    square = ImageOps.fit(rgb, (side, side), Image.Resampling.LANCZOS)
    for quality in _QUALITIES:
        buffer = BytesIO()
        square.save(buffer, "JPEG", quality=quality, optimize=True)
        if buffer.tell() < THUMBNAIL_MAX_BYTES:
            return buffer.getvalue()
    raise CoverError(f"Thumbnail is over {THUMBNAIL_MAX_BYTES} bytes at quality {_QUALITIES[-1]}")


async def prepare_thumbnail(source: Path | None, directory: Path) -> Path:
    """Make the thumbnail for an audio, falling back to the default cover.

    Args:
        source: The cover image the provider fetched, or ``None`` if it got none.
        directory: The download's temporary directory; the thumbnail is written there,
            so it is removed together with the audio.

    Returns:
        The thumbnail: a file in ``directory``, or ``DEFAULT_COVER`` if ``source`` is
        missing or unusable. Never fails over a bad cover.
    """
    if source is None:
        return DEFAULT_COVER
    target = directory / "cover.jpg"
    try:
        # The thread only computes bytes; the write stays on the loop, so a cancelled
        # task cannot leave a thread writing into a directory cleanup already removed.
        data = await asyncio.to_thread(make_thumbnail, source)
        target.write_bytes(data)
    # Pillow raises OSError, ValueError, SyntaxError, DecompressionBombError and more on
    # bad input, and a cover must never fail a delivery.
    except Exception:
        logger.warning("Cover %s is unusable, using the default cover", source.name, exc_info=True)
        return DEFAULT_COVER
    return target


def _to_rgb(image: Image.Image) -> Image.Image:
    """Return ``image`` in RGB, JPEG's mode, with any transparency flattened onto white."""
    if not image.has_transparency_data:
        return image.convert("RGB")
    rgba = image.convert("RGBA")
    flat = Image.new("RGB", rgba.size, "white")
    flat.paste(rgba, mask=rgba)
    return flat
