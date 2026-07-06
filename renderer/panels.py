"""Panel abstraction — one style codebase drives both a 1-bit B/W panel and a
six-colour Spectra 6 (E6) panel.

A style draws with *semantic* colours ("black", "red", "green", "blue",
"yellow", "white"). Each panel maps those to what it can physically show:

  BWPanel  — every ink colour collapses to black; photos are Floyd–Steinberg
             dithered; the final image is thresholded to mode "1". Supports the
             pre-invert dance needed when the panel firmware inverts the PNG.
  E6Panel  — inks map to the six pure RGB values that land cleanly in the
             ESPHome epaper_spi color_to_hex() buckets; photos are error-
             diffusion dithered to that 6-colour palette; finalize() quantises
             every pixel exactly like the device driver, and also emits a
             muted "what the paper really looks like" preview PNG.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

from . import config

ASSETS = Path(__file__).resolve().parent / "assets"

# Six-colour source palette: pure RGB the device must RECEIVE (each lands in the
# right color_to_hex bucket), and the muted RGB the physical panel SHOWS.
E6_INK = {
    "black":  (0, 0, 0),
    "white":  (255, 255, 255),
    "red":    (200, 0, 0),
    "green":  (0, 140, 0),
    "blue":   (0, 60, 190),
    "yellow": (235, 200, 0),
}
E6_PANEL_RGB = {
    "black":  (28, 28, 28),
    "white":  (244, 242, 236),
    "red":    (176, 42, 40),
    "green":  (58, 122, 74),
    "blue":   (46, 66, 150),
    "yellow": (222, 190, 60),
}


# ── ordered dithering (EINK_DITHER=bayer|bluenoise; fs = error diffusion) ────
_BAYER8 = np.array([
    [0, 32, 8, 40, 2, 34, 10, 42],
    [48, 16, 56, 24, 50, 18, 58, 26],
    [12, 44, 4, 36, 14, 46, 6, 38],
    [60, 28, 52, 20, 62, 30, 54, 22],
    [3, 35, 11, 43, 1, 33, 9, 41],
    [51, 19, 59, 27, 49, 17, 57, 25],
    [15, 47, 7, 39, 13, 45, 5, 37],
    [63, 31, 55, 23, 61, 29, 53, 21],
])


def _threshold_map(size: tuple[int, int]) -> np.ndarray | None:
    """Tiled 0..255 threshold matrix for the configured ordered mode, or None
    for error diffusion (fs)."""
    mode = config.DITHER
    if mode == "bayer":
        base = ((_BAYER8 + 0.5) * 4).astype(np.uint8)          # 0..255
    elif mode == "bluenoise":
        base = np.asarray(Image.open(ASSETS / "bluenoise64.png"))
    else:
        return None
    w, h = size
    reps = (h // base.shape[0] + 1, w // base.shape[1] + 1)
    return np.tile(base, reps)[:h, :w]


def _quantize_e6(img: Image.Image, palette: dict) -> Image.Image:
    """Mirror ESPHome epaper_spi color_to_hex() exactly, pixel by pixel."""
    GRAY_THRESHOLD = 50
    px = img.load()
    out = Image.new("RGB", img.size)
    opx = out.load()
    cache: dict[tuple, tuple] = {}
    for y in range(img.height):
        for x in range(img.width):
            c = px[x, y]
            mapped = cache.get(c)
            if mapped is None:
                r, g, b = c[0], c[1], c[2]
                mx, mn = max(r, g, b), min(r, g, b)
                if (mx - mn) < GRAY_THRESHOLD:
                    bucket = "white" if (r + g + b) > 382 else "black"
                else:
                    r_on, g_on, b_on = r > 128, g > 128, b > 128
                    if r_on and g_on and not b_on:
                        bucket = "yellow"
                    elif r_on and not g_on and not b_on:
                        bucket = "red"
                    elif not r_on and g_on and not b_on:
                        bucket = "green"
                    elif not r_on and not g_on and b_on:
                        bucket = "blue"
                    elif not r_on and g_on and b_on:
                        bucket = "green"       # cyan → green
                    elif r_on and not g_on:
                        bucket = "red"         # magenta → red
                    elif r_on:
                        bucket = "white"
                    else:
                        bucket = "black"
                mapped = palette[bucket]
                cache[c] = mapped
            opx[x, y] = mapped
    return out


class Panel:
    """Base: 800x480. Subclasses define colour mapping, photo prep, finalize."""

    name: str
    remote_png: str        # filename under /config/www/eink/ (→ /local/eink/...)
    default_ss: int        # supersample factor for vector/text styles
    is_color: bool

    W, H = config.W, config.H

    def color(self, name: str) -> tuple[int, int, int]:
        raise NotImplementedError

    def prepare_photo(self, img: Image.Image, size: tuple[int, int] | None = None) -> Image.Image:
        """Center-fit a photo to `size` and dither it into this panel's gamut.
        Returns RGB whose pixels are already exact panel colours — composite it
        onto a canvas at ss=1 only (downscaling would destroy the dither)."""
        raise NotImplementedError

    def export(self, img: Image.Image, out: Path) -> list[Path]:
        """Write the device PNG (and a human preview when they differ)."""
        raise NotImplementedError


class BWPanel(Panel):
    name = "bw"
    remote_png = "dashboard.png"
    default_ss = 1          # Doto dot-matrix digits are crispest at native res
    is_color = False

    def __init__(self) -> None:
        # The TRMNL firmware displays the PNG inverted → pre-invert the device copy.
        self.invert = os.getenv("EINK_INVERT") == "1"

    def color(self, name: str) -> tuple[int, int, int]:
        return (255, 255, 255) if name == "white" else (0, 0, 0)

    def prepare_photo(self, img, size=None):
        size = size or (self.W, self.H)
        im = ImageOps.fit(img.convert("RGB"), size, Image.LANCZOS)
        g = ImageOps.autocontrast(im.convert("L"), cutoff=1)
        g = ImageEnhance.Contrast(g).enhance(1.12)
        t = _threshold_map(g.size)
        if t is None:  # fs
            return g.convert("1", dither=Image.FLOYDSTEINBERG).convert("RGB")
        out = (np.asarray(g) > t).astype(np.uint8) * 255
        return Image.fromarray(out, "L").convert("RGB")

    def export(self, img, out):
        out.parent.mkdir(parents=True, exist_ok=True)
        # Threshold, not dither: photo regions are pre-dithered to pure 0/255,
        # and antialiased text edges snap cleanly at 128.
        one = img.convert("L").point(lambda p: 255 if p >= 128 else 0)
        device = one.point(lambda p: 255 - p) if self.invert else one
        device.convert("1").save(out)
        paths = [out]
        if self.invert:  # preview = what the panel shows after its own invert
            pv = out.with_name(out.stem + "_preview.png")
            one.convert("1").save(pv)
            paths.append(pv)
        return paths


class E6Panel(Panel):
    name = "e6"
    remote_png = "dashboard_e6.png"
    # 1, not 2: small CJK now uses pixel fonts, which must land on the final
    # pixel grid — supersampling + downscale is what made them look blurry.
    default_ss = 1
    is_color = True

    def color(self, name: str) -> tuple[int, int, int]:
        return E6_INK[name]

    def prepare_photo(self, img, size=None):
        size = size or (self.W, self.H)
        im = ImageOps.fit(img.convert("RGB"), size, Image.LANCZOS)
        im = ImageEnhance.Color(im).enhance(1.25)      # fight the muted paper
        im = ImageEnhance.Contrast(im).enhance(1.08)
        pal = Image.new("P", (1, 1))
        flat = [v for c in E6_INK.values() for v in c]
        pal.putpalette(flat + flat[:3] * (256 - len(E6_INK)))
        t = _threshold_map(im.size)
        if t is None:  # fs
            return im.quantize(palette=pal, dither=Image.FLOYDSTEINBERG).convert("RGB")
        # ordered dithering to a palette: bias each pixel by the threshold map
        # (spread ≈ typical palette quantisation step), then snap to nearest ink
        arr = np.asarray(im).astype(np.float32) + (t[..., None] / 255.0 - 0.5) * 84
        biased = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGB")
        return biased.quantize(palette=pal, dither=Image.Dither.NONE).convert("RGB")

    def export(self, img, out):
        out.parent.mkdir(parents=True, exist_ok=True)
        _quantize_e6(img, E6_INK).save(out)
        pv = out.with_name(out.stem + "_preview.png")
        _quantize_e6(img, E6_PANEL_RGB).save(pv)
        return [out, pv]


PANELS = {"bw": BWPanel, "e6": E6Panel}


def get_panel(name: str) -> Panel:
    return PANELS[name]()
