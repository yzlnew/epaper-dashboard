"""Style: poster — photo on top, oversized date + AI one-liner below.

Top ~62% is the photo (dithered); the bottom white band is typographic: a huge
Doto day-of-month, month/weekday stack, today's weather, and a short AI-written
line for the day (今日一句 — weather-aware, cached daily). Without an AI
backend it falls back to a small built-in rotation of quiet one-liners.
"""

from __future__ import annotations

import sys

from .. import ai, config, datasources as ds, imagesource
from ..draw import Canvas
from . import nothing

PHOTO_H = 300

FALLBACK_LINES = [
    "把今天过成喜欢的样子", "慢慢来，比较快", "风景在路上，也在窗前",
    "一杯茶的时间，想想重要的事", "好好吃饭，好好睡觉", "留一点空白给自己",
    "今天也是值得记录的一天", "心里有光，慢食三餐",
]


def _daily_line(ctx) -> str:
    w = ds.weather_summary(ctx.states)
    prompt = (f"今天是{ctx.now.year}年{ctx.now.month}月{ctx.now.day}日"
              f"{config.CN_WD[ctx.now.isoweekday() - 1]}，天气{w['cn']}，"
              f"气温约{ds.num(w['temp'], '%.0f')}度。"
              "写一句克制、干净、略带诗意的中文早安短句，不超过16个字。"
              "只输出这一句，不要引号、句号、表情。")
    line = ai.try_cached_text("poster-line", prompt, "")
    line = (line or "").strip().splitlines()[-1].strip("「」\"'“”。") if line else ""
    if not line or len(line) > 24:
        line = FALLBACK_LINES[ctx.now.toordinal() % len(FALLBACK_LINES)]
    return line


def render(panel, ctx):
    try:
        photo, _hint = imagesource.fetch_photo()
    except Exception as exc:  # noqa: BLE001
        print(f"[poster] photo fetch failed ({exc}); falling back to nothing", file=sys.stderr)
        return nothing.render(panel, ctx)

    c = Canvas(panel, ss=1)
    now = ctx.now
    c.paste(panel.prepare_photo(photo, (panel.W, PHOTO_H)), 0, 0)
    c.line(0, PHOTO_H, panel.W, PHOTO_H, fill="black", width=2)

    band_y = PHOTO_H
    # Huge day-of-month, left
    day = f"{now.day:02d}"
    df = c.doto(120)
    c.text(28, band_y + (panel.H - band_y) / 2 + 4, day, df, anchor="lm")
    dx = 28 + c.tw(day, df) + 22

    # Month / weekday stack + red rule
    c.rect(dx, band_y + 38, 4, 96, fill="red")
    c.text(dx + 16, band_y + 38, config.EN_MON[now.month - 1], c.mono(20, bold=True))
    c.text(dx + 16, band_y + 66, config.EN_WD[now.isoweekday() - 1], c.mono(20))
    c.text(dx + 16, band_y + 98, f"{now.year}", c.mono(14))

    # Weather, right-top of the band
    w = ds.weather_summary(ctx.states)
    icol = "yellow" if w["icon"] == "sun" else ("blue" if w["icon"] in ("rain", "snow") else "black")
    c.dotsicon(panel.W - 150, band_y + 52, w["icon"], R=15, col=icol)
    wt = f"{ds.num(w['temp'], '%.0f')}°"
    c.text(panel.W - 110, band_y + 34, wt, c.doto(40))
    c.text(panel.W - 110, band_y + 78, w["cn"], c.sans(18, 600), fill="blue")

    # AI one-liner across the bottom
    line = _daily_line(ctx)
    c.dot(34, panel.H - 32, 3.4, "red")
    c.text(48, panel.H - 32, line, c.sans(21, 500), anchor="lm")
    c.text(panel.W - 24, panel.H - 32, "今日一句", c.sans(12, 500), fill="black", anchor="rm")
    return c.finish()
