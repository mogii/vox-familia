"""Pull candidate frames from a video time range and keep the sharpest few.

Uses the ffmpeg binary bundled with the pip package imageio-ffmpeg, so there's
nothing to install system-wide. Sharpness = variance of a Laplacian, computed
with numpy/Pillow (no OpenCV needed).
"""

import os
import shutil
import subprocess
import tempfile

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
    # Downscale large frames so the metric is fast and resolution-agnostic.
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


def _extract_candidates(video, start, end, fps, tmpdir):
    duration = max(0.4, float(end) - float(start))
    out_pattern = os.path.join(tmpdir, "cand_%04d.jpg")
    cmd = [
        _ffmpeg_exe(),
        "-hide_banner",
        "-loglevel", "error",
        "-i", video,
        "-ss", f"{float(start):.3f}",
        "-t", f"{duration:.3f}",
        "-vf", f"fps={fps}",
        "-q:v", "2",
        out_pattern,
    ]
    subprocess.run(cmd, check=True)
    return sorted(
        os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.startswith("cand_")
    )


def best_frames(video, start, end, count, sample_fps, dest_dir, prefix):
    """Extract, score, and save up to `count` sharp, time-spread frames.

    Returns the list of saved file paths.
    """
    os.makedirs(dest_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        candidates = _extract_candidates(video, start, end, sample_fps, tmp)
        if not candidates:
            return []

        scored = [(p, _sharpness(p)) for p in candidates]
        # Drop the blurriest third before spacing, so we don't pick smudges.
        scored.sort(key=lambda x: x[1], reverse=True)
        keep = scored[: max(count, (len(scored) * 2) // 3)]

        # Greedily pick highest-scoring frames that aren't time-adjacent, so we
        # get variety (different angles) instead of near-duplicate frames.
        order = {p: i for i, p in enumerate(candidates)}
        keep.sort(key=lambda x: x[1], reverse=True)
        min_gap = max(1, len(candidates) // (count + 1))
        chosen = []
        for path, _ in keep:
            idx = order[path]
            if all(abs(idx - order[c]) >= min_gap for c in chosen):
                chosen.append(path)
            if len(chosen) >= count:
                break
        # If spacing was too strict to fill the quota, top up by score.
        if len(chosen) < count:
            for path, _ in keep:
                if path not in chosen:
                    chosen.append(path)
                if len(chosen) >= count:
                    break

        chosen.sort(key=lambda p: order[p])  # back into time order
        saved = []
        for j, path in enumerate(chosen, 1):
            out = os.path.join(dest_dir, f"{prefix}_{j}.jpg")
            shutil.copyfile(path, out)
            saved.append(out)
        return saved
