"""Local web server: phone uploads a video, browser reviews & exports.

Single-user, LAN-only. Run with:
    uvicorn server:app --host 0.0.0.0 --port 8000
or just:
    python server.py
"""

import asyncio
import os
from typing import Optional

from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Path,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import compose
import config
import jobs
import pipeline

app = FastAPI(title="vox-familia")

ROOT = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(ROOT, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(ROOT, "static")), name="static")

WORKER_LOCK = asyncio.Lock()

# job id 只可能是 jobs.new_id() 产的 10 位十六进制；在路由层就把
# 不合法的拦掉（404/422），防止拼出 jobs/ 目录以外的路径。
JOB_ID = Path(pattern=r"^[0-9a-f]{10}$")


# ---------- auth ----------

def _check_token(request: Request, t: Optional[str] = None):
    """Accept token via ?t=... or `Authorization: Bearer ...`. If SERVER_TOKEN
    is empty (default in .env), auth is disabled — fine for trusted home Wi-Fi.
    """
    expected = config.SERVER_TOKEN
    if not expected:
        return
    auth = request.headers.get("authorization", "")
    bearer = auth.split(" ", 1)[1] if auth.lower().startswith("bearer ") else None
    given = bearer or t
    if given != expected:
        raise HTTPException(status_code=401, detail="bad token")


# ---------- background worker ----------

async def _run_worker(job_id: str):
    async with WORKER_LOCK:
        st = jobs.read_state(job_id)
        if not st:
            return
        video_path = os.path.join(jobs.job_dir(job_id), st["video_filename"])
        try:
            await asyncio.to_thread(
                pipeline.run,
                jobs.job_dir(job_id),
                video_path,
                lambda patch: jobs.patch_state(job_id, patch),
            )
        except Exception as e:
            jobs.patch_state(job_id, {"stage": "error", "message": f"出错：{e}"})


# ---------- pages ----------

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, _: None = Depends(_check_token)):
    active, others = jobs.current_active()
    return templates.TemplateResponse(
        request,
        "job.html",
        {
            "active": active,
            "history": others[:10],
            "currency": config.CURRENCY_SYMBOL,
            "token": config.SERVER_TOKEN,
            "conditions": ["全新", "9成新", "8成新", "7成新及以下"],
            "save_shortcut": config.SAVE_SHORTCUT_NAME,
        },
    )


@app.get("/j/{job_id}", response_class=HTMLResponse)
async def view_job(request: Request, job_id: str = JOB_ID, _: None = Depends(_check_token)):
    """Look at a specific (older) job, e.g. from the history list."""
    state = jobs.read_state(job_id)
    if not state:
        raise HTTPException(404, "no such job")
    _active, others = jobs.current_active()
    return templates.TemplateResponse(
        request,
        "job.html",
        {
            "active": state,
            "history": [j for j in others if j["id"] != job_id][:10],
            "currency": config.CURRENCY_SYMBOL,
            "token": config.SERVER_TOKEN,
            "conditions": ["全新", "9成新", "8成新", "7成新及以下"],
            "save_shortcut": config.SAVE_SHORTCUT_NAME,
        },
    )


# ---------- upload ----------

@app.post("/upload")
async def upload(
    request: Request, file: UploadFile, _: None = Depends(_check_token),
):
    name = file.filename or "video.mov"
    # Keep the original filename inside the job dir, but make sure it's safe.
    safe = "".join(c for c in name if c.isalnum() or c in ("-", "_", ".")) or "video.mov"
    job_id = jobs.create_job(safe)
    target = os.path.join(jobs.job_dir(job_id), safe)
    with open(target, "wb") as fh:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    asyncio.create_task(_run_worker(job_id))
    return {"ok": True, "id": job_id}


# ---------- JSON API ----------

@app.get("/status.json")
async def status_json(_: None = Depends(_check_token)):
    active, _others = jobs.current_active()
    return {
        "active": (
            {
                "id": active["id"],
                "stage": active.get("stage"),
                "message": active.get("message"),
                "progress": active.get("progress"),
                "updated_at": active.get("updated_at"),
            }
            if active
            else None
        ),
    }


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str = JOB_ID, _: None = Depends(_check_token)):
    state = jobs.read_state(job_id)
    if not state:
        raise HTTPException(404, "no such job")
    return state


@app.patch("/api/jobs/{job_id}/listings/{n}")
async def patch_listing(
    job_id: str = JOB_ID, n: int = Path(), body: dict = None, _: None = Depends(_check_token),
):
    state = jobs.read_state(job_id)
    if not state:
        raise HTTPException(404, "no such job")
    listings = state.get("listings", [])
    if not (0 <= n < len(listings)):
        raise HTTPException(404, "no such listing")
    allowed = {"title", "price", "condition", "description", "contact", "selected",
               "captions", "marketPrice", "marketPriceText", "marketSource"}
    for k, v in (body or {}).items():
        if k in allowed:
            listings[n][k] = v
    # Invalidate any cached poster for this listing.
    p = os.path.join(jobs.job_dir(job_id), "posters", f"{n}.jpg")
    if os.path.exists(p):
        os.remove(p)
    jobs.patch_state(job_id, {"listings": listings})
    return {"ok": True}


