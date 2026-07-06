"""Style: mathart — procedurally generated mathematical art, no image source.

The picture area is computed, not fetched: one of five generators, rotated
deterministically by date (all cron ticks of a day show the same piece, and
both panels agree):

  julia         escape-time Julia set, curated c values
  mandelbrot    escape-time Mandelbrot, curated interesting windows
  newton        z^3 - 1 Newton basins with convergence shading
  dejong        Peter de Jong strange attractor, density point cloud
  harmonograph  damped Lissajous pendulum curves

Escape-time fields are posterised into hard colour bands — flat pure inks are
what e-paper renders best, so no dithering is needed: B/W gets classic contour
stripes, the E6 cycles its palette. The bottom bar names the piece and its
actual parameters.
"""

from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw

from .. import config
from ..draw import Canvas

BAR = 64


# ── shared helpers ────────────────────────────────────────────────────────────
def _grid(w: int, h: int, cx: float, cy: float, span: float) -> np.ndarray:
    """Complex-plane grid; `span` is the height of the window, width follows AR."""
    ar = w / h
    x = np.linspace(cx - span * ar / 2, cx + span * ar / 2, w)
    y = np.linspace(cy - span / 2, cy + span / 2, h)
    X, Y = np.meshgrid(x, y)
    return X + 1j * Y


def _escape_field(z: np.ndarray, c, it: int = 140) -> tuple[np.ndarray, np.ndarray]:
    """Smooth escape-time field in [0,1] + interior mask (never escaped)."""
    out = np.zeros(z.shape)
    alive = np.ones(z.shape, bool)
    for i in range(it):
        z2 = z[alive] ** 2 + (c[alive] if isinstance(c, np.ndarray) else c)
        z[alive] = z2
        esc = np.zeros(z.shape, bool)
        esc[alive] = np.abs(z2) > 4.0
        mag = np.abs(z[esc])
        out[esc] = i + 1 - np.log2(np.maximum(np.log(np.maximum(mag, 1.001)), 1e-9))
        alive &= ~esc
    out = np.maximum(out, 0.0)  # far-outside pixels can go slightly negative
    mx = out.max()
    return (out / mx if mx > 0 else out), alive


def _band_image(panel, field: np.ndarray, interior: np.ndarray, freq: float) -> Image.Image:
    """Posterise a [0,1] field into hard ink bands (interior stays black)."""
    names = ["white", "yellow", "green", "blue", "red"] if panel.is_color else ["white", "black"]
    cols = np.array([panel.color(n) for n in names], dtype=np.uint8)
    idx = np.floor(field * freq).astype(int) % len(cols)
    px = cols[idx]
    px[interior] = panel.color("black")
    return Image.fromarray(px, "RGB")


# ── generators: (panel, w, h, rng) -> (RGB image, title, ascii caption) ───────
JULIA_CS = [-0.79 + 0.15j, -0.4 + 0.6j, 0.285 + 0.01j,
            -0.835 - 0.2321j, -0.70176 - 0.3842j, -0.8 + 0.156j]


def _julia(panel, w, h, rng):
    c = rng.choice(JULIA_CS)
    field, interior = _escape_field(_grid(w, h, 0.0, 0.0, 2.6), c)
    # compress the field before banding: escape values pile up near the set
    # boundary, and linear bands there turn into 1px confetti — the worst
    # texture for e-paper. Power-law scaling widens the near-set bands.
    cap = f"z <- z^2 + c   c = {c.real:+.3f} {c.imag:+.4f}i"
    return _band_image(panel, field ** 0.35, interior, freq=5), "JULIA SET", cap


MANDEL_VIEWS = [(-0.75, 0.0, 2.4), (-0.7436, 0.1318, 0.05),
                (-0.1607, 1.0376, 0.06), (-1.25275, -0.3434, 0.04)]


def _mandelbrot(panel, w, h, rng):
    cx, cy, span = rng.choice(MANDEL_VIEWS)
    grid = _grid(w, h, cx, cy, span)
    field, interior = _escape_field(np.zeros_like(grid), grid)
    cap = f"c = ({cx:+.4f}, {cy:+.4f})   span {span:g}"
    return _band_image(panel, field ** 0.35, interior, freq=6), "MANDELBROT", cap


