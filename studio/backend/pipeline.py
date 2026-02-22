"""
pipeline.py — Three video modes:
  meme       → hook clip + caption only (no TTS, no CTA)
  narration  → hook clip + voiceover body + branded CTA card
  cta_only   → standalone 5s branded CTA card

All output: 1080x1920 (9:16), libx264/aac.
"""
import asyncio
import os
import re
import subprocess
import textwrap
import uuid
from pathlib import Path

from .config import (BASE_DIR, FONT_PATH, LOGO_PATH, PUBLISHED_DIR,
                     REVIEW_DIR, TMP_DIR,
                     CTA_TAGLINE_DEFAULT, CTA_SUBTITLE, CTA_URL)
from .tts import generate_tts, get_audio_duration
from . import sse

OW, OH = 1080, 1920
VH = 608
VY = (OH - VH) // 2      # 656
MAX_FONT, MIN_FONT = 76, 44
CHAR_W_RATIO = 0.50
CANVAS_W = OW - 60
BORDER = 6


# ── helpers ─────────────────────────────────────────────────────────────────

def esc(t: str) -> str:
    return (
        t.replace("\\", "\\\\")
         .replace("'",  "\u2019")
         .replace("\u2018", "\u2019")
         .replace(":",  "\\:")
         .replace(",",  "\\,")
    )


def auto_wrap(text: str, max_chars: int = 26) -> list[str]:
    result = []
    for seg in text.split("\n"):
        result.extend(textwrap.wrap(seg, width=max_chars) if len(seg) > max_chars else [seg])
    return result


def font_size_for(lines: list[str]) -> int:
    max_len = max(len(l) for l in lines) if lines else 1
    return max(MIN_FONT, min(MAX_FONT, int(CANVAS_W / (max_len * CHAR_W_RATIO))))


def _run_ff(args: list[str], job_id: str = "", step: str = "") -> None:
    """Run ffmpeg, emit SSE progress events, raise on failure."""
    cmd = ["ffmpeg", "-y", "-progress", "pipe:1", "-nostats", *args]
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    duration_sec = None
    current_sec = 0.0

    stdout_lines = []
    stderr_lines = []

    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None:
            break
        stdout_lines.append(line)
        line = line.strip()
        if line.startswith("out_time_ms="):
            try:
                current_sec = int(line.split("=")[1]) / 1_000_000
            except ValueError:
                pass
        if job_id and step and duration_sec:
            pct = min(int(current_sec / duration_sec * 100), 99)
            sse.emit(job_id, "progress", {"step": step, "pct": pct})

    stderr_out = proc.stderr.read()
    # Extract total duration from stderr for progress calculation
    if not duration_sec:
        m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", stderr_out)
        if m:
            h, mi, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
            duration_sec = h * 3600 + mi * 60 + s

    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg [{step}] failed:\n{stderr_out[-600:]}")

    if job_id:
        sse.emit(job_id, "progress", {"step": step, "pct": 100})


