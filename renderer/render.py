#!/usr/bin/env python3
"""Render one dashboard frame.

  set -a && source .env && set +a
  .venv/bin/python -m renderer.render --panel e6 --style nothing [--out PATH]

Writes out/<panel>_<style>.png plus, when the device image differs from what a
human should preview (E6 quantised colours, B/W pre-invert), a *_preview.png.
Use --deploy to also push the device PNG to HA in one step.
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from . import config, datasources
from .panels import get_panel
from .styles import STYLES


def build_ctx() -> SimpleNamespace:
    return SimpleNamespace(
        now=datetime.now(),
        states=datasources.fetch_states(),
        news=datasources.fetch_news(),
    )


def render_frame(panel_name: str, style_name: str, out: Path | None = None) -> list[Path]:
    panel = get_panel(panel_name)
    ctx = build_ctx()
    img = STYLES[style_name](panel, ctx)
    out = out or config.OUT_DIR / f"{panel_name}_{style_name}.png"
    paths = panel.export(img, out)
    print(f"[render] {style_name} → {', '.join(p.name for p in paths)} "
          f"(states={len(ctx.states)} news={len(ctx.news)})")
    return paths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", choices=["bw", "e6"], required=True)
    ap.add_argument("--style", choices=sorted(STYLES), default="nothing")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--deploy", action="store_true", help="push the device PNG to HA after rendering")
    args = ap.parse_args()

    paths = render_frame(args.panel, args.style, args.out)
    if args.deploy:
        from .deploy import deploy
        deploy(args.panel, paths[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
