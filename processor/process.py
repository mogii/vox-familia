"""CLI fallback: process a single video without the web server.

Most of the time you'll just let the iPhone trigger the server and review on
the phone. This one's handy for testing the pipeline without a phone in the
loop.

    python process.py 我的视频.mp4

Writes a fresh job under JOBS_DIR/<id>/, same layout as the server creates.
After it finishes, run `python server.py` and visit / to review.
"""

import argparse
import os
import shutil

import config
import jobs
import pipeline


def main():
    ap = argparse.ArgumentParser(description="视频 → 一个新的待审 job")
    ap.add_argument("video", help="视频文件路径")
    ap.add_argument("--frames", type=int, default=config.FRAMES_PER_ITEM)
    ap.add_argument("--fps", type=float, default=config.SAMPLE_FPS)
    args = ap.parse_args()

    if not os.path.isfile(args.video):
        raise SystemExit(f"找不到视频文件：{args.video}")

    name = os.path.basename(args.video)
    job_id = jobs.create_job(name)
    target = os.path.join(jobs.job_dir(job_id), name)
    shutil.copyfile(args.video, target)
    print(f"[ok] 新建 job {job_id}，开始处理...")

    pipeline.run(
        jobs.job_dir(job_id),
        target,
        lambda patch: jobs.patch_state(job_id, patch),
        frames_per_item=args.frames,
        sample_fps=args.fps,
    )
    print(f"[done] 跑 `python server.py` 然后打开 / 即可审。job id = {job_id}")


if __name__ == "__main__":
    main()
