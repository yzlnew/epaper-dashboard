"""Canvas + drawing primitives shared by all styles.

All primitives take FINAL-pixel coordinates; the canvas supersamples internally
(ss from the panel, or overridden by the style — photo styles must use ss=1 so
pasted pre-dithered pixels survive untouched).

Colours are semantic names ("black", "red", …) resolved via the panel, so the
same style renders on both the 1-bit and the six-colour panel.
"""

from __future__ import annotations

import math
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFont

from . import config
from .panels import Panel

DOTO = "Doto.ttf"
MONO = "SpaceMono-Regular.ttf"
MONOB = "SpaceMono-Bold.ttf"
SANS = "NotoSansSC.ttf"
SERIF = "NotoSerifSC.ttf"
GARAMOND = "CormorantGaramond.ttf"
PIXEL12 = "fusion-pixel-12px-proportional-zh_hans.ttf"
PIXEL8 = "fusion-pixel-8px-proportional-zh_hans.ttf"


@lru_cache(maxsize=256)
def _font(name: str, px: int, axes: tuple | None) -> ImageFont.FreeTypeFont:
    ft = ImageFont.truetype(str(config.FONT_DIR / name), px)
    if axes:
        try:
            ft.set_variation_by_axes(list(axes))
        except Exception:
            pass
    return ft


