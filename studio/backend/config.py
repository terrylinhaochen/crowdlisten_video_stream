from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent.parent  # crowdlisten_marketing/
load_dotenv(BASE_DIR / ".env")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")

FONT_PATH           = "/System/Library/Fonts/Supplemental/Impact.ttf"
PROCESSING_DIR      = BASE_DIR / "processing"
REELS_OUTPUT_DIR    = BASE_DIR / "reels_output"
PUBLISHED_DIR       = BASE_DIR / "published"
MARKETING_CLIPS_DIR = BASE_DIR / "marketing_clips"
BRAND_ASSETS_DIR    = BASE_DIR / "brand_assets"
LOGO_PATH           = str(BRAND_ASSETS_DIR / "CRD.png")
TMP_DIR             = BASE_DIR / "studio" / "tmp"
REVIEW_DIR          = BASE_DIR / "studio" / "review"
INBOX_DIR           = BASE_DIR / "studio" / "inbox"
QUEUE_FILE          = BASE_DIR / "studio" / "queue.json"

CTA_TAGLINE_DEFAULT = "Try CrowdListen now"
CTA_SUBTITLE        = "the PM for AI Agents"
CTA_URL             = "crowdlisten.com"

# Ensure runtime dirs exist
for d in [TMP_DIR, REVIEW_DIR, INBOX_DIR, PUBLISHED_DIR]:
    d.mkdir(parents=True, exist_ok=True)
