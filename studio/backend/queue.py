import json
import threading
import time
import uuid
from datetime import datetime, timezone
from .config import QUEUE_FILE

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_queue() -> list[dict]:
    with _lock:
        if not QUEUE_FILE.exists():
            return []
        try:
            return json.loads(QUEUE_FILE.read_text())
        except Exception:
            return []


def save_queue(jobs: list[dict]):
    with _lock:
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        QUEUE_FILE.write_text(json.dumps(jobs, indent=2))


def add_job(job: dict) -> dict:
    jobs = load_queue()
    jobs.append(job)
    save_queue(jobs)
    return job


def update_job(job_id: str, updates: dict) -> dict | None:
    jobs = load_queue()
    for job in jobs:
        if job["id"] == job_id:
            job.update(updates)
            save_queue(jobs)
            return job
    return None


def get_job(job_id: str) -> dict | None:
    for job in load_queue():
        if job["id"] == job_id:
            return job
    return None


def remove_job(job_id: str) -> bool:
    jobs = load_queue()
    new_jobs = [j for j in jobs if j["id"] != job_id]
    if len(new_jobs) == len(jobs):
        return False
    save_queue(new_jobs)
    return True


def build_job(
    mode: str,
    hook_clip_id: str,
    hook_caption: str,
    body_script: str,
    body_audio_file: str | None,
    voice: str,
    provider: str,
    cta_tagline: str,
    cta_subtitle: str,
    cta_url: str,
    output_name: str,
    source_file: str,
    start_sec: int,
    duration_sec: int,
) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "status": "queued",
        "mode": mode,
        "created_at": _now(),
        "completed_at": None,
        "error": None,
        "hook_clip_id": hook_clip_id,
        "hook_caption": hook_caption,
        "body_script": body_script,
        "body_audio_file": body_audio_file,
        "voice": voice,
        "provider": provider,
        "cta_tagline": cta_tagline,
        "cta_subtitle": cta_subtitle,
        "cta_url": cta_url,
        "output_name": output_name,
        "source_file": source_file,
        "start_sec": start_sec,
        "duration_sec": duration_sec,
    }


def start_processor():
    def _process():
        while True:
            time.sleep(2)
            jobs = load_queue()
            queued = [j for j in jobs if j["status"] == "queued"]
            if not queued:
                continue
            job = queued[0]
            update_job(job["id"], {"status": "rendering"})
            try:
                from .pipeline import run_pipeline
                run_pipeline(job)
                update_job(job["id"], {"status": "review", "completed_at": _now()})
            except Exception as exc:
                update_job(job["id"], {"status": "failed", "error": str(exc), "completed_at": _now()})

    threading.Thread(target=_process, daemon=True).start()
