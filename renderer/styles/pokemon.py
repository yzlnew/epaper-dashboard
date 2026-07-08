"""Style: pokemon — a daily Pokémon with just the time and weather.

One Pokémon per day (deterministic hash of the date over the gen 1-5 dex,
whose sprites are proper 96x96 pixel art). The sprite comes from the PokeAPI
sprites repo, its Chinese/English names from the PokeAPI species endpoint —
both cached on disk per dex id, so each id is downloaded exactly once and the
style keeps working offline on repeat days. If nothing is cached and the
network is down, a Poké Ball drawn from primitives stands in.

Rendering keeps the pixel-art contract: trim the sprite's transparent border,
upscale by an INTEGER factor with NEAREST (never smooth), and on B/W dither
the flat colours with an ordered Bayer map so shading reads as retro texture.
Layout is a Game Boy dialog: double-frame page, huge pixel-font clock,
weather, and a Pokédex entry box.

Sprite artwork © Nintendo/Game Freak — personal dashboard use.
"""

from __future__ import annotations

import json
import random
import sys

import numpy as np
import requests
from PIL import Image

from .. import config, datasources as ds
from ..draw import Canvas
from ..panels import _BAYER8

SPRITE_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{id}.png"
SPECIES_URL = "https://pokeapi.co/api/v2/pokemon-species/{id}/"
MAX_ID = 649  # gens 1-5: real 96x96 pixel sprites
UA = {"User-Agent": "epaper-dashboard"}


def _daily_id(day: int) -> int:
    return (day * 2654435761) % MAX_ID + 1


def _fetch(day: int):
    """(sprite RGBA, id, {'cn','en'}) for today, cached per dex id."""
    pid = _daily_id(day)
    config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    spr_p = config.CACHE_DIR / f"pokemon-{pid}.png"
    meta_p = config.CACHE_DIR / f"pokemon-{pid}.json"
    if not spr_p.exists():
        r = requests.get(SPRITE_URL.format(id=pid), headers=UA, timeout=15)
        r.raise_for_status()
        spr_p.write_bytes(r.content)
    if not meta_p.exists():
        meta = {"cn": "", "en": f"NO.{pid}"}
        try:
            r = requests.get(SPECIES_URL.format(id=pid), headers=UA, timeout=15)
            r.raise_for_status()
            data = r.json()
            meta["en"] = (data.get("name") or "").upper()
            for n in data.get("names", []):
                if n.get("language", {}).get("name", "").lower() == "zh-hans":
                    meta["cn"] = n.get("name") or ""
        except Exception as exc:  # noqa: BLE001  (sprite without names is fine)
            print(f"[pokemon] species meta failed: {exc}", file=sys.stderr)
        meta_p.write_text(json.dumps(meta, ensure_ascii=False))
    return Image.open(spr_p).convert("RGBA"), pid, json.loads(meta_p.read_text())


def _any_cached():
    """Offline fallback: reuse whatever dex entry is already on disk."""
    cached = sorted(config.CACHE_DIR.glob("pokemon-*.png"))
    if not cached:
        return None
    spr_p = random.choice(cached)
    pid = int(spr_p.stem.split("-")[1])
    meta_p = spr_p.with_suffix(".json")
    meta = json.loads(meta_p.read_text()) if meta_p.exists() else {"cn": "", "en": f"NO.{pid}"}
    return Image.open(spr_p).convert("RGBA"), pid, meta


