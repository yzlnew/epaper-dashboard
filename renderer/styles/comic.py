"""Style: comic — an American comic-book front page.

Golden-age comic idioms, all drawn with primitives: thick-bordered panels with
offset drop shadows, a starburst carrying the temperature, speech bubbles for
the news, a yellow NARRATOR caption with an AI-written line (cached daily),
Ben-Day dots (Canvas.hatch) for the printed-paper texture, and an alert burst
breaking out of the home panel when something needs attention.

The classic four-colour print palette (black/red/yellow/blue on paper) is
exactly what the E6 has; on B/W the yellow fills fall back to white so black
lettering stays readable.
"""

from __future__ import annotations

import math
from functools import lru_cache

from .. import ai, config, datasources as ds
from ..draw import Canvas

BANGERS = "Bangers-Regular.ttf"        # comic display caps (titles, tabs)
COMICNEUE = "ComicNeue-Bold.ttf"       # Comic Sans successor (latin lettering)
KUAILE = "ZCOOLKuaiLe-Regular.ttf"     # playful rounded CJK (站酷快乐体)


@lru_cache(maxsize=1)
def _kuaile_cmap() -> set:
    from fontTools.ttLib import TTFont

    return set(TTFont(str(config.FONT_DIR / KUAILE)).getBestCmap())


def _lettering(c, t, px):
    """Comic lettering per string: Comic Neue for pure latin, 快乐体 for CJK it
    covers, bold Noto as the safety net (AI text can contain rare chars)."""
    if t.isascii():
        return c.font(COMICNEUE, px + 2)   # Comic Neue runs small for its size
    if all(ord(ch) in _kuaile_cmap() for ch in t if not ch.isascii()):
        return c.font(KUAILE, px)
    return c.sans(px, 700)

FALLBACK_LINES = [
    "与此同时，在我们英雄的家中……", "这座城市今天出奇地平静……",
    "阳光照常升起，冒险仍在继续！", "没有超能力，也要面对星期一！",
    "一切尽在掌握……大概吧。", "剧情还在酝酿，请保持关注！",
]


def _narration(ctx) -> str:
    w = ds.weather_summary(ctx.states)
    prompt = (f"今天是{ctx.now.month}月{ctx.now.day}日"
              f"{config.CN_WD[ctx.now.isoweekday() - 1]}，天气{w['cn']}，"
              f"气温约{ds.num(w['temp'], '%.0f')}度。"
              "请以美式漫画旁白（NARRATOR）的夸张戏剧化口吻，写一句不超过22字的"
              "中文旁白总结今天，可以幽默。只输出这一句，不要引号和表情。")
    line = ai.try_cached_text("comic-line", prompt, "")
    line = (line or "").strip().splitlines()[-1].strip("「」\"'“”") if line else ""
    if not line or len(line) > 30:
        line = FALLBACK_LINES[ctx.now.toordinal() % len(FALLBACK_LINES)]
    return line


def _shadow_box(c, x, y, w, h, fill="white", off=5, border=3, r=3):
    c.rect(x + off, y + off, w, h, fill="black")
    c.tile(x, y, w, h, r=r, fill=fill, outline="black", width=border)


def _tab(c, x, y, t):
    f = c.font(BANGERS, 16)
    w = c.tw(t, f) + 16
    c.rect(x, y, w, 20, fill="black")
    c.text(x + 8, y + 2, t, f, fill="white")


def _burst(c, cx, cy, R, r, n, fill, outline="black", width=3):
    pts = []
    for i in range(2 * n):
        rad = R if i % 2 == 0 else r
        a = math.pi * i / n - math.pi / 2
        pts.append(((cx + math.cos(a) * rad) * c.s, (cy + math.sin(a) * rad) * c.s))
    c.d.polygon(pts, fill=c.col(fill), outline=c.col(outline),
                width=max(1, int(width * c.s)))


def _bubble(c, x, y, w, h, tipx, tipy, fill="white"):
    c.tile(x, y, w, h, r=16, fill=fill, outline="black", width=3)
    ey = y + h if tipy >= y + h else y                    # tail leaves top or bottom
    b1 = max(x + 22, min(tipx - 16, x + w - 54))
    b2 = b1 + 30
    c.d.polygon([(b1 * c.s, ey * c.s), (b2 * c.s, ey * c.s), (tipx * c.s, tipy * c.s)],
                fill=c.col(fill), outline=c.col("black"), width=int(3 * c.s))
    c.line(b1 + 3, ey, b2 - 3, ey, fill=fill, width=5)    # erase the base seam


