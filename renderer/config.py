"""Central configuration: env, paths, panel targets, HA entity map, palettes.

Everything an agent needs to adapt this project to a new home lives here:
  - ENTITIES: swap in your own HA entity IDs
  - PANELS (in panels.py): add/adjust panel hardware targets
  - env vars: see .env.example at the repo root
"""

from __future__ import annotations

import os
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FONT_DIR = REPO / "fonts"
OUT_DIR = REPO / "out"
CACHE_DIR = OUT_DIR / "cache"

W, H = 800, 480  # both supported panels are 800x480

# ── Home Assistant ────────────────────────────────────────────────────────────
HA_URL = (os.getenv("HA_URL") or os.getenv("HA_EXTERNAL_URL") or "").rstrip("/")
HA_TOKEN = os.getenv("HA_TOKEN") or ""

# HA entity IDs used by the info styles. Replace with your own; any entity that
# is missing/unavailable renders as "--" instead of failing.
ENTITIES = {
    "temp": "sensor.xiaomi_cn_2008215373_ua3a_temperature_p_3_7",
    "humidity": "sensor.xiaomi_cn_2008215373_ua3a_relative_humidity_p_3_1",
    "pm25": "sensor.xiaomi_cn_2008215373_ua3a_pm2_5_density_p_3_4",
    "co2": "sensor.xiaomi_cn_2008215373_ua3a_co2_density_p_3_8",
    "hcho": "sensor.xiaomi_cn_2008215373_ua3a_hcho_density_p_3_10",  # mg/m³
    "lock_batt": "sensor.lumi_cn_1011935590_bzacn1_battery_level_p_4_1",
    "weather": "weather.forecast_wo_de_jia",
    "cat_waste": "binary_sensor.zhi_neng_mao_ce_suo_max_wastebin_filled",
    "cat_sand": "binary_sensor.zhi_neng_mao_ce_suo_max_sand_lack",
    "water_lack": "binary_sensor.yin_shui_ji_max_zhen_wu_xian_water_lack_warning",
}

WEATHER_CN = {
    "sunny": "晴", "clear-night": "晴", "partlycloudy": "多云", "cloudy": "阴",
    "rainy": "小雨", "pouring": "大雨", "snowy": "雪", "fog": "雾",
    "lightning": "雷阵雨", "lightning-rainy": "雷雨", "windy": "大风",
    "windy-variant": "大风", "hail": "冰雹", "exceptional": "异常",
}
WEATHER_ICON = {
    "sunny": "sun", "clear-night": "moon", "partlycloudy": "cloud", "cloudy": "cloud",
    "rainy": "rain", "pouring": "rain", "snowy": "snow", "fog": "cloud",
    "lightning": "rain", "lightning-rainy": "rain", "windy": "cloud",
    "windy-variant": "cloud", "hail": "rain",
}
EN_WD = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
CN_WD = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
EN_MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

# ── Photos ────────────────────────────────────────────────────────────────────
# bing | nas | picsum | ai   (see imagesource.py)
PHOTO_SOURCE = (os.getenv("EINK_PHOTO_SOURCE") or "bing").lower()
NAS_PHOTO_DIR = os.getenv("EINK_NAS_PHOTO_DIR") or ""

# ── News ──────────────────────────────────────────────────────────────────────
# Optional FreshRSS bridge (reuses /root/ha the_daily scorer). Point at the
# directory that contains freshrss_bridge.py, or leave empty to disable news.
NEWS_BRIDGE_DIR = os.getenv("EINK_NEWS_BRIDGE_DIR") or ""

# ── AI (claude / codex CLI) ───────────────────────────────────────────────────
# claude | codex | none. Empty = auto-detect (claude, then codex, then none).
AI_BACKEND = (os.getenv("EINK_AI_BACKEND") or "").lower()
AI_TIMEOUT = int(os.getenv("EINK_AI_TIMEOUT") or "180")
# Optional custom image-gen command template with {prompt} and {out} placeholders,
# e.g. a script that calls your preferred image model. Default uses codex.
IMAGEGEN_CMD = os.getenv("EINK_IMAGEGEN_CMD") or ""

# ── Deploy target (HA /config/www, served at /local/...) ─────────────────────
SSH_HOST = os.getenv("HA_SSH_HOST") or ""
SSH_USER = os.getenv("HA_SSH_USER") or "hassio"
SSH_PASSWORD = os.getenv("HA_SSH_PASSWORD") or ""
REMOTE_DIR = os.getenv("EINK_REMOTE_DIR") or "/config/www/eink"
