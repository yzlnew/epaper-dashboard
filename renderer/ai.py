"""AI text/image via local agent CLIs (claude / codex) — no API keys wired here;
the CLIs bring their own auth.

Used for the "personalised" parts of a dashboard that a plain cron render can't
produce: a written morning brief, a one-line remark about the weather, a caption
describing today's photo, or a generated artwork.

Backends (EINK_AI_BACKEND=claude|codex|none, empty = auto-detect):
  claude — `claude -p "<prompt>"`; image captions pass the file path in the
           prompt with the Read tool allowed.
  codex  — `codex exec`; image captions use `-i <path>`; image generation asks
           the agent to use its imagegen tooling and save to the target path.

All calls go through cached_text()/generate_image() with a per-day file cache,
so a 10-minute cron doesn't re-pay an agent call on every tick. Failures raise;
styles catch and render their non-AI fallback.
"""

from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

from . import config


def backend() -> str:
    b = config.AI_BACKEND
    if b in ("claude", "codex", "none"):
        return b
    if shutil.which("claude"):
        return "claude"
    if shutil.which("codex"):
        return "codex"
    return "none"


def _run(cmd: list[str], cwd: str | None = None) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True,
                       timeout=config.AI_TIMEOUT, cwd=cwd)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed rc={r.returncode}: {r.stderr.strip()[:300]}")
    return r.stdout.strip()


def _claude(prompt: str, extra: list[str] | None = None) -> str:
    # --output-format json isolates the reply in .result — plain stdout can
    # carry harness notice lines that would pollute the rendered text
    import json

    raw = _run(["claude", "-p", prompt, "--output-format", "json", *(extra or [])])
    try:
        return (json.loads(raw).get("result") or "").strip()
    except json.JSONDecodeError:
        return raw


def _codex_exec(prompt: str, extra: list[str] | None = None, cwd: str | None = None) -> str:
    out_file = config.CACHE_DIR / ".codex_last_message.txt"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["codex", "exec", "--skip-git-repo-check",
           "--output-last-message", str(out_file), *(extra or []), prompt]
    _run(cmd, cwd=cwd)
    return out_file.read_text().strip() if out_file.exists() else ""


def text(prompt: str) -> str:
    """One-shot text generation. Returns the model's reply, stripped."""
    b = backend()
    if b == "claude":
        return _claude(prompt)
    if b == "codex":
        return _codex_exec(prompt)
    raise RuntimeError("no AI backend available (EINK_AI_BACKEND=none)")


def caption_image(image_path: Path, prompt: str) -> str:
    """Describe an image (e.g. today's photo) in one short sentence."""
    b = backend()
    if b == "claude":
        return _claude(f"{prompt}\n图片文件: {image_path}",
                       extra=["--allowedTools", "Read"])
    if b == "codex":
        return _codex_exec(prompt, extra=["-i", str(image_path)])
    raise RuntimeError("no AI backend available")


def generate_image(prompt: str, out: Path) -> Path:
    """Generate an image to `out`. Uses EINK_IMAGEGEN_CMD if set (a shell
    template with {prompt} and {out}), otherwise asks codex to use its
    imagegen tooling."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if config.IMAGEGEN_CMD:
        cmd = config.IMAGEGEN_CMD.format(prompt=shlex.quote(prompt),
                                         out=shlex.quote(str(out)))
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=config.AI_TIMEOUT)
        if r.returncode != 0:
            raise RuntimeError(f"imagegen cmd failed: {r.stderr.strip()[:300]}")
    elif shutil.which("codex"):
        _codex_exec(
            f"请用你的图片生成工具（imagegen）生成一张图片，并把结果文件保存为 "
            f"{out.name}（保存在当前目录）。图片要求：{prompt}",
            extra=["-s", "workspace-write"], cwd=str(out.parent))
    else:
        raise RuntimeError("no image generation backend (set EINK_IMAGEGEN_CMD or install codex)")
    if not out.exists():
        raise RuntimeError(f"imagegen produced no file at {out}")
    return out


def cached_text(key: str, prompt: str, daily: bool = True) -> str:
    """text() with a file cache. `key` is a slug; daily=True scopes it to today
    so the first cron tick of the day pays the agent call and the rest reuse it."""
    slug = f"{key}-{date.today().isoformat()}" if daily else key
    cache = config.CACHE_DIR / f"{slug}.txt"
    if cache.exists() and cache.read_text().strip():
        return cache.read_text().strip()
    result = text(prompt)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(result)
    return result


def try_cached_text(key: str, prompt: str, fallback: str = "") -> str:
    try:
        return cached_text(key, prompt)
    except Exception as exc:  # noqa: BLE001
        print(f"[ai] {key} unavailable ({type(exc).__name__}: {exc})", file=sys.stderr)
        return fallback
