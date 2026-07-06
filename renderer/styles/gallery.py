"""Style: gallery — full-bleed photo frame with a slim caption bar.

The photo (Bing / NAS / Picsum / AI art, per EINK_PHOTO_SOURCE) fills the top
416px, dithered into the panel's gamut. The bottom 64px black bar carries the
date in Doto and a caption: the source's own title (Bing copyright, NAS file
name) when available, optionally replaced by an AI-written one-liner describing
the picture (EINK_AI_CAPTION=1).

Falls back to the `nothing` dashboard if the photo fetch fails, so the panel
never shows an error frame.
"""

from __future__ import annotations

import hashlib
import sys

from .. import ai, config, imagesource
from ..draw import Canvas
from . import nothing

BAR = 64


def _caption(photo, hint: str) -> str:
    """Caption for the bar: AI description when EINK_AI_CAPTION=1 (cached by
    photo content hash, so a repeated photo never re-pays the agent call),
    otherwise the source's own title."""
    import io
    import os

    if os.getenv("EINK_AI_CAPTION") != "1":
        return hint
    raw = io.BytesIO()
    photo.save(raw, format="JPEG", quality=80)
    key = "caption-" + hashlib.md5(raw.getvalue()).hexdigest()[:12]
    cache = config.CACHE_DIR / f"{key}.txt"
    if cache.exists():
        return cache.read_text().strip() or hint
    try:
        tmp = config.CACHE_DIR / f"{key}.jpg"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(raw.getvalue())
        cap = ai.caption_image(
            tmp, "用一句不超过20字的中文描述这张照片的画面与氛围，不要引号和句号。")
        cap = (cap or "").strip().splitlines()[-1][:40]
        cache.write_text(cap)
        return cap or hint
    except Exception as exc:  # noqa: BLE001
        print(f"[gallery] AI caption failed: {exc}", file=sys.stderr)
        return hint


def render(panel, ctx):
    try:
        photo, hint = imagesource.fetch_photo()
    except Exception as exc:  # noqa: BLE001
        print(f"[gallery] photo fetch failed ({exc}); falling back to nothing", file=sys.stderr)
        return nothing.render(panel, ctx)

    c = Canvas(panel, ss=1)  # pre-dithered pixels must not be rescaled
    c.paste(panel.prepare_photo(photo, (panel.W, panel.H - BAR)), 0, 0)

    # caption bar
    y0 = panel.H - BAR
    c.rect(0, y0, panel.W, BAR, fill="black")
    now = ctx.now
    dstr = now.strftime("%m·%d")
    df = c.doto(34)
    c.text(20, y0 + BAR / 2, dstr, df, fill="white", anchor="lm")
    # on the black bar, coloured inks only exist on the colour panel — B/W
    # collapses every ink to black, which would vanish here
    hi = "yellow" if panel.is_color else "white"
    dot_col = "red" if panel.is_color else "white"
    wd = config.EN_WD[now.isoweekday() - 1]
    c.text(24 + c.tw(dstr, df) + 14, y0 + BAR / 2, wd, c.mono(13, bold=True),
           fill=hi, anchor="lm")

    cap = _caption(photo, hint)
    if cap:
        capf = c.sans(15, 600)
        shown = c.ellipsize(capf, cap, panel.W - 220)
        c.text(panel.W - 20, y0 + BAR / 2, shown, capf, fill="white", anchor="rm")
        c.dot(panel.W - 28 - c.tw(shown, capf) - 14, y0 + BAR / 2, 3, dot_col)
    return c.finish()
