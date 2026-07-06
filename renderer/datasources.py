"""Data feeding the info styles: HA sensor states, weather, news.

Everything degrades gracefully: no HA token → placeholders, no news bridge →
empty list. A style must never crash because a source is down.
"""

from __future__ import annotations

import sys

import requests

from . import config


def fetch_states() -> dict[str, dict]:
    if not config.HA_URL or not config.HA_TOKEN:
        print("[data] HA_URL/HA_TOKEN not set — rendering with placeholders", file=sys.stderr)
        return {}
    try:
        r = requests.get(f"{config.HA_URL}/api/states",
                         headers={"Authorization": f"Bearer {config.HA_TOKEN}"},
                         timeout=12, verify=not config.HA_URL.startswith("https"))
        r.raise_for_status()
        return {s["entity_id"]: s for s in r.json()}
    except Exception as exc:  # noqa: BLE001
        print(f"[data] states fetch failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return {}


def state(states: dict, key: str) -> str | None:
    s = states.get(config.ENTITIES.get(key, key))
    if not s:
        return None
    v = s.get("state")
    return None if v in (None, "unknown", "unavailable", "") else v


def attr(states: dict, key: str, name: str) -> float | None:
    s = states.get(config.ENTITIES.get(key, key))
    if not s:
        return None
    v = s.get("attributes", {}).get(name)
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def num(v, fmt: str = "%.1f") -> str:
    try:
        return fmt % float(v)
    except (TypeError, ValueError):
        return "--"


def f(v) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def weather_summary(states: dict) -> dict:
    cond = state(states, "weather") or "cloudy"
    return {
        "condition": cond,
        "cn": config.WEATHER_CN.get(cond, "--"),
        "icon": config.WEATHER_ICON.get(cond, "cloud"),
        "temp": attr(states, "weather", "temperature"),
    }


def fetch_news(limit: int = 6) -> list[dict]:
    """Top headlines via the optional FreshRSS bridge (EINK_NEWS_BRIDGE_DIR)."""
    if not config.NEWS_BRIDGE_DIR:
        return []
    try:
        sys.path.insert(0, config.NEWS_BRIDGE_DIR)
        import freshrss_bridge  # type: ignore

        items, _ = freshrss_bridge.fetch_top(limit=limit, pad=True)
        return items or []
    except Exception as exc:  # noqa: BLE001
        print(f"[data] news unavailable ({type(exc).__name__}); skipping", file=sys.stderr)
        return []