def _newton(panel, w, h, rng):
    Z = _grid(w, h, 0.0, 0.0, 3.0)
    roots = np.array([1.0 + 0j, -0.5 + 0.8660254j, -0.5 - 0.8660254j])
    iters = np.full(Z.shape, 39, dtype=int)
    done = np.zeros(Z.shape, bool)
    for i in range(40):
        Z = Z - (Z ** 3 - 1) / (3 * Z ** 2 + 1e-12)
        conv = ~done & (np.min(np.abs(Z[..., None] - roots), axis=-1) < 1e-4)
        iters[conv] = i
        done |= conv
    basin = np.argmin(np.abs(Z[..., None] - roots), axis=-1)
    if panel.is_color:
        cols = np.array([panel.color(n) for n in ("red", "blue", "yellow")], dtype=np.uint8)
        px = cols[basin]
        px[iters >= 18] = panel.color("black")   # slow-converging fringes → black filigree
        px[iters <= 4] = panel.color("white")    # calm root cores → paper
    else:
        # marble the three basins with convergence-contour parity
        cols = np.array([panel.color("white"), panel.color("black")], dtype=np.uint8)
        px = cols[(basin + iters) % 2]
    return Image.fromarray(px, "RGB"), "NEWTON FRACTAL", "z <- z - (z^3 - 1)/(3z^2)"


DEJONG_PARAMS = [(-2.7, -0.09, -0.86, -2.2), (-2.24, 0.43, -0.65, -2.43),
                 (1.4, -2.3, 2.4, -2.1), (-2.0, -2.0, -1.2, 2.0)]


def _dejong(panel, w, h, rng):
    a, b, c, d = rng.choice(DEJONG_PARAMS)
    H = np.zeros((h, w))
    x = y = 0.0
    sx, sy = (w - 1) / 4.4, (h - 1) / 4.4
    for _ in range(140_000):
        x, y = math.sin(a * y) - math.cos(b * x), math.sin(c * x) - math.cos(d * y)
        H[int((y + 2.2) * sy), int((x + 2.2) * sx)] += 1
    dens = np.log1p(H)
    dens /= max(dens.max(), 1e-9)
    px = np.full((h, w, 3), panel.color("white"), dtype=np.uint8)
    px[dens > 0.10] = panel.color("black")
    if panel.is_color:
        px[dens > 0.55] = panel.color("red")     # hottest orbits glow red
    cap = f"a={a:g} b={b:g} c={c:g} d={d:g}"
    return Image.fromarray(px, "RGB"), "DE JONG ATTRACTOR", cap


def _harmonograph(panel, w, h, rng):
    S = 3  # draw supersampled, downscale for smooth strokes
    img = Image.new("RGB", (w * S, h * S), panel.color("white"))
    d = ImageDraw.Draw(img)
    fx, fy = rng.choice([(2, 3), (3, 4), (3, 5), (5, 6), (4, 7)])
    # red underlay first, black structure on top
    curves = [("red" if panel.is_color else "black", math.pi / 5), ("black", 0.0)]
    for col, detune in curves:
        p1, p2 = rng.uniform(0, math.pi), rng.uniform(0, math.pi)
        pts = []
        for i in range(14_000):
            t = i * 0.012
            damp = math.exp(-0.004 * t)
            x = math.sin(fx * t + p1 + detune) * damp
            y = math.sin(fy * t + p2) * damp
            pts.append((w * S / 2 + x * w * S * 0.44, h * S / 2 + y * h * S * 0.44))
        d.line(pts, fill=panel.color(col), width=S)
    art = img.resize((w, h), Image.LANCZOS)
    return art, "HARMONOGRAPH", f"x=sin({fx}t+p)e^-dt  y=sin({fy}t+q)e^-dt"


GENERATORS = [_julia, _mandelbrot, _newton, _dejong, _harmonograph]


def render(panel, ctx):
    day = ctx.now.toordinal()
    rng = random.Random(day)                     # stable within a day
    gen = GENERATORS[day % len(GENERATORS)]
    art, title, cap = gen(panel, panel.W, panel.H - BAR, rng)

    c = Canvas(panel, ss=1)
    c.paste(art, 0, 0)

    y0 = panel.H - BAR
    c.rect(0, y0, panel.W, BAR, fill="black")
    now = ctx.now
    dstr = now.strftime("%m·%d")
    df = c.doto(34)
    c.text(20, y0 + BAR / 2, dstr, df, fill="white", anchor="lm")
    hi = "yellow" if panel.is_color else "white"
    x = 24 + c.tw(dstr, df) + 14
    c.text(x, y0 + BAR / 2, config.EN_WD[now.isoweekday() - 1], c.mono(13, bold=True),
           fill=hi, anchor="lm")
    x += c.tw(config.EN_WD[now.isoweekday() - 1], c.mono(13, bold=True)) + 18
    c.dot(x, y0 + BAR / 2, 3, "red" if panel.is_color else "white")
    c.text(x + 12, y0 + BAR / 2, title, c.mono(13, bold=True), fill="white", anchor="lm")

    capf = c.mono(13)
    c.text(panel.W - 20, y0 + BAR / 2, c.ellipsize(capf, cap, 330), capf,
           fill="white", anchor="rm")
    return c.finish()
