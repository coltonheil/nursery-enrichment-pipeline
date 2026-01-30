#!/usr/bin/env python3
"""
Test ALL originally failed sites with the new Form Detector V2.
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.form_detector_v2 import FormDetectorV2, FieldType


# ALL original test sites
ALL_SITES = [
    # SUCCESS case
    ("Carpenter Farms ✅", "https://carpenterfarmsadrian.com/contact"),
    # Originally failed
    ("Sprig Native Plant", "https://sprignativenursery.com"),
    ("Dulcet Farm", "https://dulcetfarm.com"),
    ("Andy Mast", "https://andymastgreenhouses.com/contact"),
    ("Bear Creek Organics", "https://bearcreekorganicfarm.com"),
    ("Botanically Correct", "https://goodvibescannabiscompany.com/contact-us"),
    ("Bruce Helsel", "https://brucehelsel.com/contact-us"),
    ("City Farmer", "https://thecityfarmergrandhaven.org/contact"),
]


async def test_site(detector, name, url, page):
    """Test a single site."""
    result = {
        "name": name,
        "url": url,
        "success": False,
        "fields": [],
        "strategy": None,
        "platform": None,
        "issues": [],
        "blocked": False,
    }
    
    try:
        print(f"\n{'='*60}")
        print(f"{name}: {url}")
        
        response = await page.goto(url, wait_until='networkidle', timeout=30000)
        result["http_status"] = response.status if response else None
        await asyncio.sleep(2)
        
        analysis = await detector.analyze_form(page)
        
        result["strategy"] = analysis.detection_strategy.value
        result["platform"] = analysis.platform
        result["issues"] = analysis.issues
        result["blocked"] = analysis.page_blocked
        result["confidence"] = analysis.confidence
        
        if analysis.has_required_fields():
            result["success"] = True
            result["fields"] = [
                {"type": f.field_type.value, "selector": f.selector}
                for f in analysis.fields
            ]
            print(f"  ✅ FORM FOUND - {len(analysis.fields)} fields ({analysis.detection_strategy.value})")
            for f in analysis.fields:
                print(f"     {f.field_type.value}: {f.selector[:40]}")
        else:
            if analysis.page_blocked:
                print(f"  🚫 BLOCKED - {analysis.issues}")
            else:
                print(f"  ❌ NO FORM - {analysis.issues}")
                
    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ ERROR: {e}")
    
    return result


async def main():
    print("="*80)
    print("COMPREHENSIVE FORM DETECTION TEST - ALL SITES")
    print("="*80)
    
    detector = FormDetectorV2()
    results = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        for name, url in ALL_SITES:
            result = await test_site(detector, name, url, page)
            results.append(result)
            await asyncio.sleep(1)
        
        await browser.close()
    
    # Summary
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    
    success_count = sum(1 for r in results if r["success"])
    blocked_count = sum(1 for r in results if r["blocked"])
    
    print(f"\nSuccess: {success_count}/{len(results)}")
    print(f"Blocked: {blocked_count}")
    print(f"Failed: {len(results) - success_count - blocked_count}")
    
    print("\n" + "-"*80)
    for r in results:
        status = "✅" if r["success"] else ("🚫" if r["blocked"] else "❌")
        fields = len(r.get("fields", []))
        strategy = r.get("strategy", "N/A")
        print(f"{status} {r['name']:<25} Fields:{fields:2} Strategy:{strategy:<15} Issues:{r.get('issues', [])}")
    
    # Calculate improvement
    original_success = 1  # Only Carpenter Farms
    new_success = success_count
    improvement = new_success - original_success
    
    print(f"\n📈 IMPROVEMENT: {original_success} → {new_success} (+{improvement} sites)")
    print(f"   Success rate: {original_success}/{len(results)} → {new_success}/{len(results)}")
    print(f"   Percentage: {original_success/len(results)*100:.0f}% → {new_success/len(results)*100:.0f}%")
    
    # Save results
    output_path = Path(__file__).parent.parent / "FINAL_TEST_RESULTS.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\nResults saved to {output_path}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
