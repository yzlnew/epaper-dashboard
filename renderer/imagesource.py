"""Photo sources for the image styles: Bing wallpaper, NAS folder, Picsum, AI.

fetch_photo() returns (PIL RGB image, caption hint). The caller pushes it
through panel.prepare_photo() to dither it into the panel's gamut. Failures
raise — styles catch and fall back to a photo-free layout.

Sources (EINK_PHOTO_SOURCE):
  bing   — Bing daily wallpaper, random pick from the last 8 days (no key)
  nas    — random image from a local/NAS directory (EINK_NAS_PHOTO_DIR),
           e.g. an NFS/SMB mount like /mnt/fnOS/photos
  picsum — Lorem Picsum random photo (no key)
  ai     — daily generated artwork via the AI image backend (see ai.py);
           cached per day so cron reruns don't regenerate
"""

from __future__ import annotations

import io
import random
import sys
from datetime import date
from pathlib import Path

import requests
from PIL import Image

from . import ai, config

UA = {"User-Agent": "Mozilla/5.0 (epaper-dashboard)"}
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def _bing() -> tuple[Image.Image, str]:
    idx = random.randint(0, 7)
    r = requests.get("https://www.bing.com/HPImageArchive.aspx",
                     params={"format": "js", "idx": idx, "n": 1, "mkt": "zh-CN"},
                     headers=UA, timeout=12)
    r.raise_for_status()
    info = r.json()["images"][0]
    img = requests.get("https://www.bing.com" + info["url"], headers=UA, timeout=25)
    img.raise_for_status()
    title = (info.get("copyright") or "").split("(")[0].strip()
    return Image.open(io.BytesIO(img.content)).convert("RGB"), title


def _nas() -> tuple[Image.Image, str]:
    root = Path(config.NAS_PHOTO_DIR)
    if not config.NAS_PHOTO_DIR or not root.is_dir():
        raise FileNotFoundError(f"EINK_NAS_PHOTO_DIR not set or missing: {root}")
    files = [p for p in root.rglob("*")
             if p.suffix.lower() in IMG_EXT and p.stat().st_size > 30_000]
    if not files:
        raise FileNotFoundError(f"no images under {root}")
    pick = random.choice(files)
    return Image.open(pick).convert("RGB"), pick.stem.replace("_", " ")


def _picsum() -> tuple[Image.Image, str]:
    r = requests.get(f"https://picsum.photos/{config.W}/{config.H}", headers=UA, timeout=25)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGB"), ""


AI_ART_PROMPT = (
    "一幅适合 800x480 电子墨水屏展示的横幅插画，构图简洁、色块分明、"
    "少量大面积纯色（黑/白/红/黄/蓝/绿为主），主题：{theme}。"
    "扁平插画风格，不要过多渐变和细碎纹理。"
)
AI_THEMES = ["四季山水", "城市清晨", "猫与窗台", "星空与山脉", "海边灯塔",
             "雨后街道", "书房一角", "远山与飞鸟"]


def _ai() -> tuple[Image.Image, str]:
    out = config.CACHE_DIR / f"aiart-{date.today().isoformat()}.png"
    if not out.exists():
        theme = AI_THEMES[date.today().toordinal() % len(AI_THEMES)]
        ai.generate_image(AI_ART_PROMPT.format(theme=theme), out)
    return Image.open(out).convert("RGB"), "AI ART"


PROVIDERS = {"bing": _bing, "nas": _nas, "picsum": _picsum, "ai": _ai}


def fetch_photo(source: str | None = None) -> tuple[Image.Image, str]:
    src = (source or config.PHOTO_SOURCE).lower()
    provider = PROVIDERS.get(src)
    if provider is None:
        print(f"[photo] unknown source {src!r}, using bing", file=sys.stderr)
        provider = _bing
    return provider()
