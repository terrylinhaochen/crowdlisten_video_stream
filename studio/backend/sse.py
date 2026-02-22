"""
sse.py — Server-Sent Events bus.
Any backend thread can call emit() to push a task update to all connected browsers.
"""
import asyncio
import json
from collections import defaultdict
from typing import AsyncIterator

# Global event queue: job_id → list of asyncio.Queue
_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)
_global_subscribers: list[asyncio.Queue] = []


def _make_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def emit(job_id: str, event: str, data: dict):
    """
    Called from sync background threads (pipeline, queue processor).
    Pushes to all SSE subscribers for this job + global subscribers.
    """
    msg = _make_event(event, {"job_id": job_id, **data})
    for q in list(_subscribers.get(job_id, [])):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass
    for q in list(_global_subscribers):
        try:
            q.put_nowait(msg)
        except asyncio.QueueFull:
            pass


async def subscribe_all() -> AsyncIterator[str]:
    """Async generator — yields SSE messages for all jobs."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _global_subscribers.append(q)
    try:
        # Send a keepalive immediately
        yield ": keepalive\n\n"
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=20.0)
                yield msg
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
    finally:
        try:
            _global_subscribers.remove(q)
        except ValueError:
            pass
