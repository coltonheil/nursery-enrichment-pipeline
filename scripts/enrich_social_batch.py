#!/usr/bin/env python3
"""Batch social enrichment for plant images using Claude vision."""

import json
import os
import sys
import base64
import httpx
from pathlib import Path
from supabase import create_client

# Supabase connection - using env vars or hardcoded for this project
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://esumuspzedpummjebxtc.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImVzdW11c3B6ZWRwdW1tamVieHRjIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2ODg2ODY2NCwiZXhwIjoyMDg0NDQ0NjY0fQ.L7hdOBa0b7mhU3tu8hj5TQpIn60DhitprXvHgcNjrAE"))

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
BATCH_SIZE = 20

SOCIAL_PROMPT = """Analyze this plant/nursery product image for social media marketing.

Return a JSON object with these exact keys:
{
  "alt_text": "Descriptive alt text for accessibility, 125 chars max",
  "caption_short": "Punchy Instagram caption under 150 chars with 1-2 emojis",
  "caption_long": "Longer caption (200-300 chars) with storytelling angle, plant care tip, or seasonal hook",
  "hashtag_sets": {
    "primary": ["#Plants", "#Gardening", ...5-7 broad reach tags],
    "seasonal": ["#SpringPlanting", ...3-4 seasonal/timely tags],
    "niche": ["#RarePlants", "#PlantParent", ...4-5 community tags]
  },
  "best_platform": "instagram|pinterest|facebook",
  "visual_appeal_score": 1-10,
  "content_suggestions": ["suggestion1", "suggestion2"]
}

Focus on what makes this specific plant/product visually appealing and marketable.
Be specific to what you see - leaf patterns, colors, pot style, arrangement."""


def get_supabase_client():
    """Create Supabase client."""
    if not SUPABASE_KEY:
        raise ValueError("SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY environment variable required")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def encode_image_from_url(url: str) -> tuple[str, str]:
    """Download and encode image from URL."""
    response = httpx.get(url, timeout=30, follow_redirects=True)
    response.raise_for_status()
    
    content_type = response.headers.get("content-type", "image/jpeg")
    if "png" in content_type:
        media_type = "image/png"
    elif "webp" in content_type:
        media_type = "image/webp"
    elif "gif" in content_type:
        media_type = "image/gif"
    else:
        media_type = "image/jpeg"
    
    b64 = base64.b64encode(response.content).decode("utf-8")
    return b64, media_type


def call_claude_vision(image_url: str) -> dict:
    """Call Claude API with image for social enrichment."""
    b64_data, media_type = encode_image_from_url(image_url)
    
    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64_data,
                            },
                        },
                        {"type": "text", "text": SOCIAL_PROMPT},
                    ],
                }
            ],
        },
        timeout=60,
    )
    response.raise_for_status()
    
    result = response.json()
    text = result["content"][0]["text"]
    
    # Extract JSON from response
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    
    return json.loads(text.strip())


def process_batch(batch_size: int = BATCH_SIZE):
    """Process a batch of images needing social enrichment."""
    supabase = get_supabase_client()
    
    # Get images needing enrichment
    result = supabase.table("images").select(
        "id, public_url, alt_text"
    ).or_(
        "social_enrichment_status.is.null,social_enrichment_status.eq.pending"
    ).not_.is_("public_url", "null").limit(batch_size).execute()
    
    images = result.data
    print(f"Found {len(images)} images to process")
    
    processed = 0
    errors = 0
    results_for_update = []
    
    for img in images:
        try:
            print(f"Processing {img['id']}: {img['public_url'][:60]}...")
            enrichment = call_claude_vision(img["public_url"])
            
            # Extract hashtag sets
            hashtags = enrichment.get("hashtag_sets", {})
            
            update_data = {
                "alt_text": enrichment.get("alt_text", img.get("alt_text")),
                "caption_short": enrichment.get("caption_short"),
                "caption_long": enrichment.get("caption_long"),
                "hashtag_primary": hashtags.get("primary", []),
                "hashtag_seasonal": hashtags.get("seasonal", []),
                "hashtag_niche": hashtags.get("niche", []),
                "best_platform": enrichment.get("best_platform"),
                "visual_appeal_score": enrichment.get("visual_appeal_score"),
                "content_suggestions": enrichment.get("content_suggestions", []),
                "social_enrichment_status": "done",
            }
            
            results_for_update.append({"id": img["id"], "data": update_data})
            processed += 1
            print(f"  ✓ Score: {enrichment.get('visual_appeal_score')}/10, Platform: {enrichment.get('best_platform')}")
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            errors += 1
            results_for_update.append({
                "id": img["id"],
                "data": {"social_enrichment_status": "error"}
            })
    
    # Batch update to database
    print(f"\nSaving {len(results_for_update)} results to database...")
    for item in results_for_update:
        try:
            supabase.table("images").update(item["data"]).eq("id", item["id"]).execute()
            print(f"  ✓ Saved {item['id']}")
        except Exception as e:
            print(f"  DB error for {item['id']}: {e}")
    
    print(f"\nBatch complete: {processed} processed, {errors} errors")
    return processed, errors


if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)
    
    if not SUPABASE_KEY:
        print("ERROR: SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY not set")
        sys.exit(1)
    
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else BATCH_SIZE
    process_batch(batch_size)
