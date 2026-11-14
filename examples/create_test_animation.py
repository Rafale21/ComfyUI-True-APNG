"""Regenerate the 3-second, 15 FPS test animation without ComfyUI."""

from fractions import Fraction
import math
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apng_encoder import write_apng, verify_apng


def test_frames():
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 17)
        small = ImageFont.truetype("DejaVuSans.ttf", 13)
    except OSError:
        font = small = ImageFont.load_default()
    for index in range(45):
        image = Image.new("RGB", (256, 256), (12, 15, 21))
        draw = ImageDraw.Draw(image)
        draw.text((16, 15), "TRUE APNG", font=font, fill=(238, 242, 250))
        draw.text((16, 41), "45 frames  /  15 FPS  /  3 s", font=small, fill=(155, 166, 185))
        draw.ellipse((53, 74, 203, 224), outline=(48, 59, 76), width=2)
        angle = 2 * math.pi * index / 45 - math.pi / 2
        x = 128 + 75 * math.cos(angle)
        y = 149 + 75 * math.sin(angle)
        draw.ellipse((x - 12, y - 12, x + 12, y + 12), fill=(255, 137, 36))
        draw.text((91, 139), f"{index + 1:02d} / 45", font=font, fill=(238, 242, 250))
        yield image


if __name__ == "__main__":
    path = Path(__file__).with_name("test_animation.apng")
    with path.open("wb") as stream:
        write_apng(stream, test_frames(), 45, 15)
    info = verify_apng(path, 45, 0, Fraction(1, 15))
    print(f"{path.name}: {info['frames']} images, {float(info['duration'])} s, 15 FPS")
