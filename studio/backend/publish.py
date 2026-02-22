"""
Scaffold for TikTok and Instagram publishing.

Uses:
- TikTok Content Posting API v2
- Instagram Graph API

Both are stubs — return credential-not-configured errors until API tokens are set.
"""

import os
from pathlib import Path

# Environment variables for API credentials
TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")


def publish_to_tiktok(filepath: str, caption: str) -> dict:
    """
    Publish video to TikTok using Content Posting API v2.

    Auth flow (when implemented):
    1. Use TIKTOK_ACCESS_TOKEN (OAuth 2.0 token)
    2. POST to /v2/post/publish/video/init/ to initiate upload
    3. Upload video chunks to provided upload URL
    4. POST to /v2/post/publish/video/complete/ to finalize

    Args:
        filepath: Absolute path to the video file
        caption: Caption/description for the TikTok post

    Returns:
        dict with ok, platform, message, and optionally post_url
    """
    if not TIKTOK_ACCESS_TOKEN:
        return {
            "ok": False,
            "platform": "tiktok",
            "message": "TikTok API credentials not configured",
        }

    # Validate file exists
    if not Path(filepath).exists():
        return {
            "ok": False,
            "platform": "tiktok",
            "message": f"Video file not found: {filepath}",
        }

    # TODO: Implement TikTok Content Posting API v2
    # 1. Initialize upload session
    # 2. Upload video file
    # 3. Complete upload and get post URL
    return {
        "ok": False,
        "platform": "tiktok",
        "message": "TikTok publishing not yet implemented",
    }


def publish_to_instagram(filepath: str, caption: str) -> dict:
    """
    Publish video (Reel) to Instagram using Graph API.

    Auth flow (when implemented):
    1. Use INSTAGRAM_ACCESS_TOKEN (Facebook Graph API token)
    2. POST to /{ig-user-id}/media with video_url and caption
    3. Poll for container status until ready
    4. POST to /{ig-user-id}/media_publish to publish

    Args:
        filepath: Absolute path to the video file
        caption: Caption/description for the Instagram post

    Returns:
        dict with ok, platform, message, and optionally post_url
    """
    if not INSTAGRAM_ACCESS_TOKEN:
        return {
            "ok": False,
            "platform": "instagram",
            "message": "Instagram API credentials not configured",
        }

    # Validate file exists
    if not Path(filepath).exists():
        return {
            "ok": False,
            "platform": "instagram",
            "message": f"Video file not found: {filepath}",
        }

    # TODO: Implement Instagram Graph API for Reels
    # 1. Create media container
    # 2. Wait for processing
    # 3. Publish container
    return {
        "ok": False,
        "platform": "instagram",
        "message": "Instagram publishing not yet implemented",
    }


def publish_video(filepath: str, caption: str, platform: str) -> dict:
    """
    Publish a video to the specified platform(s).

    Args:
        filepath: Absolute path to the video file
        caption: Caption/description for the post
        platform: "tiktok", "instagram", or "both"

    Returns:
        dict with ok, platform, message, and optionally post_url
    """
    if platform == "tiktok":
        return publish_to_tiktok(filepath, caption)
    elif platform == "instagram":
        return publish_to_instagram(filepath, caption)
    elif platform == "both":
        # Return list of results for both platforms
        return {
            "ok": True,
            "platform": "both",
            "message": "Published to both platforms",
            "results": [
                publish_to_tiktok(filepath, caption),
                publish_to_instagram(filepath, caption),
            ],
        }
    else:
        return {
            "ok": False,
            "platform": platform,
            "message": f"Unknown platform: {platform}",
        }
