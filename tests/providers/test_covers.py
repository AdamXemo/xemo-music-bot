import asyncio
import os
import threading
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from xemo_music_bot.providers import covers
from xemo_music_bot.providers.covers import (
    DEFAULT_COVER,
    THUMBNAIL_MAX_BYTES,
    CoverError,
    make_thumbnail,
    prepare_thumbnail,
)


def save(image: Image.Image, path: Path, image_format: str = "PNG") -> Path:
    image.save(path, image_format)
    return path


def noise(width: int, height: int) -> Image.Image:
    """Random pixels: the worst case for JPEG size."""
    return Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))


def opened(data: bytes) -> Image.Image:
    image = Image.open(BytesIO(data))
    image.load()
    return image


def test_thumbnail_is_a_centre_cropped_320_px_jpeg(tmp_path: Path) -> None:
    # Red bands on the left and right, green in the middle square.
    image = Image.new("RGB", (1000, 600), "red")
    image.paste(Image.new("RGB", (600, 600), "lime"), (200, 0))

    thumbnail = opened(make_thumbnail(save(image, tmp_path / "wide.png")))

    assert (thumbnail.format, thumbnail.mode, thumbnail.size) == ("JPEG", "RGB", (320, 320))
    for corner in [(0, 0), (319, 0), (0, 319), (319, 319)]:
        pixel = thumbnail.getpixel(corner)
        assert isinstance(pixel, tuple)
        red, green, _ = pixel
        assert green > 200 and red < 60, corner


def test_thumbnail_does_not_scale_up_a_small_image(tmp_path: Path) -> None:
    source = save(Image.new("RGB", (100, 80), "blue"), tmp_path / "small.png")

    assert opened(make_thumbnail(source)).size == (80, 80)


def test_thumbnail_of_a_huge_noisy_image_fits_the_limit(tmp_path: Path) -> None:
    source = save(noise(3000, 3000), tmp_path / "noise.png")

    data = make_thumbnail(source)

    assert len(data) < THUMBNAIL_MAX_BYTES
    assert opened(data).size == (320, 320)


def test_thumbnail_lowers_quality_until_it_fits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = save(noise(320, 320), tmp_path / "noise.png")
    first_try = make_thumbnail(source)
    monkeypatch.setattr(covers, "THUMBNAIL_MAX_BYTES", len(first_try))

    data = make_thumbnail(source)

    assert len(data) < len(first_try)
    assert opened(data).size == (320, 320)


def test_thumbnail_fails_when_even_the_lowest_quality_is_too_large(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(covers, "THUMBNAIL_MAX_BYTES", 100)

    with pytest.raises(CoverError):
        make_thumbnail(save(noise(320, 320), tmp_path / "noise.png"))


@pytest.mark.parametrize(
    ("mode", "image_format"),
    [
        pytest.param("RGBA", "PNG", id="rgba"),
        pytest.param("LA", "PNG", id="grey-alpha"),
        pytest.param("P", "PNG", id="palette"),
        pytest.param("L", "PNG", id="grey"),
        pytest.param("1", "PNG", id="black-white"),
        pytest.param("I;16", "PNG", id="16-bit-grey"),
        pytest.param("CMYK", "JPEG", id="cmyk"),
    ],
)
def test_thumbnail_is_rgb_whatever_the_source_mode(
    tmp_path: Path, mode: str, image_format: str
) -> None:
    source = save(Image.new(mode, (50, 50)), tmp_path / f"image.{image_format}", image_format)

    assert opened(make_thumbnail(source)).mode == "RGB"


def test_thumbnail_flattens_transparency_onto_white(tmp_path: Path) -> None:
    source = save(Image.new("RGBA", (50, 50), (0, 0, 0, 0)), tmp_path / "clear.png")

    pixel = opened(make_thumbnail(source)).getpixel((25, 25))

    assert isinstance(pixel, tuple)
    assert all(channel > 245 for channel in pixel)


async def test_prepare_writes_the_thumbnail_into_the_download_dir(tmp_path: Path) -> None:
    source = save(Image.new("RGB", (500, 500), "blue"), tmp_path / "123.jpg", "JPEG")

    thumbnail = await prepare_thumbnail(source, tmp_path)

    assert thumbnail.parent == tmp_path
    assert thumbnail != source
    assert opened(thumbnail.read_bytes()).size == (320, 320)


async def test_prepare_uses_the_default_cover_when_there_is_no_cover(tmp_path: Path) -> None:
    assert await prepare_thumbnail(None, tmp_path) == DEFAULT_COVER


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"<html>not found</html>", id="not-an-image"),
        pytest.param(b"", id="empty"),
    ],
)
async def test_prepare_uses_the_default_cover_for_an_unreadable_cover(
    tmp_path: Path, content: bytes
) -> None:
    source = tmp_path / "123.jpg"
    source.write_bytes(content)

    assert await prepare_thumbnail(source, tmp_path) == DEFAULT_COVER


async def test_prepare_uses_the_default_cover_for_a_truncated_cover(tmp_path: Path) -> None:
    source = save(noise(200, 200), tmp_path / "123.jpg", "JPEG")
    source.write_bytes(source.read_bytes()[:2000])

    assert await prepare_thumbnail(source, tmp_path) == DEFAULT_COVER


async def test_prepare_uses_the_default_cover_for_a_decompression_bomb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = save(Image.new("RGB", (100, 100)), tmp_path / "123.png")
    # Pillow refuses images over twice this many pixels with DecompressionBombError.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)

    assert await prepare_thumbnail(source, tmp_path) == DEFAULT_COVER


def test_default_cover_meets_telegram_thumbnail_rules() -> None:
    with Image.open(DEFAULT_COVER) as cover:
        assert cover.format == "JPEG"
        assert cover.width <= 320 and cover.height <= 320
    assert DEFAULT_COVER.stat().st_size < THUMBNAIL_MAX_BYTES


async def test_prepare_writes_nothing_when_cancelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = threading.Event()
    release = threading.Event()

    def slow_thumbnail(_source: Path) -> bytes:
        started.set()
        release.wait(5)
        return b"jpeg"

    monkeypatch.setattr(covers, "make_thumbnail", slow_thumbnail)
    source = save(Image.new("RGB", (10, 10)), tmp_path / "1.png")
    task = asyncio.create_task(prepare_thumbnail(source, tmp_path))
    await asyncio.to_thread(started.wait, 5)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()
    await asyncio.sleep(0.05)

    assert not (tmp_path / "cover.jpg").exists()
