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
from .search import smart_search
from . import calendar_api as cal

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
    return {"clips": clip_lib.load_clips(source=source, min_score=min_score)}


@app.post("/api/sync")
def sync_library():
    """Force reload of clip library from disk (instant — no re-analysis)."""
    clip_lib.invalidate_cache()
    clips = clip_lib.load_clips()
    return {"ok": True, "clip_count": len(clips)}


@app.post("/api/smart-search")
def smart_search_endpoint(body: dict):
    """
    Semantic clip search using OpenAI.
    Body: {topic: str, limit: int = 5}
    Returns: {topic, clips: [...with match_reason], method: "ai"|"keyword"}
    """
    topic = body.get("topic", "").strip()
    limit = body.get("limit", 5)

    if not topic:
        raise HTTPException(400, "topic is required")

    all_clips = clip_lib.load_clips()
    results = smart_search(topic, all_clips, limit=limit)

    # Determine method used (AI if match_reason doesn't start with "Contains:")
    method = "keyword"
    if results and not results[0].get("match_reason", "").startswith("Contains:"):
        method = "ai"

    return {"topic": topic, "clips": results, "method": method}


@app.post("/api/batch")
def batch_render(jobs: list[dict]):
    """
    Queue multiple render jobs at once.
    Each job: {clip_id, caption, mode, output_name, [body_script, voice]}
    Returns list of job ids.
    """
    from . import queue as q_lib
    results = []
    for job_spec in jobs:
        clip_id = job_spec.get("clip_id")
        clip = clip_lib.get_clip(clip_id)
        if not clip:
            results.append({"clip_id": clip_id, "error": "clip not found"})
            continue
        job = {
            "mode":          job_spec.get("mode", "meme"),
            "output_name":   job_spec.get("output_name") or clip_id,
            "source_file":   clip["source_file"],
            "start_sec":     clip["start_seconds"],
            "duration_sec":  clip["duration_seconds"],
            "hook_caption":  job_spec.get("caption") or clip["meme_caption"],
            "hook_clip_id":  clip_id,
        }
        if job["mode"] == "narration":
            job["body_script"] = job_spec.get("body_script", "")
            job["voice"]       = job_spec.get("voice", "shimmer")
        job_id = q_lib.enqueue(job)
        results.append({"clip_id": clip_id, "job_id": job_id, "output_name": job["output_name"]})
    return {"queued": len([r for r in results if "job_id" in r]), "results": results}


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


@app.get("/api/clips/{clip_id}/preview")
def clip_preview(clip_id: str):
    """Raw clip cut from source — no caption, no processing. Cached in tmp/."""
    import subprocess
    cached = TMP_DIR / f"preview_{clip_id}.mp4"
    if not cached.exists():
        clip = clip_lib.get_clip(clip_id)
        if not clip:
            raise HTTPException(404, "Clip not found")
        r = subprocess.run([
            "ffmpeg", "-y",
            "-ss", str(clip["start_seconds"]),
            "-i", clip["source_file"],
            "-t", str(clip["duration_seconds"]),
            "-vf", "scale=540:-2",   # half-res for fast preview
            "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "64k",
            str(cached),
        ], capture_output=True)
        if r.returncode != 0:
            raise HTTPException(500, "Preview generation failed")
    return FileResponse(str(cached), media_type="video/mp4")


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
        all_vids = sorted(
            [f for f in PUBLISHED_DIR.rglob("*") if f.suffix.lower() == ".mp4" and f.is_file()],
            key=lambda f: f.stat().st_mtime, reverse=True,
        )
        for mp4 in all_vids:
            rel = mp4.relative_to(PUBLISHED_DIR)
            folder = str(rel.parent) if str(rel.parent) != "." else "studio"
            mtime = datetime.fromtimestamp(mp4.stat().st_mtime, tz=timezone.utc)
            size_mb = round(mp4.stat().st_size / 1024 / 1024, 1)
            if mtime.date() == today:
                today_count += 1
            videos.append({
                "filename": mp4.name,
                "rel_path": str(rel),
                "folder": folder,
                "size_mb": size_mb,
                "created_at": mtime.isoformat(),
                "url": f"/api/published/{str(rel)}",
            })

    return {"videos": videos, "today_count": today_count, "daily_target": 2}


