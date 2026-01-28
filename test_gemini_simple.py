#!/usr/bin/env python3
"""Simple test to verify Gemini client works"""

import sys
sys.path.insert(0, '.')

print("Importing gemini_client...")
from enrichment.gemini_client import enrich_lead_with_gemini
print("Import successful!")

print("\nTesting with dummy data...")
try:
    result = enrich_lead_with_gemini(
        website_text="Green Valley Nursery is a wholesale container nursery growing perennials. Contact John Smith, Operations Manager at john@greenvalley.com",
        business_name="Green Valley Nursery",
        city="Madison",
        state="WI"
    )
    print(f"✅ Success! Result: {result}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
