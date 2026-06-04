"""Pull candidate frames from a video time range, score them, and pick a default.

All candidates are saved so the phone UI can toggle un-picked ones back in.
Sharpness = variance of a Laplacian via numpy/Pillow (no OpenCV needed).
"""

import os
import shutil
import subprocess

import numpy as np
from PIL import Image


def _ffmpeg_exe():
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        exe = shutil.which("ffmpeg")
        if not exe:
            raise SystemExit(
                "找不到 ffmpeg。请 `pip install imageio-ffmpeg`，或自行安装 ffmpeg。"
            )
        return exe


def _sharpness(path):
    img = Image.open(path).convert("L")
    img.thumbnail((640, 640))
    a = np.asarray(img, dtype=np.float64)
    lap = (
        -4 * a
        + np.roll(a, 1, 0)
        + np.roll(a, -1, 0)
        + np.roll(a, 1, 1)
        + np.roll(a, -1, 1)
    )
    return float(lap.var())


def extract_all(video, start, end, sample_fps, dest_dir, prefix):
    """Sample frames across [start, end] and save them all to dest_dir.

    Returns a time-ordered list of {"path", "filename", "sharpness"}.
    """
    os.makedirs(dest_dir, exist_ok=True)
    duration = max(0.4, float(end) - float(start))
    pattern = os.path.join(dest_dir, f"{prefix}_%03d.jpg")
    subprocess.run(
        [
            _ffmpeg_exe(),
            "-hide_banner", "-loglevel", "error",
            "-i", video,
            "-ss", f"{float(start):.3f}",
            "-t", f"{duration:.3f}",
            "-vf", f"fps={sample_fps}",
            "-q:v", "2",
            pattern,
        ],
        check=True,
    )
    files = sorted(f for f in os.listdir(dest_dir) if f.startswith(prefix + "_"))
    return [
        {
            "filename": f,
            "path": os.path.join(dest_dir, f),
            "sharpness": _sharpness(os.path.join(dest_dir, f)),
        }
        for f in files
    ]


def default_selection(candidates, count):
    """Choose up to `count` indices into `candidates` that are sharp and spread out.

    Returns a sorted list of indices (in time order).
    """
    if not candidates:
        return []
    n = len(candidates)
    by_score = sorted(range(n), key=lambda i: candidates[i]["sharpness"], reverse=True)
    pool = by_score[: max(count, (n * 2) // 3)]  # drop blurriest third
    min_gap = max(1, n // (count + 1))
    chosen = []
    for i in pool:
        if all(abs(i - c) >= min_gap for c in chosen):
            chosen.append(i)
        if len(chosen) >= count:
            break
    if len(chosen) < count:
        for i in pool:
            if i not in chosen:
                chosen.append(i)
            if len(chosen) >= count:
                break
    return sorted(chosen)