@app.get("/api/published/{rel_path:path}")
def serve_published(rel_path: str):
    path = (PUBLISHED_DIR / rel_path).resolve()
    if not str(path).startswith(str(PUBLISHED_DIR.resolve())):
        raise HTTPException(403, "Forbidden")
    if not path.exists():
        raise HTTPException(404, "Video not found")
    return FileResponse(str(path), media_type="video/mp4")


@app.get("/api/sources")
def list_sources():
    """List source videos and their analysis state."""
    from .config import PROCESSING_DIR
    sources = []
    if MARKETING_CLIPS_DIR.exists():
        for vid in sorted(MARKETING_CLIPS_DIR.glob("*")):
            if vid.suffix.lower() not in (".mp4", ".mov", ".avi", ".mkv"):
                continue
            stem = vid.stem
            analyzed = (PROCESSING_DIR / f"{stem}_visual_analysis.json").exists()
            clip_count = 0
            if analyzed:
                import json as _json
                try:
                    data = _json.loads((PROCESSING_DIR / f"{stem}_visual_analysis.json").read_text())
                    clip_count = len(data.get("clips", []))
                except Exception:
                    pass
            sources.append({
                "filename": vid.name,
                "stem": stem,
                "size_mb": round(vid.stat().st_size / 1024 / 1024, 1),
                "analyzed": analyzed,
                "clip_count": clip_count,
            })
    return {"sources": sources}


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


# ── Calendar ───────────────────────────────────────────────────────────────────

@app.get("/api/calendar")
def list_calendar():
    return {"entries": cal.load_calendar()}


class CalendarEntryCreate(BaseModel):
    topic: str
    date: str  # YYYY-MM-DD


@app.post("/api/calendar")
def create_calendar_entry(body: CalendarEntryCreate):
    entry = cal.add_entry(body.topic, body.date)
    return entry


class CalendarEntryUpdate(BaseModel):
    status: str | None = None
    clip_id: str | None = None
    output_name: str | None = None
    topic: str | None = None
    date: str | None = None


@app.put("/api/calendar/{entry_id}")
def update_calendar_entry(entry_id: str, body: CalendarEntryUpdate):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    entry = cal.update_entry(entry_id, updates)
    if not entry:
        raise HTTPException(404, "Calendar entry not found")
    return entry


@app.delete("/api/calendar/{entry_id}")
def delete_calendar_entry(entry_id: str):
    if not cal.delete_entry(entry_id):
        raise HTTPException(404, "Calendar entry not found")
    return {"ok": True}


@app.post("/api/calendar/{entry_id}/queue")
def queue_calendar_render(entry_id: str):
    """Queue a render job for a calendar entry using its clip_id."""
    entry = cal.get_entry(entry_id)
    if not entry:
        raise HTTPException(404, "Calendar entry not found")
    if not entry.get("clip_id"):
        raise HTTPException(400, "No clip selected for this calendar entry")

    clip = clip_lib.get_clip(entry["clip_id"])
    if not clip:
        raise HTTPException(404, f"Clip not found: {entry['clip_id']}")

    # Build and queue the job
    job = q.build_job(
        mode="meme",
        hook_clip_id=entry["clip_id"],
        hook_caption=clip.get("meme_caption", ""),
        body_script="",
        body_audio_file=None,
        voice="shimmer",
        provider="openai",
        cta_tagline=CTA_TAGLINE_DEFAULT,
        cta_subtitle=CTA_SUBTITLE,
        cta_url=CTA_URL,
        output_name=entry.get("output_name") or entry["topic"].lower().replace(" ", "_")[:40],
        source_file=clip["source_file"],
        start_sec=clip["start_seconds"],
        duration_sec=clip["duration_seconds"],
    )
    q.add_job(job)

    # Update calendar entry status
    cal.update_entry(entry_id, {"status": "rendering", "output_name": job["output_name"]})

    return {"ok": True, "job": job, "entry": cal.get_entry(entry_id)}


# ── Static frontend ───────────────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
