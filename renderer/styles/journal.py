"""Style: journal — a text-first "morning paper" front page.

Masthead row: Doto clock top-left, serif "The Daily" centre, red issue number
top-right, dateline with the weather in blue, double rule (black + red).
Left column: AI-written 晨报 briefing (weather + headlines digested into ~100
Chinese characters, cached daily) above the headline list. Right sidebar:
home sensor data with health-coloured values, and a weather card.

Colour degrades gracefully on the B/W panel (all inks collapse to black).
Without an AI backend the briefing block is dropped and headlines move up.
"""

from __future__ import annotations

from .. import ai, config, datasources as ds
from ..draw import Canvas

M = 30  # page margin


def _brief(ctx) -> str:
    if not ctx.news and ai.backend() == "none":
        return ""
    w = ds.weather_summary(ctx.states)
    heads = "；".join((it.get("title") or "")[:40] for it in ctx.news[:6])
    prompt = (f"今天是{ctx.now.month}月{ctx.now.day}日"
              f"{config.CN_WD[ctx.now.isoweekday() - 1]}，天气{w['cn']}，"
              f"气温约{ds.num(w['temp'], '%.0f')}度。今日要闻：{heads or '无'}。"
              "请以冷静、简练的新闻编辑口吻写一段80到110字的中文晨报导语，"
              "串起天气与最重要的一两条新闻，供电子墨水屏展示。"
              "只输出正文，不要标题、引号、表情。")
    return ai.try_cached_text("journal-brief", prompt, "")


def _level_color(v, good, bad):
    """green below `good`, yellow up to `bad`, red beyond; black if unknown."""
    if v is None:
        return "black"
    return "green" if v < good else ("yellow" if v <= bad else "red")


def render(panel, ctx):
    c = Canvas(panel)
    now, states, news = ctx.now, ctx.states, ctx.news
    w = ds.weather_summary(states)

    # ── masthead row: clock / title / issue no. ──────────────────────────────
    c.text(M, 30, now.strftime("%H:%M"), c.doto(34), fill="blue")
    c.text(panel.W - M, 32, f"NO.{now.timetuple().tm_yday:03d}", c.mono(14, bold=True),
           fill="red", anchor="ra")
    c.text(panel.W / 2, 24, "The Daily", c.garamond(46, 640), anchor="ma")
    pf = c.pixel(12)
    p1 = (f"{now.year}年{now.month}月{now.day}日  "
          f"{config.CN_WD[now.isoweekday() - 1]}  ·  ")
    p2 = f"{w['cn']} {ds.num(w['temp'], '%.0f')}°C"
    x0 = (panel.W - c.tw(p1 + p2, pf)) / 2
    c.ptext(x0, 88, p1, 12)
    c.ptext(x0 + c.tw(p1, pf), 88, p2, 12, fill="blue")
    c.line(M, 114, panel.W - M, 114, width=3)
    c.line(M, 119, panel.W - M, 119, fill="red", width=1)

    col_x, col_w = M, 470                     # main column
    sb_x = col_x + col_w + 26                 # sidebar
    sb_w = panel.W - M - sb_x
    y = 136

    # ── briefing ─────────────────────────────────────────────────────────────
    brief = _brief(ctx)
    if brief:
        c.rect(col_x, y + 2, 4, 14, fill="red")
        c.ptext(col_x + 12, y + 1, "晨报 BRIEFING", 12)
        y += 26
        bf = c.serif(18, 620)   # newspaper body; heavy enough to survive threshold
        for line in c.wrap(brief, bf, col_w)[:5]:
            c.text(col_x, y, line, bf)
            y += 27
        y += 10
        c.line(col_x, y, col_x + col_w, y, width=1)
        y += 16

    # ── headlines ────────────────────────────────────────────────────────────
    c.rect(col_x, y + 2, 4, 14, fill="blue")
    c.ptext(col_x + 12, y + 1, "要闻 HEADLINES", 12)
    y += 30
    hf = c.sans(15, 600)
    if not news:
        c.text(col_x, y, "暂无新闻 / NO FEED", hf)
    for i, it in enumerate(news[:6]):
        if y > panel.H - 40:
            break
        c.text(col_x, y, f"{i + 1:02d}", c.mono(14, bold=True), fill="red")
        c.text(col_x + 30, y - 1, c.ellipsize(hf, it.get("title") or "", col_w - 30), hf)
        y += 31

    # ── sidebar: home data, health-coloured ──────────────────────────────────
    sy = 136
    c.tile(sb_x, sy, sb_w, 250, r=10)
    c.rect(sb_x + 16, sy + 16, 4, 14, fill="green")
    c.text(sb_x + 28, sy + 14, "AT HOME", c.mono(13, bold=True))
    tv = ds.f(ds.state(states, "temp"))
    hv = ds.f(ds.state(states, "humidity"))
    pm = ds.f(ds.state(states, "pm25"))
    co = ds.f(ds.state(states, "co2"))
    hcho = ds.f(ds.state(states, "hcho"))
    hug = hcho * 1000 if hcho is not None else None
    rows = [
        ("室温", ds.num(tv) + " °C",
         "red" if (tv is not None and tv >= 28) else "black"),
        ("湿度", ds.num(hv, "%.0f") + " %", "blue"),
        ("PM2.5", ds.num(pm, "%.0f"), _level_color(pm, 35, 75)),
        ("CO2", ds.num(co, "%.0f") + " ppm", _level_color(co, 800, 1200)),
        ("甲醛", ds.num(hug, "%.0f") + " µg/m³", _level_color(hug, 50, 80)),
    ]
    ry = sy + 46
    vf, kf = c.mono(16, bold=True), c.sans(14, 600)
    for k, v, col in rows:
        c.text(sb_x + 16, ry, k, kf)
        c.text(sb_x + sb_w - 16, ry, v, vf, fill=col, anchor="ra")
        ry += 38
        if ry < sy + 240:
            c.line(sb_x + 16, ry - 10, sb_x + sb_w - 16, ry - 10, width=1)

    # sidebar footer: weather card (blue, white ink)
    wy = sy + 264
    c.tile(sb_x, wy, sb_w, panel.H - wy - 22, r=10, fill="blue", outline="blue")
    cyc = wy + (panel.H - wy - 22) / 2
    c.dotsicon(sb_x + 40, cyc, w["icon"], R=13, col="white")
    c.text(sb_x + 80, cyc - 2, f"{ds.num(w['temp'], '%.0f')}°", c.doto(36),
           fill="white", anchor="lm")
    c.ptext(sb_x + sb_w - 18, cyc, w["cn"], 24, fill="white", anchor="rm")

    # ── page footer ──────────────────────────────────────────────────────────
    c.line(M, panel.H - 26, panel.W - M, panel.H - 26, width=1)
    c.dot(M + 3, panel.H - 17, 3, "red")
    c.text(M + 14, panel.H - 22, "THE DAILY", c.mono(10))
    c.text(col_x + col_w, panel.H - 22, now.strftime("UPDATED %H:%M"), c.mono(10), anchor="ra")
    return c.finish()
