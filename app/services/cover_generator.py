import io
import math
import random

from PIL import Image, ImageDraw, ImageFilter

_SIZE = 512
_BG = (10, 10, 10)
DrawContext = ImageDraw.ImageDraw


def generate_cover(seed: str) -> bytes:
    rng = random.Random(seed)
    style = rng.randint(0, 3)
    img = Image.new("RGB", (_SIZE, _SIZE), _BG)
    draw = ImageDraw.Draw(img)

    generators = [
        _draw_geometric,
        _draw_waves,
        _draw_gradient_mesh,
        _draw_dots_grid,
    ]
    generators[style](img, draw, rng)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _gray(rng: random.Random, lo: int = 40, hi: int = 255) -> tuple[int, int, int]:
    v = rng.randint(lo, hi)
    return (v, v, v)


def _draw_geometric(
    img: Image.Image,
    draw: DrawContext,
    rng: random.Random,
) -> None:
    for _ in range(rng.randint(3, 8)):
        cx = rng.randint(0, _SIZE)
        cy = rng.randint(0, _SIZE)
        r = rng.randint(40, 220)
        color = _gray(rng, 20, 80)
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=color,
            width=rng.randint(1, 3),
        )

    for _ in range(rng.randint(5, 15)):
        x1 = rng.randint(-50, _SIZE + 50)
        y1 = rng.randint(-50, _SIZE + 50)
        x2 = rng.randint(-50, _SIZE + 50)
        y2 = rng.randint(-50, _SIZE + 50)
        color = _gray(rng, 60, 200)
        draw.line(
            [x1, y1, x2, y2],
            fill=color,
            width=rng.randint(1, 2),
        )

    grid_step = rng.randint(40, 100)
    grid_color = _gray(rng, 15, 35)
    for x in range(0, _SIZE, grid_step):
        draw.line(
            [x, 0, x, _SIZE], fill=grid_color, width=1
        )
    for y in range(0, _SIZE, grid_step):
        draw.line(
            [0, y, _SIZE, y], fill=grid_color, width=1
        )

    for _ in range(rng.randint(1, 4)):
        cx = rng.randint(100, _SIZE - 100)
        cy = rng.randint(100, _SIZE - 100)
        r = rng.randint(20, 60)
        color = _gray(rng, 180, 255)
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=color,
        )


def _draw_waves(
    img: Image.Image,
    draw: DrawContext,
    rng: random.Random,
) -> None:
    num_waves = rng.randint(5, 12)
    for w in range(num_waves):
        amplitude = rng.randint(20, 100)
        frequency = rng.uniform(0.005, 0.025)
        phase = rng.uniform(0, math.tau)
        y_base = int(
            _SIZE * (w + 1) / (num_waves + 1)
        )
        brightness = int(
            40 + (215 * (w / max(num_waves - 1, 1)))
        )
        color = (brightness, brightness, brightness)
        width = rng.randint(1, 3)

        points = []
        for x in range(_SIZE):
            y = y_base + int(
                amplitude
                * math.sin(frequency * x + phase)
            )
            points.append((x, y))

        if len(points) > 1:
            draw.line(points, fill=color, width=width)

    for _ in range(rng.randint(0, 3)):
        cx = rng.randint(0, _SIZE)
        cy = rng.randint(0, _SIZE)
        r = rng.randint(2, 6)
        color = _gray(rng, 200, 255)
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=color,
        )


def _draw_gradient_mesh(
    img: Image.Image,
    draw: DrawContext,
    rng: random.Random,
) -> None:
    overlay = Image.new("RGB", (_SIZE, _SIZE), _BG)
    overlay_draw = ImageDraw.Draw(overlay)

    num_blobs = rng.randint(3, 7)
    for _ in range(num_blobs):
        cx = rng.randint(-100, _SIZE + 100)
        cy = rng.randint(-100, _SIZE + 100)
        r = rng.randint(100, 300)
        brightness = rng.randint(30, 120)
        color = (brightness, brightness, brightness)
        overlay_draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=color,
        )

    overlay = overlay.filter(
        ImageFilter.GaussianBlur(radius=80)
    )
    img.paste(overlay)

    draw = ImageDraw.Draw(img)
    for _ in range(rng.randint(2, 6)):
        x1 = rng.randint(0, _SIZE)
        y1 = rng.randint(0, _SIZE)
        x2 = rng.randint(0, _SIZE)
        y2 = rng.randint(0, _SIZE)
        color = _gray(rng, 150, 255)
        draw.line(
            [x1, y1, x2, y2], fill=color, width=1
        )


def _draw_dots_grid(
    img: Image.Image,
    draw: DrawContext,
    rng: random.Random,
) -> None:
    step = rng.randint(16, 32)
    max_radius = step // 2 - 2
    wave_freq = rng.uniform(0.008, 0.02)
    wave_phase_x = rng.uniform(0, math.tau)
    wave_phase_y = rng.uniform(0, math.tau)

    for gx in range(step // 2, _SIZE, step):
        for gy in range(step // 2, _SIZE, step):
            dist_factor = (
                math.sin(wave_freq * gx + wave_phase_x)
                * math.cos(wave_freq * gy + wave_phase_y)
                + 1
            ) / 2

            r = max(1, int(max_radius * dist_factor))
            brightness = int(40 + 215 * dist_factor)
            color = (brightness, brightness, brightness)

            draw.ellipse(
                [gx - r, gy - r, gx + r, gy + r],
                fill=color,
            )

    for _ in range(rng.randint(1, 3)):
        x = rng.randint(0, _SIZE)
        color = _gray(rng, 20, 40)
        draw.line(
            [x, 0, x, _SIZE], fill=color, width=1
        )
