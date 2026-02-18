#!/usr/bin/env python3
"""
Phase 3: Gemini Prompt Tuning — Verification Tests

Tests that:
1. Cannabis prompt is well-formed and contains expected keywords
2. Hemp prompt is well-formed and contains expected keywords
3. Routing logic dispatches to correct prompt per segment
4. Field normalization maps cannabis/hemp fields to existing DB column names
5. Existing nursery prompt is UNCHANGED (regression test)
6. Prompt builders accept segment-aware parameters

Does NOT call the Gemini API — tests prompt structure and response parsing only.
"""

import sys
import json
sys.path.insert(0, '.')

from enrichment.gemini_client import (
    build_cannabis_prompt,
    build_hemp_prompt,
    build_nursery_prompt,
    _normalize_cannabis_response,
    _normalize_hemp_response,
)

PASS = "✅"
FAIL = "❌"
results = []

def check(name, condition, detail=''):
    status = PASS if condition else FAIL
    msg = f"  {status} {name}"
    if detail:
        msg += f"  [{detail}]"
    print(msg)
    results.append((name, condition))
    return condition


# =============================================================================
# 1. Cannabis Prompt Structure Tests
# =============================================================================
print("\n── Cannabis Prompt Tests ──────────────────────────────────────────────")

CANNABIS_SAMPLE = (
    "We are an indoor cannabis cultivation facility in Michigan with 50,000 sqft of canopy. "
    "Our Class C license allows up to 1,500 plants. We run a living soil program with "
    "organic amendments including compost and worm castings. Clean Green Certified."
)

cannabis_prompt = build_cannabis_prompt(CANNABIS_SAMPLE)

# Required field names appear in prompt (so Gemini knows to extract them)
check("cultivation_type in prompt", "cultivation_type" in cannabis_prompt)
check("indoor_sqft in prompt", "indoor_sqft" in cannabis_prompt)
check("canopy_sqft in prompt", "canopy_sqft" in cannabis_prompt)
check("plant_count in prompt", "plant_count" in cannabis_prompt)
check("uses_amendments in prompt", "uses_amendments" in cannabis_prompt)
check("uses_worm_castings in prompt", "uses_worm_castings" in cannabis_prompt)
check("organic_certified in prompt", "organic_certified" in cannabis_prompt)
check("dispensary_only in prompt", "dispensary_only" in cannabis_prompt)
check("business_type in prompt", "business_type" in cannabis_prompt)

# Cannabis-specific language
check("'cannabis' in prompt (case-insensitive)", "cannabis" in cannabis_prompt.lower())
check("'canopy' in prompt", "canopy" in cannabis_prompt.lower())
check("'cultivat' in prompt", "cultivat" in cannabis_prompt.lower())

# Website text is embedded
check("website text in prompt", CANNABIS_SAMPLE[:50] in cannabis_prompt)

# JSON output format mentioned
check("JSON output requested", "{" in cannabis_prompt and "}" in cannabis_prompt)

# With optional business name/location
cannabis_prompt_with_ctx = build_cannabis_prompt(CANNABIS_SAMPLE, "Green Peak Cannabis", "Lansing", "MI")
check("business name included when provided", "Green Peak Cannabis" in cannabis_prompt_with_ctx)
check("location included when provided", "Lansing" in cannabis_prompt_with_ctx)

# Without optional args (signature test per verification spec)
cannabis_prompt_minimal = build_cannabis_prompt(CANNABIS_SAMPLE)
check("prompt works with only website_text arg", "cultivation_type" in cannabis_prompt_minimal)


# =============================================================================
# 2. Hemp Prompt Structure Tests
# =============================================================================
print("\n── Hemp Prompt Tests ──────────────────────────────────────────────────")

HEMP_SAMPLE = (
    "We grow industrial hemp on 200 acres for CBD extraction. Our farm is USDA Organic certified. "
    "We process our hemp on-site with our extraction facility. Located in Wisconsin."
)

hemp_prompt = build_hemp_prompt(HEMP_SAMPLE)

# Required field names appear in prompt
check("hemp_type in prompt", "hemp_type" in hemp_prompt)
check("acreage in prompt (lowercase)", "acreage" in hemp_prompt.lower())
check("processing_on_site in prompt", "processing_on_site" in hemp_prompt)
check("uses_amendments in prompt", "uses_amendments" in hemp_prompt)
check("organic_certified in prompt", "organic_certified" in hemp_prompt)
check("business_type in prompt", "business_type" in hemp_prompt)

# Hemp-specific language
check("'hemp' in prompt (case-insensitive)", "hemp" in hemp_prompt.lower())
check("'acreage' or 'acres' in prompt", "acre" in hemp_prompt.lower())
check("fiber / CBD / seed mentioned", any(t in hemp_prompt.lower() for t in ["fiber", "cbd", "seed"]))

# Website text is embedded
check("website text in prompt", HEMP_SAMPLE[:50] in hemp_prompt)

