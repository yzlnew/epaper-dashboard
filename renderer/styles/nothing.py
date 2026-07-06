"""Style: nothing — the Nothing UI design system (ported from the original repo).

White paper canvas with floating rounded tiles; Doto dot-matrix numerals for
hero values; Space Mono ALL-CAPS labels; Noto Sans SC for Chinese. Two tiles
are inverted "interrupt" accents: the calendar (red on colour, black on B/W)
and the air card (filled with the air-quality level colour).

Layout: top row CLOCK / WEATHER / CALENDAR; bottom row HOME / AIR / NEWS.
"""

from __future__ import annotations

from .. import config, datasources as ds
from ..draw import Canvas


def render(panel, ctx):
    c = Canvas(panel)
    now, states, news = ctx.now, ctx.states, ctx.news

    LAB = c.mono(13)
    LABB = c.mono(13, bold=True)
    CJKS = c.sans(12)
    CJKW = c.sans(30, 600)
    NEWSF = c.sans(15, 400)

    GAP, M = 16, 20

    # ════════ TOP ROW ════════
    ty, th = 20, 206
    # CLOCK
    cx, cw = M, 326
    c.tile(cx, ty, cw, th)
    c.header(cx + 20, ty + 18, "NOW", accent="blue")
    tstr = now.strftime("%H:%M")
    c.text(cx + cw / 2, ty + th / 2 + 6, tstr, c.fit_doto(tstr, cw - 40, [112, 104, 96, 88]),
           anchor="mm")
    c.text(cx + 22, ty + th - 30, f"{now.year}-{now.month:02d}-{now.day:02d}", LAB)
    wd = config.EN_WD[now.isoweekday() - 1]
    pw = c.tw(wd, LABB) + 24
    c.pill(cx + cw - 20 - pw, ty + th - 34, pw, 22, wd, LABB, fill="blue")

    # WEATHER
    wx, ww = cx + cw + GAP, 196
    c.tile(wx, ty, ww, th)
    c.header(wx + 20, ty + 18, "WEATHER", accent="yellow")
    w = ds.weather_summary(states)
    icol = "yellow" if w["icon"] == "sun" else ("blue" if w["icon"] in ("rain", "snow") else "black")
    c.dotsicon(wx + 46, ty + 74, w["icon"], R=18, col=icol)
    wt = ds.num(w["temp"], "%.0f")
    c.text(wx + 20, ty + 108, f"{wt}°", c.fit_doto(f"{wt}°", ww - 40, [64, 56, 48]))
    c.text(wx + 20, ty + th - 46, w["cn"], CJKW, fill="blue")

    # CALENDAR — inverted accent card (red on colour, black on B/W)
    lx, lw = wx + ww + GAP, panel.W - M - (wx + ww + GAP)
    c.tile(lx, ty, lw, th, outline="red", fill="red")
    c.header(lx + 20, ty + 18, config.EN_MON[now.month - 1], accent="white", fg="white")
    c.text(lx + lw - 20, ty + 18, config.EN_WD[now.isoweekday() - 1], LABB,
           fill="white", anchor="ra")
    dstr = f"{now.day:02d}"
    c.text(lx + lw / 2, ty + th / 2 + 14, dstr, c.fit_doto(dstr, lw - 40, [120, 110, 100]),
           anchor="mm", fill="white")

    # ════════ BOTTOM ROW ════════
    by, bh = ty + th + GAP, panel.H - (ty + th + GAP) - M
    # HOME
    hx, hw = M, 248
    c.tile(hx, by, hw, bh)
    c.header(hx + 20, by + 16, "HOME", accent="green")
    temp, hum = ds.num(ds.state(states, "temp")), ds.num(ds.state(states, "humidity"), "%.0f")
    tv = ds.f(ds.state(states, "temp"))
    c.text(hx + 22, by + 46, "TEMP °C", LAB)
    c.text(hx + 22, by + 64, temp, c.fit_doto(temp, 104, [44, 40, 36]),
           fill="red" if (tv is not None and tv >= 28) else "black")
    c.text(hx + 138, by + 46, "HUM %", LAB)
    c.text(hx + 138, by + 64, hum, c.fit_doto(hum, 96, [44, 40, 36]), fill="blue")
    lb = ds.f(ds.state(states, "lock_batt")) or 0
    cat_full = states.get(config.ENTITIES["cat_waste"], {}).get("state") == "on"
    cat_low = states.get(config.ENTITIES["cat_sand"], {}).get("state") == "on"
    cat = ("FULL", "red") if cat_full else (("LOW", "red") if cat_low else ("OK", "green"))
    water = ("LOW", "red") if states.get(config.ENTITIES["water_lack"], {}).get("state") == "on" \
        else ("OK", "green")
    batt_col = "red" if lb < 20 else ("black" if lb < 50 else "green")
    ry = by + bh - 66
    for name, val, col in [("LOCK", f"{lb:.0f}%", batt_col),
                           ("LITTER", *cat), ("WATER", *water)]:
        c.text(hx + 22, ry, name, LAB)
        c.text(hx + hw - 22, ry, val, LABB, fill=col, anchor="ra")
        ry += 20

    # AIR — card filled with the air-quality level colour, white ink
    ax, aw = hx + hw + GAP, 188
    pm, co = ds.f(ds.state(states, "pm25")), ds.f(ds.state(states, "co2"))
    hcho = ds.f(ds.state(states, "hcho"))
    hug = hcho * 1000 if hcho is not None else None   # mg/m³ → µg/m³
    # GB/T 18883 limit 0.08 mg/m³: green < 50, yellow 50-80, red > 80 µg/m³
    rcol = "black" if hug is None else ("red" if hug > 80 else "yellow" if hug >= 50 else "green")
    c.tile(ax, by, aw, bh, outline=rcol, fill=rcol)
    c.header(ax + 20, by + 16, "AIR", accent="white", fg="white")
    c.ring(ax + aw / 2, by + 92, 52, (hug or 0) / 100, w=8, col="white", track="white")
    rtxt = ds.num(hug, "%.0f") + ("!" if (hug is not None and hug > 80) else "")
    c.text(ax + aw / 2, by + 92, rtxt, c.fit_doto(rtxt, 84, [40, 34, 28]),
           anchor="mm", fill="white")
    c.text(ax + aw / 2, by + 146, "甲醛 μg/m³", CJKS, anchor="ma", fill="white")
    c.text(ax + 20, by + bh - 46, "PM2.5", LAB, fill="white")
    c.text(ax + aw - 20, by + bh - 46, ds.num(pm, "%.0f"), LABB, fill="white", anchor="ra")
    c.text(ax + 20, by + bh - 24, "CO2", LAB, fill="white")
    c.text(ax + aw - 20, by + bh - 24, ds.num(co, "%.0f"), LABB, fill="white", anchor="ra")

    # NEWS
    nx = ax + aw + GAP
    nw = panel.W - M - nx
    c.tile(nx, by, nw, bh)
    c.header(nx + 20, by + 16, "NEWS", accent="red")
    ny = by + 46
    if not news:
        c.text(nx + 20, ny, "暂无新闻 / NO FEED", NEWSF)
    for it in news[:4]:
        if ny > by + bh - 30:
            break
        c.text(nx + 20, ny + 2, "●", CJKS, fill="red")
        c.text(nx + 36, ny, c.ellipsize(NEWSF, it.get("title") or "", nw - 46), NEWSF)
        ny += 30

    return c.finish()