class Canvas:
    def __init__(self, panel: Panel, ss: int | None = None, bg: str = "white"):
        self.panel = panel
        self.s = ss if ss is not None else panel.default_ss
        self.W, self.H = panel.W, panel.H
        self.img = Image.new("RGB", (self.W * self.s, self.H * self.s), panel.color(bg))
        self.d = ImageDraw.Draw(self.img)

    # ── colours & fonts ──────────────────────────────────────────────────────
    def col(self, c):
        return self.panel.color(c) if isinstance(c, str) else c

    def doto(self, px, wght=800, rnd=100):
        return _font(DOTO, int(px * self.s), (rnd, wght))

    def mono(self, px, bold=False):
        return _font(MONOB if bold else MONO, int(px * self.s), None)

    def sans(self, px, wght=500):
        return _font(SANS, int(px * self.s), (wght,))

    def serif(self, px, wght=500):
        return _font(SERIF, int(px * self.s), (wght,))

    def garamond(self, px, wght=600):
        return _font(GARAMOND, int(px * self.s), (wght,))

    def font(self, filename, px):
        """Load any TTF from fonts/ by filename (style-specific faces)."""
        return _font(filename, int(px * self.s), None)

    def pixel(self, px=12):
        """CJK pixel font (Fusion Pixel). Crisp on e-ink ONLY at integer
        multiples of the native size (12 → 12/24/36; 8 → 8/16) on an ss=1
        canvas, drawn with antialiasing off — use via ptext()."""
        native = 8 if px % 12 else 12
        assert px % native == 0, f"pixel font size {px} not a multiple of {native}"
        assert self.s == 1, "pixel fonts need an ss=1 canvas (downscale blurs the grid)"
        return _font(PIXEL8 if native == 8 else PIXEL12, px, None)

    # ── text ─────────────────────────────────────────────────────────────────
    def text(self, x, y, t, font, fill="black", anchor=None, aa=True):
        if not aa:
            prev = self.d.fontmode
            self.d.fontmode = "1"   # bilevel rendering: no antialiasing
        self.d.text((x * self.s, y * self.s), t, font=font, fill=self.col(fill), anchor=anchor)
        if not aa:
            self.d.fontmode = prev

    def ptext(self, x, y, t, px=12, fill="black", anchor=None):
        """Pixel-font text: native-multiple size, antialiasing off."""
        self.text(x, y, t, self.pixel(px), fill=fill, anchor=anchor, aa=False)

    def tw(self, t, font) -> float:
        return font.getlength(t) / self.s

    def fit_doto(self, t, max_w, sizes, wght=800):
        for sz in sizes:
            f = self.doto(sz, wght)
            if self.tw(t, f) <= max_w:
                return f
        return self.doto(sizes[-1], wght)

    def ellipsize(self, font, text, max_w):
        if self.tw(text, font) <= max_w:
            return text
        while text and self.tw(text + "…", font) > max_w:
            text = text[:-1]
        return text + "…"

    def text_mixed(self, x, y, t, ascii_font, cjk_font, max_w, fill="black"):
        """Per-char ASCII/CJK font mix, truncated with … at max_w. Returns end x."""
        cx = x
        for ch in t:
            f = ascii_font if ch.isascii() else cjk_font
            chw = self.tw(ch, f)
            if cx + chw > x + max_w:
                self.text(cx, y, "…", ascii_font, fill=fill, anchor="lm")
                return cx
            self.text(cx, y, ch, f, fill=fill, anchor="lm")
            cx += chw
        return cx

    _NO_LINE_START = "。，、；：？！）》」』…—·"

    def wrap(self, t, font, max_w) -> list[str]:
        """CJK-aware wrap: break anywhere on CJK, prefer spaces for latin runs,
        and hang closing punctuation (a line must not start with 。，…)."""
        lines, line = [], ""
        for ch in t.replace("\n", " "):
            cand = line + ch
            if self.tw(cand, font) <= max_w or (ch in self._NO_LINE_START and line):
                line = cand
                continue
            if " " in line and ch.isascii() and ch != " ":
                head, _, tail = line.rpartition(" ")
                lines.append(head)
                line = tail + ch
            else:
                lines.append(line)
                line = "" if ch == " " else ch
        if line.strip():
            lines.append(line)
        return lines

    # ── shapes ───────────────────────────────────────────────────────────────
    def rect(self, x, y, w, h, fill=None, outline=None, width=1):
        self.d.rectangle([x * self.s, y * self.s, (x + w) * self.s, (y + h) * self.s],
                         fill=self.col(fill) if fill else None,
                         outline=self.col(outline) if outline else None,
                         width=max(1, int(width * self.s)))

    def line(self, x0, y0, x1, y1, fill="black", width=1):
        self.d.line([x0 * self.s, y0 * self.s, x1 * self.s, y1 * self.s],
                    fill=self.col(fill), width=max(1, int(width * self.s)))

    def tile(self, x, y, w, h, r=16, outline="black", width=1, fill=None):
        self.d.rounded_rectangle([x * self.s, y * self.s, (x + w) * self.s, (y + h) * self.s],
                                 radius=int(r * self.s),
                                 outline=self.col(outline) if outline else None,
                                 width=max(1, int(width * self.s)),
                                 fill=self.col(fill) if fill else None)

    def pill(self, x, y, w, h, t, font, fill="black", fg="white"):
        self.d.rounded_rectangle([x * self.s, y * self.s, (x + w) * self.s, (y + h) * self.s],
                                 radius=int(h / 2 * self.s), fill=self.col(fill))
        self.text(x + w / 2, y + h / 2, t, font, fill=fg, anchor="mm")

    def header(self, x, y, label, accent="black", fg="black"):
        """Small colour tab + mono label — tile header, Nothing style."""
        self.d.rounded_rectangle([x * self.s, (y + 1) * self.s, (x + 4) * self.s, (y + 13) * self.s],
                                 radius=int(2 * self.s), fill=self.col(accent))
        self.text(x + 12, y, label, self.mono(13), fill=fg)

    def dot(self, cx, cy, r, fill="black"):
        self.d.ellipse([(cx - r) * self.s, (cy - r) * self.s,
                        (cx + r) * self.s, (cy + r) * self.s], fill=self.col(fill))

    def dotsicon(self, cx, cy, kind, R=18, col="black"):
        """Nothing-style dot-matrix weather icon: sun/moon/cloud/snow/rain."""
        if kind == "sun":
            self.dot(cx, cy, 6, col)
            for a in range(0, 360, 45):
                self.dot(cx + math.cos(math.radians(a)) * R,
                         cy + math.sin(math.radians(a)) * R, 2.4, col)
        elif kind == "moon":
            for a in range(40, 320, 28):
                self.dot(cx + math.cos(math.radians(a)) * R,
                         cy + math.sin(math.radians(a)) * R, 2.6, col)
        elif kind in ("cloud", "snow"):
            for (px, py, rr) in [(cx - 9, cy + 2, 5), (cx + 1, cy - 4, 6.5), (cx + 11, cy + 2, 5),
                                 (cx - 3, cy + 4, 5), (cx + 7, cy + 4, 5)]:
                self.dot(px, py, rr, col)
        elif kind == "rain":
            for (px, py, rr) in [(cx - 8, cy - 3, 5), (cx + 2, cy - 7, 6), (cx + 10, cy - 3, 5)]:
                self.dot(px, py, rr, col)
            for px in (cx - 6, cx + 2, cx + 10):
                self.dot(px, cy + 8, 2.2, col)
                self.dot(px, cy + 14, 2.2, col)

    def hatch(self, x, y, w, h, style="diag", spacing=6, col="black", width=1, r=0):
        """Fill a region with a line/dot pattern — the 1-bit way to say "gray".
        Perceived darkness = ink coverage: tune spacing (denser = darker) and
        width. styles: diag (////), cross (crosshatch), lines (horizontal),
        dots (stipple grid). r rounds the region's corners."""
        s = self.s
        x0, y0 = int(x * s), int(y * s)
        W2, H2 = max(1, int(w * s)), max(1, int(h * s))
        pat = Image.new("L", (W2, H2), 0)
        pd = ImageDraw.Draw(pat)
        sp = max(2, int(spacing * s))
        lw = max(1, int(width * s))
        if style in ("diag", "cross"):
            for o in range(-H2, W2 + H2, sp):
                pd.line([o, H2, o + H2, 0], fill=255, width=lw)
        if style == "cross":
            for o in range(-H2, W2 + H2, sp):
                pd.line([o, 0, o + H2, H2], fill=255, width=lw)
        elif style == "lines":
            for yy in range(0, H2, sp):
                pd.line([0, yy, W2, yy], fill=255, width=lw)
        elif style == "dots":
            rr = max(1, lw)
            for j, yy in enumerate(range(0, H2, sp)):
                for xx in range(sp // 2 if j % 2 else 0, W2, sp):
                    pd.ellipse([xx - rr, yy - rr, xx + rr, yy + rr], fill=255)
        if r:
            mask = Image.new("L", (W2, H2), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                [0, 0, W2 - 1, H2 - 1], radius=int(r * s), fill=255)
            pat = ImageChops.multiply(pat, mask)
        solid = Image.new("RGB", (W2, H2), self.col(col))
        self.img.paste(solid, (x0, y0), pat)

    def ring(self, cx, cy, R, ratio, w=7, col="black", track="black"):
        for a in range(0, 360, 12):  # faint dotted track
            self.dot(cx + math.cos(math.radians(a)) * R,
                     cy + math.sin(math.radians(a)) * R, 1.2, track)
        bb = [(cx - R) * self.s, (cy - R) * self.s, (cx + R) * self.s, (cy + R) * self.s]
        end = -90 + max(0.0, min(1.0, ratio)) * 360
        self.d.arc(bb, -90, end, fill=self.col(col), width=max(1, int(w * self.s)))

    # ── compositing ──────────────────────────────────────────────────────────
    def paste(self, img: Image.Image, x: int, y: int):
        """Paste a panel-ready (pre-dithered) image. Requires ss=1 — a later
        downscale would smear the dither pattern into grays."""
        assert self.s == 1, "paste pre-dithered images only on an ss=1 canvas"
        self.img.paste(img, (x, y))

    def invert_region(self, x, y, w, h, r=16):
        """B/W 'interrupt' accent: flip a rounded region to reverse video."""
        s = self.s
        x0, y0, x1, y1 = int(x * s), int(y * s), int((x + w) * s), int((y + h) * s)
        region = self.img.crop((x0, y0, x1, y1))
        mask = Image.new("1", region.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, region.size[0] - 1, region.size[1] - 1], radius=int(r * s), fill=1)
        self.img.paste(region.point(lambda p: 255 - p), (x0, y0), mask)

    def finish(self) -> Image.Image:
        if self.s == 1:
            return self.img
        return self.img.resize((self.W, self.H), Image.LANCZOS)