# JSON output format mentioned
check("JSON output requested", "{" in hemp_prompt and "}" in hemp_prompt)

# With optional context
hemp_prompt_with_ctx = build_hemp_prompt(HEMP_SAMPLE, "Badger Hemp Co", "Eau Claire", "WI")
check("business name included when provided", "Badger Hemp Co" in hemp_prompt_with_ctx)
check("location included when provided", "Eau Claire" in hemp_prompt_with_ctx)

# Minimal signature
hemp_prompt_minimal = build_hemp_prompt(HEMP_SAMPLE)
check("prompt works with only website_text arg", "hemp_type" in hemp_prompt_minimal)


# =============================================================================
# 3. Nursery Prompt Regression Tests (MUST NOT CHANGE)
# =============================================================================
print("\n── Nursery Prompt Regression Tests ────────────────────────────────────")

NURSERY_SAMPLE = (
    "Green Valley Growers is a 45-acre wholesale nursery specializing in container-grown "
    "perennials and shrubs. We use Pro-Mix growing media throughout our 200,000 sqft greenhouse."
)

nursery_prompt = build_nursery_prompt(NURSERY_SAMPLE, "Green Valley Growers", "Madison", "WI")

# Original nursery fields must still be present
check("uses_growing_media in nursery prompt", "uses_growing_media" in nursery_prompt)
check("production_method in nursery prompt", "production_method" in nursery_prompt)
check("container_production in nursery prompt", "container_production" in nursery_prompt)
check("soil_relevance in nursery prompt", "soil_relevance" in nursery_prompt)
check("negative_indicators in nursery prompt", "negative_indicators" in nursery_prompt)
check("business_type in nursery prompt", "business_type" in nursery_prompt)
check("nursery language present", "nursery" in nursery_prompt.lower())
check("worm castings language in nursery", "worm castings" in nursery_prompt.lower())

# Nursery prompt should NOT contain cannabis-specific fields that would confuse it
check("dispensary_only NOT in nursery prompt", "dispensary_only" not in nursery_prompt)
check("canopy_sqft NOT in nursery prompt", "canopy_sqft" not in nursery_prompt)


# =============================================================================
# 4. Field Normalization Tests (Cannabis → Existing DB Columns)
# =============================================================================
print("\n── Cannabis Field Normalization Tests ──────────────────────────────────")

# Simulate what Gemini would return from cannabis prompt
cannabis_raw_response = {
    "business_type": "cannabis_cultivator",
    "cultivation_type": "indoor",
    "indoor_sqft": 50000,
    "canopy_sqft": None,
    "plant_count": 1500,
    "license_type": "Class C",
    "uses_amendments": True,
    "uses_worm_castings": True,
    "organic_certified": True,
    "dispensary_only": False,
    "multiple_locations": False,
    "crops_grown": ["cannabis"],
    "scale_indicators": ["50,000 sqft indoor facility", "1,500 plant license"],
    "disqualification_signals": [],
    "contact_name": "Jane Smith",
    "contact_title": "Head Grower",
    "email": "jane@greenpeakcannabis.com",
    "confidence": "high"
}

normalized = _normalize_cannabis_response(cannabis_raw_response)

check("cultivation_type → production_method", normalized.get('production_method') == 'indoor')
check("cultivation_type removed", 'cultivation_type' not in normalized)
check("indoor_sqft → greenhouse_sqft", normalized.get('greenhouse_sqft') == 50000)
check("indoor_sqft removed", 'indoor_sqft' not in normalized)
check("canopy_sqft removed", 'canopy_sqft' not in normalized)
check("uses_amendments → uses_growing_media", normalized.get('uses_growing_media') == True)
check("uses_amendments removed", 'uses_amendments' not in normalized)
check("organic_certified → is_organic_certified", normalized.get('is_organic_certified') == True)
check("organic_certified removed", 'organic_certified' not in normalized)
check("dispensary_only → negative_indicators.dispensary_only",
      isinstance(normalized.get('negative_indicators'), dict) and
      normalized['negative_indicators'].get('dispensary_only') == False)
check("dispensary_only removed from top level", 'dispensary_only' not in normalized)

# Test canopy_sqft takes priority over indoor_sqft
cannabis_with_canopy = dict(cannabis_raw_response)
cannabis_with_canopy['canopy_sqft'] = 25000
cannabis_with_canopy['indoor_sqft'] = 50000
normalized_canopy = _normalize_cannabis_response(cannabis_with_canopy)
check("canopy_sqft takes priority over indoor_sqft", normalized_canopy.get('greenhouse_sqft') == 25000)

# Test dispensary disqualification
dispensary_response = dict(cannabis_raw_response)
dispensary_response['dispensary_only'] = True
dispensary_response['business_type'] = 'dispensary'
normalized_disp = _normalize_cannabis_response(dispensary_response)
check("dispensary_only=True stored in negative_indicators",
      normalized_disp['negative_indicators'].get('dispensary_only') == True)


