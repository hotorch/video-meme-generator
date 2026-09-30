"""Higgsfield Genjutsu: REST model paths, MCP model ids, limits and prices (https://docs.higgsfield.ai/docs/models)."""

import math

BASE_URL = "https://api.higgsfield.ai"

# Video — Genjutsu. Same input schema for both:
#   video_url (MP4, 4–30s; longer is trimmed to 30s), image_urls (1–8, ordered),
#   prompt (<=10k chars), resolution ("480p" | "720p" | "1080p")
GENJUTSU_OBJECT_SWAP = "higgsfield/genjutsu/object-swap/v1.0"
GENJUTSU_MOTION_TRANSFER = "higgsfield/genjutsu/motion-transfer/v1.0"
GENJUTSU = {"object-swap": GENJUTSU_OBJECT_SWAP, "motion-transfer": GENJUTSU_MOTION_TRANSFER}
# The same two models through the Higgsfield MCP connector (generate_video `model`), billed in account credits.
GENJUTSU_MCP = {"object-swap": "hf_mult_replace_object", "motion-transfer": "hf_mult_motion_control"}

GENJUTSU_MIN_SECONDS = 4.0
GENJUTSU_MAX_SECONDS = 30.0
GENJUTSU_MAX_IMAGES = 8
OBJECT_SWAP_MIN_PIXELS = 409_600  # width * height per frame
PROBE_SECONDS = GENJUTSU_MIN_SECONDS

# Images are not generated on Higgsfield (quality): see memegen/imagegen/codex.py (Codex CLI image_gen).

# Both backends bill per second of input video, rounded UP (12.04 s costs 13 s), same price for both modes.
# REST: pay-as-you-go USD from POST /estimate (2026-09-29, pre-discount).
GENJUTSU_USD_PER_SECOND = {"480p": 0.318, "720p": 0.681, "1080p": 1.632}
# MCP: subscription credits per second per variant, measured on real takes (2026-09-30). 1080p not measured.
GENJUTSU_CREDITS_PER_SECOND = {"480p": 3, "720p": 7}


def billed_seconds(duration: float) -> int:
    return math.ceil(round(duration, 2))


def genjutsu_cost_usd(duration: float, resolution: str) -> float:
    return round(billed_seconds(duration) * GENJUTSU_USD_PER_SECOND[resolution], 3)


def genjutsu_cost_credits(duration: float, resolution: str) -> int | None:
    rate = GENJUTSU_CREDITS_PER_SECOND.get(resolution)
    return billed_seconds(duration) * rate if rate else None


def genjutsu_cost(duration: float, resolution: str) -> dict:
    """Both price lists for one run: {"seconds", "resolution", "usd" (REST), "credits" (MCP)}."""
    return {"seconds": billed_seconds(duration), "resolution": resolution,
            "usd": genjutsu_cost_usd(duration, resolution), "credits": genjutsu_cost_credits(duration, resolution)}
