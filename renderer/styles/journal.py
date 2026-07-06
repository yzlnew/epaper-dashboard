"""Style: journal — a text-first "morning paper" front page.

Serif masthead + dateline, then a left column carrying an AI-written 晨报
briefing (weather + today's headlines digested into ~100 Chinese characters,
cached daily) above the headline list, and a right sidebar with home sensor
data. Entirely legible on 1-bit panels; the colour panel adds red/blue accents.

Without an AI backend the briefing block is dropped and headlines move up —
the page still works as a plain news front.
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


def render(panel, ctx):
    c = Canvas(panel)
    now, states, news = ctx.now, ctx.states, ctx.news

    # ── masthead ─────────────────────────────────────────────────────────────
    c.text(panel.W / 2, 30, "The E-Ink Daily", c.garamond(44, 640), anchor="ma")
    w = ds.weather_summary(states)
    dateline = (f"{now.year}年{now.month}月{now.day}日  "
                f"{config.CN_WD[now.isoweekday() - 1]}  ·  "
                f"{w['cn']} {ds.num(w['temp'], '%.0f')}°C")
    c.ptext(panel.W / 2, 88, dateline, 12, anchor="ma")
    c.line(M, 114, panel.W - M, 114, width=3)
    c.line(M, 119, panel.W - M, 119, width=1)

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
        bf = c.pixel(12)
        for line in c.wrap(brief, bf, col_w)[:6]:
            c.ptext(col_x, y, line, 12)
            y += 21
        y += 10
        c.line(col_x, y, col_x + col_w, y, width=1)
        y += 16

    # ── headlines ────────────────────────────────────────────────────────────
    c.rect(col_x, y + 2, 4, 14, fill="blue")
    c.ptext(col_x + 12, y + 1, "要闻 HEADLINES", 12)
    y += 30
    hf = c.pixel(12)
    if not news:
        c.ptext(col_x, y, "暂无新闻 / NO FEED", 12)
    for i, it in enumerate(news[:6]):
        if y > panel.H - 40:
            break
        c.text(col_x, y, f"{i + 1:02d}", c.mono(14, bold=True), fill="red")
        c.ptext(col_x + 30, y + 2, c.ellipsize(hf, it.get("title") or "", col_w - 30), 12)
        y += 30

    # ── sidebar: home data ───────────────────────────────────────────────────
    sy = 136
    c.tile(sb_x, sy, sb_w, 250, r=10)
    c.text(sb_x + 16, sy + 14, "AT HOME", c.mono(13, bold=True))
    hcho = ds.f(ds.state(states, "hcho"))
    rows = [
        ("室温", ds.num(ds.state(states, "temp")) + " °C"),
        ("湿度", ds.num(ds.state(states, "humidity"), "%.0f") + " %"),
        ("PM2.5", ds.num(ds.state(states, "pm25"), "%.0f")),
        ("CO2", ds.num(ds.state(states, "co2"), "%.0f") + " ppm"),
        ("甲醛", (ds.num(hcho * 1000 if hcho is not None else None, "%.0f")) + " µg/m³"),
    ]
    ry = sy + 46
    vf = c.mono(16, bold=True)
    for k, v in rows:
        c.ptext(sb_x + 16, ry + 2, k, 12)
        c.text(sb_x + sb_w - 16, ry, v, vf, anchor="ra")
        ry += 38
        if ry < sy + 240:
            c.line(sb_x + 16, ry - 10, sb_x + sb_w - 16, ry - 10, width=1)

    # sidebar footer: clock stamp
    c.tile(sb_x, sy + 266, sb_w, 78, r=10, fill="black", outline="black")
    tstr = now.strftime("%H:%M")
    c.text(sb_x + sb_w / 2, sy + 266 + 39, tstr, c.doto(44), fill="white", anchor="mm")

    # ── page footer ──────────────────────────────────────────────────────────
    c.line(M, panel.H - 26, panel.W - M, panel.H - 26, width=1)
    c.text(M, panel.H - 20, "E-PAPER DASHBOARD", c.mono(10))
    c.text(panel.W - M, panel.H - 20, now.strftime("UPDATED %H:%M"), c.mono(10), anchor="ra")
    return c.finish()