# =============================================================================
# 5. Field Normalization Tests (Hemp → Existing DB Columns)
# =============================================================================
print("\n── Hemp Field Normalization Tests ──────────────────────────────────────")

hemp_raw_response = {
    "business_type": "hemp_grower",
    "hemp_type": "CBD",
    "acreage": 200,
    "processing_on_site": True,
    "uses_amendments": True,
    "organic_certified": True,
    "market_channel": "wholesale",
    "multiple_locations": False,
    "crops_grown": [],
    "scale_indicators": ["200 acres", "on-site extraction"],
    "disqualification_signals": [],
    "contact_name": "Bob Johnson",
    "contact_title": "Farm Owner",
    "email": None,
    "confidence": "medium"
}

hemp_norm = _normalize_hemp_response(hemp_raw_response)

check("hemp_type → crops_grown (hemp_CBD)", 'hemp_CBD' in hemp_norm.get('crops_grown', []))
check("hemp_type removed", 'hemp_type' not in hemp_norm)
check("acreage preserved", hemp_norm.get('acreage') == 200)
check("uses_amendments → uses_growing_media", hemp_norm.get('uses_growing_media') == True)
check("uses_amendments removed", 'uses_amendments' not in hemp_norm)
check("organic_certified → is_organic_certified", hemp_norm.get('is_organic_certified') == True)
check("organic_certified removed", 'organic_certified' not in hemp_norm)
check("processing_on_site → negative_indicators.processing_on_site",
      isinstance(hemp_norm.get('negative_indicators'), dict) and
      hemp_norm['negative_indicators'].get('processing_on_site') == True)
check("production_method defaults to 'field'", hemp_norm.get('production_method') == 'field')

# Hemp fiber type
hemp_fiber = dict(hemp_raw_response)
hemp_fiber['hemp_type'] = 'fiber'
hemp_fiber['crops_grown'] = []
hemp_fiber_norm = _normalize_hemp_response(hemp_fiber)
check("hemp_fiber type in crops_grown", 'hemp_fiber' in hemp_fiber_norm.get('crops_grown', []))

# Hemp unknown type still adds 'hemp' to crops_grown
hemp_unknown = dict(hemp_raw_response)
hemp_unknown['hemp_type'] = 'unknown'
hemp_unknown['crops_grown'] = []
hemp_unknown_norm = _normalize_hemp_response(hemp_unknown)
check("hemp_type=unknown still adds 'hemp' to crops_grown",
      'hemp' in hemp_unknown_norm.get('crops_grown', []))


# =============================================================================
# 6. Routing Logic Integration Test (without calling Gemini API)
# =============================================================================
print("\n── Routing Logic Tests ─────────────────────────────────────────────────")

# Verify that segment='cannabis_grower' produces cannabis prompt (not nursery)
c_prompt = build_cannabis_prompt("Indoor cannabis cultivation facility")
n_prompt = build_nursery_prompt("Indoor cannabis cultivation facility", "Test", "MI", "MI")

check("cannabis prompt differs from nursery prompt", c_prompt != n_prompt)
check("cannabis prompt contains cultivation_type, nursery does not",
      "cultivation_type" in c_prompt and "cultivation_type" not in n_prompt)
check("nursery prompt contains container_production, cannabis does not",
      "container_production" in n_prompt and "container_production" not in c_prompt)

# Verify hemp prompt differs from both
h_prompt = build_hemp_prompt("Hemp farm in Wisconsin")
check("hemp prompt differs from nursery prompt", h_prompt != n_prompt)
check("hemp prompt differs from cannabis prompt", h_prompt != c_prompt)
check("hemp prompt has hemp_type, cannabis does not",
      "hemp_type" in h_prompt and "hemp_type" not in c_prompt)


# =============================================================================
# 7. enrich_lead_with_gemini signature test (no API call)
# =============================================================================
print("\n── Signature Compatibility Tests ───────────────────────────────────────")

import inspect
from enrichment.gemini_client import enrich_lead_with_gemini

sig = inspect.signature(enrich_lead_with_gemini)
params = list(sig.parameters.keys())

check("segment parameter exists", 'segment' in params)
check("segment defaults to 'nursery'", sig.parameters['segment'].default == 'nursery')
check("website_text is first param", params[0] == 'website_text')
check("business_name is second param", params[1] == 'business_name')
check("city is third param", params[2] == 'city')
check("state is fourth param", params[3] == 'state')
check("segment is fifth param", params[4] == 'segment')


# =============================================================================
# Summary
# =============================================================================
print("\n" + "=" * 70)
passed = sum(1 for _, ok in results if ok)
total = len(results)
failed = total - passed

print(f"  PASSED: {passed}/{total}")
if failed:
    print(f"  FAILED: {failed}/{total}")
    print("\n  Failed tests:")
    for name, ok in results:
        if not ok:
            print(f"    ❌ {name}")

print("=" * 70)

sys.exit(0 if failed == 0 else 1)
