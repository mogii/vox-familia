"""Local web server: phone uploads a video, browser reviews & exports.

Single-user, LAN-only. Run with:
    uvicorn server:app --host 0.0.0.0 --port 8000
or just:
    python server.py
"""

import asyncio
import io
import os
import zipfile
from typing import List, Optional

from PIL import Image, ImageOps

try:  # iPhone 默认拍 HEIC；装了 pillow-heif 就能直接读
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

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

# 自己打访问日志：只打路径不打 query string（?t=<token> 不能进日志）。
# uvicorn 自带的 access_log 已关。轮询和静态资源太吵，跳过。
_QUIET_PATHS = ("/status.json", "/static", "/healthz")


@app.middleware("http")
async def _access_log(request: Request, call_next):
    response = await call_next(request)
    p = request.url.path
    if not p.startswith(_QUIET_PATHS):
        client = request.client.host if request.client else "?"
        print(f"[req] {client}  {request.method} {p} -> {response.status_code}",
              flush=True)
    return response


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

        def save(patch):
            # 阶段变化同时播报到终端，盯着 server 就能看到进展。
            if "stage" in patch or "message" in patch:
                print(f"[job {job_id}] {patch.get('stage', '')} {patch.get('message', '')}",
                      flush=True)
            jobs.patch_state(job_id, patch)

        try:
            await asyncio.to_thread(pipeline.run, jobs.job_dir(job_id), video_path, save)
        except Exception as e:
            print(f"[job {job_id}] 出错：{e}", flush=True)
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

VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".avi", ".mkv"}


def _ext(name) -> str:
    return os.path.splitext(name or "")[1].lower()


def _is_video(f: UploadFile) -> bool:
    return _ext(f.filename) in VIDEO_EXTS or (f.content_type or "").startswith("video/")


def _is_zip(f: UploadFile) -> bool:
    return _ext(f.filename) == ".zip" or (f.content_type or "") in (
        "application/zip", "application/x-zip-compressed",
    )


def _safe_name(name, fallback):
    safe = "".join(c for c in (name or "") if c.isalnum() or c in ("-", "_", "."))
    return safe or fallback


def _start_video_job(name, write_chunks):
    """Create a video job, stream the bytes in via write_chunks(fh), kick worker."""
    safe = _safe_name(name, "video.mov")
    job_id = jobs.create_job(safe)
    target = os.path.join(jobs.job_dir(job_id), safe)
    with open(target, "wb") as fh:
        write_chunks(fh)
    size_mb = os.path.getsize(target) / 1e6
    print(f"[job {job_id}] 收到视频 {safe}（{size_mb:.1f} MB），开始处理", flush=True)
    asyncio.create_task(_run_worker(job_id))
    return {"ok": True, "id": job_id, "kind": "video"}


@app.post("/upload")
async def upload(request: Request, _: None = Depends(_check_token)):
    """同一个入口收视频或照片；也接受 zip（快捷指令的 Make Archive 产物）。

    iOS 快捷指令的表单 File 字段对列表只会带第一项，所以多选照片要先
    Make Archive 打成一个 zip 再传。服务端解包：
    - zip 里有视频 → 取第一个跑整条管线；
    - zip 里是照片（或散传的照片）→ 一次分享算**一件商品**，照片全勾上，
      字段留空到网页里填。HEIC 转 JPEG、按 EXIF 摆正。

    表单手工解析：收下**任何字段名**下的文件部件（捷径里 key 打错也没事），
    并把收到的每个部件打到终端，方便对着日志排查捷径配置。
    """
    form = await request.form()
    file: List[UploadFile] = []
    notes = []
    for key, val in form.multi_items():
        if isinstance(val, str):
            notes.append(f"{key}=文本({len(val)}字符)")
        else:  # 文件部件，无论字段叫什么都收
            file.append(val)
            notes.append(f"{key}=文件({val.filename}, {val.content_type})")
    print(f"[upload] 表单字段: {', '.join(notes) or '(空)'}", flush=True)

    if not file:
        raise HTTPException(
            400,
            "表单里没有文件——检查捷径 Get Contents of URL 里那个字段的类型"
            "是不是选成了 File（不是 Text），值是不是 Make Archive 的输出。",
        )

    # 1) 散传的视频：照旧流式落盘（不整读进内存）。
    for f in file:
        if _is_video(f):
            def _write(fh, src=f):
                while True:
                    chunk = src.file.read(1024 * 1024)
                    if not chunk:
                        break
                    fh.write(chunk)

            return _start_video_job(f.filename or "video.mov", _write)

    # 2) 收集图片字节；zip 展开（里面藏着视频就走视频流程）。
    image_payloads = []
    for f in file:
        if _is_zip(f):
            try:
                zf = zipfile.ZipFile(f.file)  # UploadFile 落在临时文件上，可随机读
            except zipfile.BadZipFile:
                raise HTTPException(400, "zip 文件损坏")
            names = [
                n for n in zf.namelist()
                if os.path.basename(n) and not os.path.basename(n).startswith(".")
            ]
            zvideos = [n for n in names if _ext(n) in VIDEO_EXTS]
            if zvideos:
                def _write(fh, zf=zf, member=zvideos[0]):
                    with zf.open(member) as src:
                        while True:
                            chunk = src.read(1024 * 1024)
                            if not chunk:
                                break
                            fh.write(chunk)

                return _start_video_job(os.path.basename(zvideos[0]), _write)
            for n in names:
                image_payloads.append(zf.read(n))
        else:
            image_payloads.append(await f.read())

    if len(image_payloads) > 40:
        raise HTTPException(400, f"一次最多 40 张（收到 {len(image_payloads)} 张）")

    # 3) 纯照片：一件商品，无需跑管线。
    job_id = jobs.create_job("照片")
    item_dir = os.path.join(jobs.job_dir(job_id), "items", "0")
    os.makedirs(item_dir, exist_ok=True)

    candidates = []
    for i, data in enumerate(image_payloads):
        try:
            img = Image.open(io.BytesIO(data))
            img = ImageOps.exif_transpose(img).convert("RGB")
        except Exception:
            continue  # 读不了的跳过（比如混进来的非图片文件）
        fn = f"photo_{i + 1:03d}.jpg"
        img.save(os.path.join(item_dir, fn), "JPEG", quality=92)
        candidates.append({"filename": fn, "sharpness": 0})

    jobs.patch_state(job_id, {"video_filename": f"照片×{len(candidates)}"})
    if not candidates:
        jobs.patch_state(job_id, {"stage": "error", "message": "没有能读取的图片"})
        raise HTTPException(400, "没有能读取的图片")

    listing = {
        "title": "",
        "price": None,
        "condition": None,
        "description": "",
        "contact": config.CONTACT,
        "transcript": "",
        "candidates": candidates,
        "selected": list(range(len(candidates))),
        "captions": {},
        "marketSearched": False,
        "marketPrice": None,
        "marketPriceText": None,
        "marketSource": None,
    }
    jobs.patch_state(job_id, {
        "stage": "done",
        "message": "照片已就绪",
        "listings": [listing],
    })
    print(f"[job {job_id}] 收到照片 ×{len(candidates)}，已就绪", flush=True)
    return {"ok": True, "id": job_id, "kind": "photos", "count": len(candidates)}


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
