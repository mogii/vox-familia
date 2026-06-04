"""On-disk job store.

Each job is a directory under JOBS_DIR/<id>/ containing:
    video.<ext>      uploaded video
    state.json       current state (stage, listings, etc.)
    items/<n>/*.jpg  candidate frames
    posters/<n>.jpg  composed posters (lazily rendered)
"""

import json
import os
import threading
import time
import uuid

import config

_LOCK = threading.Lock()


def _root():
    os.makedirs(config.JOBS_DIR, exist_ok=True)
    return config.JOBS_DIR


def new_id():
    return uuid.uuid4().hex[:10]


def job_dir(job_id):
    return os.path.join(_root(), job_id)


def state_path(job_id):
    return os.path.join(job_dir(job_id), "state.json")


def write_state(job_id, state):
    path = state_path(job_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def read_state(job_id):
    try:
        with open(state_path(job_id), encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None


def patch_state(job_id, patch):
    """Merge `patch` into the job's state.json. Thread-safe across the process."""
    with _LOCK:
        state = read_state(job_id) or {}
        state.update(patch)
        state["updated_at"] = int(time.time())
        write_state(job_id, state)
        return state


def create_job(video_filename):
    job_id = new_id()
    os.makedirs(job_dir(job_id), exist_ok=True)
    write_state(
        job_id,
        {
            "id": job_id,
            "video_filename": video_filename,
            "stage": "queued",
            "message": "排队中...",
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            "listings": [],
        },
    )
    return job_id


def list_jobs():
    """Return all jobs sorted newest first."""
    root = _root()
    if not os.path.isdir(root):
        return []
    out = []
    for name in os.listdir(root):
        st = read_state(name)
        if st and "created_at" in st:
            out.append(st)
    out.sort(key=lambda s: s.get("created_at", 0), reverse=True)
    return out


def current_active():
    """Pick the job to show on the home page.

    Precedence:
      1. An in-progress job (queued / transcribing / segmenting / extracting / enriching)
      2. The most recently completed job
      3. None (nothing to show)
    """
    jobs = list_jobs()
    active_stages = {"queued", "transcribing", "segmenting", "extracting", "enriching"}
    for j in jobs:
        if j.get("stage") in active_stages:
            return j, [k for k in jobs if k["id"] != j["id"]]
    for j in jobs:
        if j.get("stage") in ("done", "error"):
            return j, [k for k in jobs if k["id"] != j["id"]]
    return None, jobs
