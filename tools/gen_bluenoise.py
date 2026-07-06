#!/usr/bin/env python3
"""Generate the blue-noise threshold texture used by EINK_DITHER=bluenoise.

Ulichney void-and-cluster on a 64x64 torus: start from a relaxed random binary
pattern, then rank every cell by repeatedly removing the tightest cluster
(below the seed density) and filling the largest void (above it). The rank
map, scaled to 0..255, is a tileable threshold matrix whose spectrum has no
low-frequency energy — dithering with it looks like film grain instead of the
crosshatch patterns Bayer produces.

Run once; the committed PNG (renderer/assets/bluenoise64.png) is the artifact:
  .venv/bin/python tools/gen_bluenoise.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

N = 64
SIGMA = 1.9
OUT = Path(__file__).resolve().parent.parent / "renderer" / "assets" / "bluenoise64.png"


def energy(pattern: np.ndarray) -> np.ndarray:
    """Toroidal Gaussian-filtered density (FFT convolution, wraps at edges)."""
    idx = np.arange(N)
    d = np.minimum(idx, N - idx)
    Y, X = np.meshgrid(d, d, indexing="ij")
    kernel = np.exp(-(X ** 2 + Y ** 2) / (2 * SIGMA ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(pattern) * np.fft.fft2(kernel)))


def main() -> None:
    rng = np.random.default_rng(20260706)
    total = N * N
    seeds = total // 10

    # phase 0: relax random seeds until swap-stable
    pat = np.zeros((N, N))
    pat.flat[rng.choice(total, seeds, replace=False)] = 1
    while True:
        cluster = np.argmax(np.where(pat == 1, energy(pat), -np.inf))
        pat.flat[cluster] = 0
        void = np.argmin(np.where(pat == 0, energy(pat), np.inf))
        pat.flat[void] = 1
        if void == cluster:
            break

    rank = np.zeros(total, dtype=int)

    # phase 1: peel seeds off (ranks seeds-1 .. 0)
    p = pat.copy()
    for r in range(seeds - 1, -1, -1):
        cluster = np.argmax(np.where(p == 1, energy(p), -np.inf))
        p.flat[cluster] = 0
        rank[cluster] = r

    # phase 2: fill voids up to full (ranks seeds .. total-1)
    p = pat.copy()
    for r in range(seeds, total):
        void = np.argmin(np.where(p == 0, energy(p), np.inf))
        p.flat[void] = 1
        rank[void] = r

    thresholds = ((rank.reshape(N, N) + 0.5) * 256.0 / total).clip(0, 255).astype(np.uint8)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(thresholds, "L").save(OUT)
    print(f"wrote {OUT} ({N}x{N})")


if __name__ == "__main__":
    main()
