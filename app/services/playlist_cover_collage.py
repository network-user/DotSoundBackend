from __future__ import annotations

import io
from collections.abc import Sequence

from PIL import Image

_EDGE = 512
_PLACEHOLDER_RGB = (43, 43, 48)


def build_playlist_cover_collage_webp(
    cell_images: Sequence[bytes | None],
    *,
    grid_side: int,
) -> bytes:
    n = grid_side * grid_side
    if len(cell_images) != n:
        msg = "cell_images must match grid_side ** 2"
        raise ValueError(msg)
    cell = max(1, _EDGE // grid_side)
    side_px = cell * grid_side
    canvas = Image.new("RGB", (side_px, side_px), _PLACEHOLDER_RGB)
    for idx in range(n):
        row, col = divmod(idx, grid_side)
        x0 = col * cell
        y0 = row * cell
        tile = Image.new("RGB", (cell, cell), _PLACEHOLDER_RGB)
        raw = cell_images[idx]
        if raw:
            try:
                im = Image.open(io.BytesIO(raw))
                rgb = im.convert("RGB")
                rgb = rgb.resize(
                    (cell, cell),
                    Image.Resampling.LANCZOS,
                )
                tile = rgb
            except Exception:
                pass
        canvas.paste(tile, (x0, y0))
    out_img = canvas
    if side_px != _EDGE:
        out_img = canvas.resize(
            (_EDGE, _EDGE),
            Image.Resampling.LANCZOS,
        )
    buf = io.BytesIO()
    out_img.save(buf, format="WEBP", quality=82)
    return buf.getvalue()