def run_ff(args: list[str], job_id: str = "", step: str = "") -> None:
    """Simpler wrapper for cases where progress tracking isn't critical."""
    cmd = ["ffmpeg", "-y", *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg [{step}] failed:\n{r.stderr[-600:]}")
    if job_id:
        sse.emit(job_id, "progress", {"step": step, "pct": 100})


# ── thumbnail ────────────────────────────────────────────────────────────────

def generate_thumbnail(source_file: str, start_sec: int, clip_id: str) -> str:
    """Extract a single frame as JPEG thumbnail."""
    out = str(TMP_DIR / f"thumb_{clip_id}.jpg")
    if Path(out).exists():
        return out
    run_ff([
        "-ss", str(start_sec + 2),
        "-i", source_file,
        "-vframes", "1",
        "-vf", f"scale=270:-2",
        "-q:v", "3",
        out,
    ])
    return out


# ── CTA card (shared) ────────────────────────────────────────────────────────

def render_cta_card(job_id: str, tagline: str = CTA_TAGLINE_DEFAULT,
                    subtitle: str = CTA_SUBTITLE, url: str = CTA_URL,
                    duration: int = 5) -> str:
    out = str(TMP_DIR / f"cta_{job_id}.mp4")

    logo_h = 200
    logo_y = OH // 2 - logo_h - 60
    tagline_y = OH // 2 + 20
    subtitle_y = OH // 2 + 90
    url_y = OH // 2 + 155

    filter_complex = (
        f"[1:v]scale=300:-1,format=rgba[logo];"
        f"[0:v][logo]overlay=(W-300)/2:{logo_y}[bg_logo];"
        f"[bg_logo]"
        f"drawtext=fontfile='{FONT_PATH}':text='{esc(tagline)}'"
        f":fontcolor=white:fontsize=52:borderw=4:bordercolor=black"
        f":x=(w-text_w)/2:y={tagline_y},"
        f"drawtext=fontfile='{FONT_PATH}':text='{esc(subtitle)}'"
        f":fontcolor=#a5b4fc:fontsize=38:borderw=3:bordercolor=black"
        f":x=(w-text_w)/2:y={subtitle_y},"
        f"drawtext=fontfile='{FONT_PATH}':text='{esc(url)}'"
        f":fontcolor=#cccccc:fontsize=32:borderw=2:bordercolor=black"
        f":x=(w-text_w)/2:y={url_y}"
        "[v]"
    )

    run_ff([
        "-f", "lavfi",
        "-i", f"color=c=black:s={OW}x{OH}:r=30",
        "-i", LOGO_PATH,
        "-t", str(duration),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-movflags", "+faststart",
        out,
    ], job_id=job_id, step="cta")
    return out


def add_silent_audio(video_path: str, duration: float) -> str:
    out = video_path.replace(".mp4", "_sa.mp4")
    run_ff([
        "-i", video_path,
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(duration), "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k", "-shortest",
        out,
    ])
    return out


# ── MODE 1: MEME ─────────────────────────────────────────────────────────────

def render_meme(job_id: str, source_file: str, start_sec: int,
                duration_sec: int, caption: str, output_name: str) -> str:
    """Pure meme: clip + caption burned in. No TTS, no CTA."""
    out = str(REVIEW_DIR / f"{output_name}.mp4")

    lines = auto_wrap(caption)
    fs = font_size_for(lines)
    lh = fs + 10
    block_h = len(lines) * lh
    block_y = max((VY - block_h) // 2, 24)

    filters = [
        f"scale={OW}:-2",
        f"pad={OW}:{OH}:(ow-iw)/2:(oh-ih)/2:black",
    ]
    for i, line in enumerate(lines):
        filters.append(
            f"drawtext=fontfile='{FONT_PATH}':text='{esc(line)}':fontcolor=white"
            f":fontsize={fs}:borderw={BORDER}:bordercolor=black"
            f":x=(w-text_w)/2:y={block_y + i * lh}"
        )

    run_ff([
        "-ss", str(start_sec), "-i", source_file, "-t", str(duration_sec),
        "-vf", ",".join(filters),
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        out,
    ], job_id=job_id, step="render")
    return out


# ── MODE 2: NARRATION ────────────────────────────────────────────────────────

def render_hook(job_id: str, source_file: str, start_sec: int,
                duration_sec: int, caption: str) -> str:
    out = str(TMP_DIR / f"hook_{job_id}.mp4")
    lines = auto_wrap(caption)
    fs = font_size_for(lines)
    lh = fs + 10
    block_h = len(lines) * lh
    block_y = max((VY - block_h) // 2, 24)

    filters = [
        f"scale={OW}:-2",
        f"pad={OW}:{OH}:(ow-iw)/2:(oh-ih)/2:black",
    ]
    for i, line in enumerate(lines):
        filters.append(
            f"drawtext=fontfile='{FONT_PATH}':text='{esc(line)}':fontcolor=white"
            f":fontsize={fs}:borderw={BORDER}:bordercolor=black"
            f":x=(w-text_w)/2:y={block_y + i * lh}"
        )

    run_ff([
        "-ss", str(start_sec), "-i", source_file, "-t", str(duration_sec),
        "-vf", ",".join(filters),
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        out,
    ], job_id=job_id, step="hook")
    return out


def render_body(job_id: str, script: str, audio_file: str,
                audio_duration: float) -> str:
    out = str(TMP_DIR / f"body_{job_id}.mp4")
    lines = auto_wrap(script, max_chars=32)
    fs = 54
    lh = fs + 12
    base_y = int(OH * 0.70)

    subtitle_filters = []
    for i, line in enumerate(lines[:6]):
        subtitle_filters.append(
            f"drawtext=fontfile='{FONT_PATH}':text='{esc(line)}':fontcolor=white"
            f":fontsize={fs}:borderw=4:bordercolor=black"
            f":x=(w-text_w)/2:y={base_y + i * lh}"
        )

    logo_filter = (
        "[1:v]scale=100:-1,format=rgba,colorchannelmixer=aa=0.4[logo];"
        "[0:v][logo]overlay=W-100-16:16[bg_logo]"
    )
    sub_chain = "[bg_logo]" + ",".join(subtitle_filters) + "[v]" if subtitle_filters else "[bg_logo]copy[v]"

    run_ff([
        "-f", "lavfi",
        "-i", f"color=c=0x0a0a0a:s={OW}x{OH}:r=30",
        "-i", LOGO_PATH,
        "-i", audio_file,
        "-t", str(audio_duration),
        "-filter_complex", f"{logo_filter};{sub_chain}",
        "-map", "[v]", "-map", "2:a",
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        out,
    ], job_id=job_id, step="body")
    return out


def assemble(job_id: str, hook_file: str, body_file: str,
             cta_file: str, output_name: str) -> str:
    cta_with_audio = add_silent_audio(cta_file, 5.0)
    out = str(REVIEW_DIR / f"{output_name}.mp4")

    run_ff([
        "-i", hook_file, "-i", body_file, "-i", cta_with_audio,
        "-filter_complex",
        "[0:v][0:a][1:v][1:a][2:v][2:a]concat=n=3:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-crf", "20", "-preset", "fast",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
        out,
    ], job_id=job_id, step="assemble")

    try:
        os.remove(cta_with_audio)
    except Exception:
        pass
    return out


def cleanup_tmp(job_id: str):
    for f in TMP_DIR.glob(f"*_{job_id}*.mp4"):
        try:
            f.unlink()
        except Exception:
            pass


# ── MODE 3: CTA ONLY ─────────────────────────────────────────────────────────

def run_cta_only(job_id: str, tagline: str, subtitle: str,
                 url: str, output_name: str) -> str:
    cta_file = render_cta_card(job_id, tagline, subtitle, url, duration=8)
    cta_with_audio = add_silent_audio(cta_file, 8.0)
    out = str(REVIEW_DIR / f"{output_name}.mp4")
    import shutil
    shutil.move(cta_with_audio, out)
    try:
        Path(cta_file).unlink()
    except Exception:
        pass
    return out


# ── MAIN ENTRY ────────────────────────────────────────────────────────────────

def run_pipeline(job: dict) -> dict:
    """Synchronous — called from background thread in queue.py."""
    job_id = job["id"]
    mode = job.get("mode", "narration")

    sse.emit(job_id, "status", {"status": "rendering", "mode": mode})

    try:
        if mode == "meme":
            sse.emit(job_id, "progress", {"step": "render", "pct": 0})
            out = render_meme(
                job_id,
                job["source_file"], job["start_sec"], job["duration_sec"],
                job["hook_caption"], job["output_name"],
            )

        elif mode == "cta_only":
            sse.emit(job_id, "progress", {"step": "cta", "pct": 0})
            out = run_cta_only(
                job_id,
                job.get("cta_tagline", CTA_TAGLINE_DEFAULT),
                job.get("cta_subtitle", CTA_SUBTITLE),
                job.get("cta_url", CTA_URL),
                job["output_name"],
            )

        else:  # narration
            sse.emit(job_id, "progress", {"step": "hook", "pct": 0})
            hook_file = render_hook(
                job_id, job["source_file"], job["start_sec"],
                job["duration_sec"], job["hook_caption"],
            )

            sse.emit(job_id, "progress", {"step": "tts", "pct": 0})
            audio_file = job.get("body_audio_file")
            if audio_file and Path(audio_file).exists():
                audio_duration = get_audio_duration(audio_file)
            else:
                tts_result = asyncio.run(
                    generate_tts(
                        job["body_script"],
                        voice=job.get("voice", "shimmer"),
                        provider=job.get("provider", "openai"),
                    )
                )
                audio_file = tts_result["audio_file"]
                audio_duration = tts_result["duration"]
            sse.emit(job_id, "progress", {"step": "tts", "pct": 100})

            sse.emit(job_id, "progress", {"step": "body", "pct": 0})
            body_file = render_body(job_id, job["body_script"], audio_file, audio_duration)

            sse.emit(job_id, "progress", {"step": "cta", "pct": 0})
            cta_file = render_cta_card(
                job_id,
                job.get("cta_tagline", CTA_TAGLINE_DEFAULT),
                job.get("cta_subtitle", CTA_SUBTITLE),
            )

            sse.emit(job_id, "progress", {"step": "assemble", "pct": 0})
            out = assemble(job_id, hook_file, body_file, cta_file, job["output_name"])
            cleanup_tmp(job_id)

        sse.emit(job_id, "status", {"status": "review", "output_file": out})
        return {"output_file": out, "status": "review"}

    except Exception as exc:
        sse.emit(job_id, "status", {"status": "failed", "error": str(exc)})
        cleanup_tmp(job_id)
        raise
