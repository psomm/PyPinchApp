"""Generate the simple PyPinch app icon with Pillow."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
DESTINATION = Path(__file__).resolve().parents[1] / "src" / "assets" / "icon.png"


def curve(points: tuple[tuple[int, int], ...]) -> list[tuple[int, int]]:
    """Sample a smooth cubic through four control points."""
    result = []
    for step in range(101):
        t = step / 100
        x = sum(
            (1 - t) ** (3 - index) * t**index * (1, 3, 3, 1)[index] * point[0]
            for index, point in enumerate(points)
        )
        y = sum(
            (1 - t) ** (3 - index) * t**index * (1, 3, 3, 1)[index] * point[1]
            for index, point in enumerate(points)
        )
        result.append((round(x), round(y)))
    return result


def main() -> None:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((100, 100, 924, 924), radius=205, fill="#0f766e")
    draw.line([(247, 751), (247, 275)], fill="#ffffff", width=30)
    draw.line([(231, 750), (790, 750)], fill="#ffffff", width=30)
    hot = curve(((300, 642), (450, 525), (620, 425), (758, 256)))
    cold = curve(((335, 707), (478, 599), (612, 552), (793, 392)))
    draw.line(hot, fill="#ffb36b", width=75, joint="curve")
    draw.line(cold, fill="#8fd8ff", width=75, joint="curve")
    for x, y in (hot[0], hot[-1]):
        draw.ellipse((x - 37, y - 37, x + 37, y + 37), fill="#ffb36b")
    for x, y in (cold[0], cold[-1]):
        draw.ellipse((x - 37, y - 37, x + 37, y + 37), fill="#8fd8ff")
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    image.save(DESTINATION)


if __name__ == "__main__":
    main()
