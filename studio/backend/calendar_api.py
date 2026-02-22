"""Content calendar API for planning and scheduling clips."""
import json
import threading
import uuid
from datetime import datetime, timezone

from .config import BASE_DIR

CALENDAR_FILE = BASE_DIR / "studio" / "calendar.json"

_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_calendar() -> list[dict]:
    """Load calendar entries from disk."""
    with _lock:
        if not CALENDAR_FILE.exists():
            return []
        try:
            return json.loads(CALENDAR_FILE.read_text())
        except Exception:
            return []


def save_calendar(entries: list[dict]) -> None:
    """Save calendar entries to disk."""
    with _lock:
        CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
        CALENDAR_FILE.write_text(json.dumps(entries, indent=2))


def add_entry(topic: str, date: str) -> dict:
    """Add a new calendar entry."""
    entries = load_calendar()
    entry = {
        "id": str(uuid.uuid4()),
        "topic": topic,
        "date": date,  # YYYY-MM-DD
        "status": "planned",
        "clip_id": None,
        "output_name": None,
        "created_at": _now(),
    }
    entries.append(entry)
    save_calendar(entries)
    return entry


def update_entry(entry_id: str, updates: dict) -> dict | None:
    """Update an existing calendar entry."""
    entries = load_calendar()
    for entry in entries:
        if entry["id"] == entry_id:
            # Only allow updating specific fields
            allowed_fields = {"status", "clip_id", "output_name", "topic", "date"}
            for key, value in updates.items():
                if key in allowed_fields:
                    entry[key] = value
            save_calendar(entries)
            return entry
    return None


def delete_entry(entry_id: str) -> bool:
    """Delete a calendar entry."""
    entries = load_calendar()
    new_entries = [e for e in entries if e["id"] != entry_id]
    if len(new_entries) == len(entries):
        return False
    save_calendar(new_entries)
    return True


def get_entry(entry_id: str) -> dict | None:
    """Get a single calendar entry by ID."""
    for entry in load_calendar():
        if entry["id"] == entry_id:
            return entry
    return None