def render(panel, ctx):
    c = Canvas(panel, ss=1)
    now, states, news = ctx.now, ctx.states, ctx.news
    w = ds.weather_summary(states)
    YEL = "yellow" if panel.is_color else "white"         # yellow fills need black ink

    # printed-paper texture + page frame
    c.hatch(8, 8, panel.W - 16, 102, style="dots",
            spacing=8 if panel.is_color else 11, col=YEL if panel.is_color else "black")
    c.rect(6, 6, panel.W - 12, panel.H - 12, outline="black", width=2)

    # ── header: title box / clock / temperature burst ────────────────────────
    _shadow_box(c, 20, 20, 300, 66, fill=YEL)
    c.text(36, 26, "THE DAILY COMIC", c.font(BANGERS, 22))
    c.text(36, 50, f"{now.month}月{now.day}日 {config.CN_WD[now.isoweekday() - 1]}",
           c.font(KUAILE, 26))
    c.text(300, 28, f"NO.{now.timetuple().tm_yday:03d}", c.mono(11, bold=True),
           fill="red", anchor="ra")

    _shadow_box(c, 352, 30, 186, 50)
    c.text(352 + 93, 55, now.strftime("%H:%M"), c.doto(34), anchor="mm")

    tv = w["temp"]
    hot = tv is not None and tv >= 32
    _burst(c, 676, 62, 54, 37, 11, fill="red" if hot else YEL, width=3)
    ink = "white" if (hot and panel.is_color) else "black"
    c.text(676, 52, f"{ds.num(tv, '%.0f')}°", c.font(BANGERS, 40), fill=ink, anchor="mm")
    c.text(676, 70, w["cn"], c.font(KUAILE, 22), fill=ink, anchor="ma")

    # ── left panel: AT HOME ──────────────────────────────────────────────────
    hx, hy, hw, hh = 20, 122, 292, 226
    _shadow_box(c, hx, hy, hw, hh)
    _tab(c, hx - 3, hy - 3, "AT HOME")
    temp = ds.num(ds.state(states, "temp"))
    hum = ds.num(ds.state(states, "humidity"), "%.0f")
    c.text(hx + 20, hy + 34, "TEMP °C", c.mono(12, bold=True))
    c.text(hx + 20, hy + 52, temp, c.doto(40), fill="red" if hot else "black")
    c.text(hx + 156, hy + 34, "HUM %", c.mono(12, bold=True))
    c.text(hx + 156, hy + 52, hum, c.doto(40), fill="blue")

    lb = ds.f(ds.state(states, "lock_batt")) or 0
    cat_full = states.get(config.ENTITIES["cat_waste"], {}).get("state") == "on"
    cat_low = states.get(config.ENTITIES["cat_sand"], {}).get("state") == "on"
    water_low = states.get(config.ENTITIES["water_lack"], {}).get("state") == "on"
    rows = [
        ("LOCK", f"{lb:.0f}%", "red" if lb < 20 else "black"),
        ("LITTER", "FULL" if cat_full else ("LOW" if cat_low else "OK"),
         "red" if (cat_full or cat_low) else "green"),
        ("WATER", "LOW" if water_low else "OK", "red" if water_low else "green"),
    ]
    ry = hy + 118
    for name, val, col in rows:
        c.text(hx + 20, ry, name, c.mono(13))
        c.text(hx + hw - 20, ry, val, c.mono(13, bold=True), fill=col, anchor="ra")
        c.line(hx + 20, ry + 18, hx + hw - 20, ry + 18, width=1)
        ry += 26
    pm = ds.num(ds.f(ds.state(states, "pm25")), "%.0f")
    co = ds.num(ds.f(ds.state(states, "co2")), "%.0f")
    c.ptext(hx + 20, hy + hh - 26, f"PM2.5 {pm} · CO2 {co}", 12)

    # alert burst breaking out of the panel corner
    alert = ("铲屎!" if cat_full else "补砂!" if cat_low else
             "没水!" if water_low else "没电!" if lb < 20 else "热!" if hot else "")
    if alert:
        _burst(c, hx + hw - 14, hy + hh - 10, 40, 26, 9, fill="red", width=3)
        c.text(hx + hw - 14, hy + hh - 10, alert, c.font(KUAILE, 18),
               fill="white", anchor="mm")

    # ── speech bubbles: the news talks ───────────────────────────────────────
    bx, bw_, bh = 330, 456, 64
    items = news[:3] or [{"title": "今日无事发生。本市各传感器一切正常。"}]
    for i, it in enumerate(items):
        by = 122 + i * 76
        tip_down = i % 2 == 0
        tipx = bx + 60 + i * 150
        tipy = by + bh + 12 if tip_down else by - 12
        _bubble(c, bx, by, bw_, bh, tipx, tipy)
        title = it.get("title") or ""
        hf = _lettering(c, title, 16)
        lines = c.wrap(title, hf, bw_ - 44)[:2]
        if len(lines) == 2:
            lines[1] = c.ellipsize(hf, lines[1], bw_ - 44)
        ty = by + (12 if len(lines) == 2 else 22)
        for ln in lines:
            c.text(bx + 22, ty, ln, hf)
            ty += 23

    # ── bottom: narrator caption + stats panel ───────────────────────────────
    ny, nh = 368, 86
    _shadow_box(c, 20, ny, 496, nh, fill=YEL)
    _tab(c, 17, ny - 3, "NARRATOR")
    line = _narration(ctx)
    nf = _lettering(c, line, 21)
    ly = ny + 22
    for ln in c.wrap(line, nf, 456)[:2]:
        c.text(40, ly, ln, nf)
        ly += 29

    sx, sw = 540, 246
    _shadow_box(c, sx, ny, sw, nh)
    _tab(c, sx - 3, ny - 3, "AIR STATS")
    hcho = ds.f(ds.state(states, "hcho"))
    hug = hcho * 1000 if hcho is not None else None
    srows = [("PM2.5", ds.num(ds.f(ds.state(states, "pm25")), "%.0f")),
             ("CO2", ds.num(ds.f(ds.state(states, "co2")), "%.0f")),
             ("甲醛", ds.num(hug, "%.0f") + " µg")]
    sy2 = ny + 24
    for k, v in srows:
        c.ptext(sx + 18, sy2, k, 12)
        c.text(sx + sw - 18, sy2 - 2, v, c.mono(13, bold=True), anchor="ra",
               fill="red" if (k == "甲醛" and hug is not None and hug > 80) else "black")
        sy2 += 20

    c.text(panel.W - 30, panel.H - 16, "TO BE CONTINUED...", c.font(BANGERS, 15),
           fill="red" if panel.is_color else "black", anchor="rm")
    return c.finish()
