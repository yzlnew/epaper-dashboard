#!/usr/bin/env python3
"""Cron entrypoint: rotate a panel through its style playlist and deploy.

Each run renders the NEXT style in the playlist (strict rotation tracked in a
state file — cron runs are independent) and pushes it to HA. The panel polls
one fixed URL, so what changes per tick is what that PNG contains.

Playlists via env (comma-separated style names, see renderer/styles):
  EINK_PLAYLIST_BW=nothing,gallery      # default
  EINK_PLAYLIST_E6=nothing,poster,gallery,journal

  set -a && source .env && set +a
  .venv/bin/python -m renderer.rotate --panel e6 [--no-deploy]

A style that throws is skipped in favour of `nothing`, so the panel never
shows a stale or broken frame.
"""

from __future__ import annotations

import argparse
import os
import sys

from . import config
from .render import build_ctx
from .panels import get_panel
from .styles import STYLES

DEFAULT_PLAYLIST = {"bw": "nothing,gallery", "e6": "nothing,poster,gallery,journal"}


def playlist(panel_name: str) -> list[str]:
    raw = os.getenv(f"EINK_PLAYLIST_{panel_name.upper()}") or DEFAULT_PLAYLIST[panel_name]
    names = [s.strip() for s in raw.split(",") if s.strip()]
    bad = [s for s in names if s not in STYLES]
    if bad:
        print(f"[rotate] unknown styles {bad} ignored", file=sys.stderr)
    return [s for s in names if s in STYLES] or ["nothing"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", choices=["bw", "e6"], required=True)
    ap.add_argument("--no-deploy", action="store_true")
    args = ap.parse_args()

    names = playlist(args.panel)
    state = config.OUT_DIR / f".rotate_{args.panel}"
    last = state.read_text().strip() if state.exists() else ""
    idx = (names.index(last) + 1) % len(names) if last in names else 0
    style = names[idx]

    panel = get_panel(args.panel)
    ctx = build_ctx()
    out = config.OUT_DIR / f"{args.panel}_current.png"
    try:
        img = STYLES[style](panel, ctx)
    except Exception as exc:  # noqa: BLE001
        print(f"[rotate] style {style} failed ({type(exc).__name__}: {exc}); "
              f"falling back to nothing", file=sys.stderr)
        style = "nothing"
        img = STYLES[style](panel, ctx)
    paths = panel.export(img, out)
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(style)
    print(f"[rotate] panel={args.panel} style={style} → {paths[0].name}")

    if not args.no_deploy:
        from .deploy import deploy
        deploy(args.panel, paths[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
