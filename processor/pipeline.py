"""End-to-end: video file → listings (transcript, frame candidates, AI fields).

This is the shared core used by both the CLI (process.py) and the web server
(server.py). It writes incremental progress into the job's state.json so the
web page can show what's happening without polling external state.
"""

import os

import config
import frames
from enrich import enrich
from segment import find_items
from transcribe import transcribe


def run(job_dir, video_path, save_state, frames_per_item=None, sample_fps=None):
    """Process one video. `save_state(patch)` is called repeatedly to update
    job state on disk (the patch is merged into the existing state.json).
    """
    frames_per_item = frames_per_item or config.FRAMES_PER_ITEM
    sample_fps = sample_fps or config.SAMPLE_FPS

    save_state({"stage": "transcribing", "message": "在转写..."})
    words, full_text = transcribe(video_path)
    save_state({"transcript": full_text})

    save_state({"stage": "segmenting", "message": "按『下一件』切段..."})
    items = find_items(words, triggers=config.TRIGGERS)

    listings = [_blank_listing(item) for item in items]
    save_state({"stage": "extracting", "message": "抽帧并打分...",
                "listings": listings, "total": len(items)})

    items_dir = os.path.join(job_dir, "items")
    for i, item in enumerate(items):
        prefix = f"item{i + 1:02d}"
        item_dir = os.path.join(items_dir, str(i))
        cands = frames.extract_all(
            video_path, item["start"], item["end"], sample_fps, item_dir, prefix,
        )
        listings[i]["candidates"] = [
            {"filename": c["filename"], "sharpness": c["sharpness"]} for c in cands
        ]
        listings[i]["selected"] = frames.default_selection(cands, frames_per_item)
        save_state({"listings": listings, "progress": {"done": i + 1, "total": len(items)}})

    client = None
    if config.ANTHROPIC_API_KEY:
        import anthropic

        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    for i, item in enumerate(items):
        save_state({"stage": "enriching",
                    "message": f"AI 整理中 {i + 1}/{len(items)}...",
                    "progress": {"done": i, "total": len(items)}})
        if client is not None:
            try:
                info = enrich(item["text"], client=client)
            except Exception as e:
                info = {"title": "宝宝闲置", "price": None, "condition": None,
                        "description": item["text"], "error": str(e)}
        else:
            info = {"title": "宝宝闲置", "price": None, "condition": None,
                    "description": item["text"]}
        listings[i].update(
            {
                "title": info.get("title") or "宝宝闲置",
                "price": info.get("price"),
                "condition": info.get("condition"),
                "description": info.get("description") or item["text"],
            }
        )
        save_state({"listings": listings})

    save_state({"stage": "done", "message": "处理完成", "listings": listings,
                "progress": {"done": len(items), "total": len(items)}})


def _blank_listing(item):
    return {
        "title": "",
        "price": None,
        "condition": None,
        "description": "",
        "contact": config.CONTACT,
        "transcript": item["text"],
        "start": item["start"],
        "end": item["end"],
        "candidates": [],   # filled after frame extraction
        "selected": [],     # indices into candidates
    }