def _pokeball(size: int = 288) -> Image.Image:
    """Last-resort placeholder, drawn from primitives."""
    from PIL import ImageDraw

    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    m = size // 24
    d.ellipse([m, m, size - m, size - m], fill=(200, 0, 0, 255),
              outline=(0, 0, 0, 255), width=size // 24)
    d.pieslice([m, m, size - m, size - m], 0, 180, fill=(255, 255, 255, 255))
    d.line([m, size // 2, size - m, size // 2], fill=(0, 0, 0, 255), width=size // 12)
    r = size // 7
    d.ellipse([size // 2 - r, size // 2 - r, size // 2 + r, size // 2 + r],
              fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=size // 24)
    return im


def _prepare_sprite(panel, spr: Image.Image, box: int) -> Image.Image:
    """Trim, integer-NEAREST upscale, composite on white, fit panel gamut."""
    bbox = spr.getbbox()
    if bbox:
        spr = spr.crop(bbox)
    factor = max(1, min(box // spr.width, box // spr.height))
    spr = spr.resize((spr.width * factor, spr.height * factor), Image.NEAREST)
    flat = Image.new("RGB", spr.size, (255, 255, 255))
    flat.paste(spr, (0, 0), spr)
    if panel.is_color:
        return flat  # export's nearest-ink quantise suits flat pixel art
    g = np.asarray(flat.convert("L"))
    t = np.tile(((_BAYER8 + 0.5) * 4).astype(np.uint8),
                (g.shape[0] // 8 + 1, g.shape[1] // 8 + 1))[:g.shape[0], :g.shape[1]]
    return Image.fromarray(((g > t) * 255).astype(np.uint8), "L").convert("RGB")


def render(panel, ctx):
    c = Canvas(panel, ss=1)
    now = ctx.now
    w = ds.weather_summary(ctx.states)

    # Game Boy double frame
    c.rect(10, 10, panel.W - 20, panel.H - 20, outline="black", width=3)
    c.rect(20, 20, panel.W - 40, panel.H - 40, outline="black", width=1)

    # ── daily sprite, left ───────────────────────────────────────────────────
    try:
        spr, pid, meta = _fetch(now.toordinal())
    except Exception as exc:  # noqa: BLE001
        print(f"[pokemon] fetch failed ({exc}); using cache/placeholder", file=sys.stderr)
        got = _any_cached()
        spr, pid, meta = got if got else (_pokeball(), 0, {"cn": "精灵球", "en": "POKE BALL"})
    art = _prepare_sprite(panel, spr, 360)
    ax, ay = 48 + (360 - art.width) // 2, 48 + (360 - art.height) // 2
    c.paste(art, ax, ay)
    # ground shadow ellipse (dotted, Pokédex style)
    gy = min(ay + art.height + 14, 434)
    for dx in range(-120, 121, 12):
        c.dot(228 + dx, gy, 1.6, "black")

    # ── right column: time / date / weather ─────────────────────────────────
    cx = 606
    tstr = now.strftime("%H:%M")
    pf72 = c.pixel(72)
    c.ptext(cx - c.tw(tstr, pf72) / 2, 64, tstr, 72)
    c.ptext(cx, 156, f"{now.month}月{now.day}日 {config.CN_WD[now.isoweekday() - 1]}",
            24, anchor="ma")

    icol = "yellow" if w["icon"] == "sun" else ("blue" if w["icon"] in ("rain", "snow") else "black")
    c.dotsicon(cx - 96, 254, w["icon"], R=17, col=icol)
    wt = ds.num(w["temp"], "%.0f")
    tv = w["temp"]
    c.ptext(cx - 52, 228, f"{wt}°", 48,
            fill="red" if (tv is not None and tv >= 32) else "black")
    c.ptext(cx + 66, 240, w["cn"], 24, fill="blue", anchor="ma")

    # ── Pokédex entry box (dialog frame) ─────────────────────────────────────
    bx, by, bw_, bh = 440, 330, 332, 118
    c.rect(bx, by, bw_, bh, outline="black", width=3)
    c.rect(bx + 6, by + 6, bw_ - 12, bh - 12, outline="black", width=1)
    c.ptext(bx + 24, by + 22, f"NO.{pid:03d}", 24, fill="red")
    c.ptext(bx + 24, by + 56, meta.get("cn") or "???", 24)
    c.ptext(bx + 24, by + 88, meta.get("en") or "", 12)
    c.ptext(bx + bw_ - 24, by + 88, "GOTTA CATCH 'EM ALL!", 12, anchor="ra")
    return c.finish()
