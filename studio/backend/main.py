import shutil
from datetime import datetime, timezone, date
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import (PUBLISHED_DIR, TMP_DIR, REVIEW_DIR, INBOX_DIR,
                     MARKETING_CLIPS_DIR, CTA_TAGLINE_DEFAULT, CTA_SUBTITLE, CTA_URL)
from . import clips as clip_lib
from . import queue as q
from . import sse as sse_bus

app = FastAPI(title="CrowdListen Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    from .queue import start_processor
    start_processor()


# ── SSE ──────────────────────────────────────────────────────────────────────

@app.get("/api/events")
async def events():
    """Server-Sent Events stream — push task progress to frontend."""
    return StreamingResponse(
        sse_bus.subscribe_all(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Clips ────────────────────────────────────────────────────────────────────

@app.get("/api/clips")
def list_clips(source: str | None = None, min_score: int = 0):
    return clip_lib.load_clips(source=source, min_score=min_score)


@app.get("/api/clips/{clip_id}")
def get_clip(clip_id: str):
    c = clip_lib.get_clip(clip_id)
    if not c:
        raise HTTPException(404, "Clip not found")
    return c


@app.get("/api/clips/{clip_id}/video")
def clip_video(clip_id: str):
    mp4 = clip_lib.find_rendered_mp4(clip_id)
    if not mp4:
        raise HTTPException(404, "No rendered video for this clip")
    return FileResponse(str(mp4), media_type="video/mp4")


@app.get("/api/clips/{clip_id}/thumbnail")
def clip_thumbnail(clip_id: str):
    """Generate or return cached thumbnail."""
    thumb = TMP_DIR / f"thumb_{clip_id}.jpg"
    if not thumb.exists():
        clip = clip_lib.get_clip(clip_id)
        if not clip:
            raise HTTPException(404, "Clip not found")
        try:
            from .pipeline import generate_thumbnail
            generate_thumbnail(clip["source_file"], clip["start_seconds"], clip_id)
        except Exception:
            raise HTTPException(500, "Thumbnail generation failed")
    if not thumb.exists():
        raise HTTPException(404, "Thumbnail not available")
    return FileResponse(str(thumb), media_type="image/jpeg")


# ── TTS ───────────────────────────────────────────────────────────────────────

class TTSRequest(BaseModel):
    script: str
    voice: str = "shimmer"
    provider: str = "openai"


@app.post("/api/tts")
async def generate_tts(req: TTSRequest):
    from .tts import generate_tts as do_tts
    return await do_tts(req.script, req.voice, req.provider)


@app.get("/api/audio/{filename}")
def serve_audio(filename: str):
    path = TMP_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Audio file not found")
    return FileResponse(str(path), media_type="audio/mpeg")


# ── Render ────────────────────────────────────────────────────────────────────

class RenderRequest(BaseModel):
    mode: str = "narration"        # meme | narration | cta_only
    # Hook (meme + narration)
    hook_clip_id: str | None = None
    hook_caption: str = ""
    # Body (narration only)
    body_script: str = ""
    body_audio_file: str | None = None
    voice: str = "shimmer"
    provider: str = "openai"
    # CTA (narration + cta_only)
    cta_tagline: str = CTA_TAGLINE_DEFAULT
    cta_subtitle: str = CTA_SUBTITLE
    cta_url: str = CTA_URL
    # Output
    output_name: str = ""


@app.post("/api/render", status_code=202)
def submit_render(req: RenderRequest):
    clip = None
    source_file = ""
    start_sec = 0
    duration_sec = 10

    if req.mode != "cta_only":
        if not req.hook_clip_id:
            raise HTTPException(400, "hook_clip_id required for this mode")
        clip = clip_lib.get_clip(req.hook_clip_id)
        if not clip:
            raise HTTPException(404, f"Clip not found: {req.hook_clip_id}")
        source_file = clip["source_file"]
        start_sec = clip["start_seconds"]
        duration_sec = clip["duration_seconds"]

    job = q.build_job(
        mode=req.mode,
        hook_clip_id=req.hook_clip_id or "",
        hook_caption=req.hook_caption,
        body_script=req.body_script,
        body_audio_file=req.body_audio_file,
        voice=req.voice,
        provider=req.provider,
        cta_tagline=req.cta_tagline,
        cta_subtitle=req.cta_subtitle,
        cta_url=req.cta_url,
        output_name=req.output_name or req.hook_clip_id or "output",
        source_file=source_file,
        start_sec=start_sec,
        duration_sec=duration_sec,
    )
    q.add_job(job)
    return job


# ── Queue ─────────────────────────────────────────────────────────────────────

@app.get("/api/queue")
def get_queue():
    return list(reversed(q.load_queue()))


@app.delete("/api/queue/{job_id}")
def delete_job(job_id: str):
    if not q.remove_job(job_id):
        raise HTTPException(404, "Job not found")
    return {"ok": True}


# ── Review ────────────────────────────────────────────────────────────────────

@app.get("/api/review")
def list_review():
    videos = []
    if REVIEW_DIR.exists():
        for mp4 in sorted(REVIEW_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True):
            stat = mp4.stat()
            videos.append({
                "filename": mp4.name,
                "size_mb": round(stat.st_size / 1024 / 1024, 1),
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "url": f"/api/review/{mp4.name}",
            })
    return videos


@app.get("/api/review/{filename}")
def serve_review(filename: str):
    path = REVIEW_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Video not found")
    return FileResponse(str(path), media_type="video/mp4")


@app.post("/api/review/{filename}/approve")
def approve_video(filename: str):
    src = REVIEW_DIR / filename
    if not src.exists():
        raise HTTPException(404, "Video not found")
    dst = PUBLISHED_DIR / filename
    shutil.move(str(src), str(dst))
    # Update job status
    for job in q.load_queue():
        if job.get("output_name") and filename.startswith(job["output_name"]):
            q.update_job(job["id"], {"status": "published"})
            break
    return {"ok": True, "published": f"/api/published/{filename}"}


@app.post("/api/review/{filename}/reject")
def reject_video(filename: str):
    path = REVIEW_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Video not found")
    path.unlink()
    return {"ok": True}


# ── Published ─────────────────────────────────────────────────────────────────

@app.get("/api/published")
def list_published():
    today = date.today()
    videos = []
    today_count = 0

    if PUBLISHED_DIR.exists():
        for mp4 in sorted(PUBLISHED_DIR.glob("*.mp4"), key=lambda f: f.stat().st_mtime, reverse=True):
            mtime = datetime.fromtimestamp(mp4.stat().st_mtime, tz=timezone.utc)
            size_mb = round(mp4.stat().st_size / 1024 / 1024, 1)
            if mtime.date() == today:
                today_count += 1
            videos.append({
                "filename": mp4.name,
                "size_mb": size_mb,
                "created_at": mtime.isoformat(),
                "url": f"/api/published/{mp4.name}",
            })

    return {"videos": videos, "today_count": today_count, "daily_target": 2}


@app.get("/api/published/{filename}")
def serve_published(filename: str):
    path = PUBLISHED_DIR / filename
    if not path.exists():
        raise HTTPException(404, "Video not found")
    return FileResponse(str(path), media_type="video/mp4")


# ── Intake ────────────────────────────────────────────────────────────────────

@app.post("/api/intake")
async def intake_video(file: UploadFile = File(...)):
    """
    Receive uploaded video → save to marketing_clips/ → trigger Gemini analysis.
    Returns immediately; analysis runs in background.
    """
    dest = MARKETING_CLIPS_DIR / file.filename
    with open(str(dest), "wb") as f:
        content = await file.read()
        f.write(content)

    import threading
    import uuid as uuid_mod

    job_id = str(uuid_mod.uuid4())
    sse_bus.emit(job_id, "intake", {"status": "analyzing", "filename": file.filename})

    def _analyze():
        try:
            import subprocess
            script = str(Path(__file__).parent.parent.parent / "scripts" / "analyze_video.py")
            result = subprocess.run(
                ["python3", script, str(dest), "--clips", "10", "--model", "gemini-2.0-flash"],
                capture_output=True, text=True, cwd=str(dest.parent.parent)
            )
            if result.returncode == 0:
                sse_bus.emit(job_id, "intake", {"status": "done", "filename": file.filename})
            else:
                sse_bus.emit(job_id, "intake", {
                    "status": "failed",
                    "filename": file.filename,
                    "error": result.stderr[-300:],
                })
        except Exception as e:
            sse_bus.emit(job_id, "intake", {"status": "failed", "filename": file.filename, "error": str(e)})

    threading.Thread(target=_analyze, daemon=True).start()
    return {"ok": True, "job_id": job_id, "filename": file.filename, "path": str(dest)}


# ── Static frontend ───────────────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