# ---------- image serving ----------

@app.get("/jobs/{job_id}/items/{n}/{filename}")
async def serve_frame(
    job_id: str = JOB_ID, n: int = Path(), filename: str = Path(), _: None = Depends(_check_token),
):
    if "/" in filename or filename.startswith("."):
        raise HTTPException(400, "bad filename")
    base = os.path.realpath(os.path.join(jobs.job_dir(job_id), "items", str(n)))
    path = os.path.realpath(os.path.join(base, filename))
    # 圈地检查：解析符号链接后必须还在这个 item 目录里。
    if not path.startswith(base + os.sep) or not os.path.isfile(path):
        raise HTTPException(404, "no such image")
    return FileResponse(path, media_type="image/jpeg")


@app.get("/jobs/{job_id}/posters/{n}.jpg")
async def serve_poster(job_id: str = JOB_ID, n: int = Path(), _: None = Depends(_check_token)):
    state = jobs.read_state(job_id)
    if not state:
        raise HTTPException(404, "no such job")
    listings = state.get("listings", [])
    if not (0 <= n < len(listings)):
        raise HTTPException(404, "no such listing")
    listing = listings[n]
    if not listing.get("selected"):
        raise HTTPException(400, "请先选一张图")
    item_dir = os.path.join(jobs.job_dir(job_id), "items", str(n))

    out_path = os.path.join(jobs.job_dir(job_id), "posters", f"{n}.jpg")
    if not os.path.isfile(out_path):
        try:
            compose.render_to(out_path, item_dir, listing,
                              currency=config.CURRENCY_SYMBOL)
        except ValueError as e:
            raise HTTPException(400, str(e))
    return FileResponse(out_path, media_type="image/jpeg")


# ---------- export endpoints for the Save-to-Photos Shortcut ----------

def _abs_url(request: Request, path: str) -> str:
    base = config.PUBLIC_BASE_URL.rstrip("/") if config.PUBLIC_BASE_URL else str(request.base_url).rstrip("/")
    return f"{base}{path}"


def _listing_urls(request, job_id, n, listing, kind, qs):
    """The image URLs the Save-to-Photos Shortcut should fetch for one listing."""
    urls = []
    if kind == "originals":
        for idx in listing.get("selected", []):
            if 0 <= idx < len(listing.get("candidates", [])):
                f = listing["candidates"][idx]["filename"]
                urls.append(_abs_url(request, f"/jobs/{job_id}/items/{n}/{f}{qs}"))
    elif listing.get("selected"):  # 没勾图的件出不了长图，跳过
        urls.append(_abs_url(request, f"/jobs/{job_id}/posters/{n}.jpg{qs}"))
    return urls


@app.get("/jobs/{job_id}/listings/{n}/export.json")
async def export_json(
    request: Request,
    job_id: str = JOB_ID,
    n: int = Path(),
    kind: str = Query("originals", pattern="^(originals|poster)$"),
    _: None = Depends(_check_token),
):
    state = jobs.read_state(job_id)
    if not state:
        raise HTTPException(404, "no such job")
    listings = state.get("listings", [])
    if not (0 <= n < len(listings)):
        raise HTTPException(404, "no such listing")
    qs = f"?t={config.SERVER_TOKEN}" if config.SERVER_TOKEN else ""
    return JSONResponse(_listing_urls(request, job_id, n, listings[n], kind, qs))


@app.get("/jobs/{job_id}/export.json")
async def export_all_json(
    request: Request,
    job_id: str = JOB_ID,
    kind: str = Query("originals", pattern="^(originals|poster)$"),
    _: None = Depends(_check_token),
):
    """整个视频一次性导出：所有件的原图，或每件一张成品长图。"""
    state = jobs.read_state(job_id)
    if not state:
        raise HTTPException(404, "no such job")
    urls = []
    qs = f"?t={config.SERVER_TOKEN}" if config.SERVER_TOKEN else ""
    for n, listing in enumerate(state.get("listings", [])):
        urls.extend(_listing_urls(request, job_id, n, listing, kind, qs))
    return JSONResponse(urls)


# ---------- entrypoint ----------

@app.get("/healthz", response_class=PlainTextResponse)
async def healthz():
    return "ok"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "server:app",
        host=config.SERVER_HOST,
        port=config.SERVER_PORT,
        reload=False,
        # 访问日志会把带 ?t=<token> 的 URL 打到终端/日志里，关掉。
        access_log=False,
    )
