#!/usr/bin/env python3
"""
Test Form Detection V2 on Failed Sites

Verifies that the new form detector correctly identifies forms
on sites that previously failed.
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

# Import the new detector
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.form_detector_v2 import FormDetectorV2, FieldType


# Test sites - focus on ones that SHOULD work
TEST_SITES = [
    # SUCCESS case - baseline
    ("Carpenter Farms", "https://carpenterfarmsadrian.com/contact", True),
    # Should work after fix (form exists, selector was the issue)  
    ("Andy Mast", "https://andymastgreenhouses.com/contact", True),
    # Should work after fix (form exists, detection was the issue)
    ("Bruce Helsel", "https://brucehelsel.com/contact-us", True),
    # These likely don't have proper contact forms
    ("Sprig Native", "https://sprignativenursery.com", False),
    ("Bear Creek", "https://bearcreekorganicfarm.com", False),
]


async def test_single_site(detector: FormDetectorV2, name: str, url: str, 
                           expected_success: bool, page) -> dict:
    """Test form detection on a single site."""
    result = {
        "name": name,
        "url": url,
        "expected_success": expected_success,
        "actual_success": False,
        "fields_found": [],
        "detection_strategy": None,
        "issues": [],
        "error": None,
    }
    
    try:
        print(f"\n{'='*60}")
        print(f"Testing: {name}")
        print(f"URL: {url}")
        print(f"Expected: {'SUCCESS' if expected_success else 'FAIL'}")
        print(f"{'='*60}")
        
        # Navigate to page
        response = await page.goto(url, wait_until='networkidle', timeout=30000)
        await asyncio.sleep(2)  # Let JS render
        
        # Run detection
        analysis = await detector.analyze_form(page)
        
        result["detection_strategy"] = analysis.detection_strategy.value
        result["platform"] = analysis.platform
        result["issues"] = analysis.issues
        result["page_blocked"] = analysis.page_blocked
        
        # Check if form was found
        if analysis.has_required_fields():
            result["actual_success"] = True
            print(f"✅ Form FOUND!")
            print(f"  Strategy: {analysis.detection_strategy.value}")
            print(f"  Platform: {analysis.platform}")
            print(f"  Confidence: {analysis.confidence:.2f}")
            print(f"  Fields:")
            for field in analysis.fields:
                result["fields_found"].append({
                    "type": field.field_type.value,
                    "selector": field.selector,
                    "element": field.element_type,
                })
                print(f"    - {field.field_type.value}: {field.selector}")
            
            if analysis.submit_selector:
                print(f"  Submit: {analysis.submit_selector}")
        else:
            print(f"❌ No form found")
            print(f"  Issues: {analysis.issues}")
            
            # Show what was detected anyway
            if analysis.fields:
                print(f"  Partial fields found:")
                for field in analysis.fields:
                    result["fields_found"].append({
                        "type": field.field_type.value,
                        "selector": field.selector,
                    })
                    print(f"    - {field.field_type.value}: {field.selector}")
        
        # Verify selectors work (critical test for the CSS bug)
        if analysis.fields:
            print("\n  Selector Validation:")
            for field in analysis.fields:
                try:
                    element = await page.query_selector(field.selector)
                    visible = await element.is_visible() if element else False
                    status = "✓" if element and visible else ("⚠ hidden" if element else "✗ not found")
                    print(f"    {field.selector[:50]:50s} {status}")
                except Exception as e:
                    print(f"    {field.selector[:50]:50s} ✗ ERROR: {e}")
                    result["issues"].append(f"Selector error: {field.selector} - {e}")
        
        # Check expectations
        match = result["actual_success"] == expected_success
        result["matches_expected"] = match
        if match:
            print(f"\n✅ Result matches expectation")
        else:
            print(f"\n⚠️ Result does NOT match expectation!")
            
    except Exception as e:
        result["error"] = str(e)
        print(f"❌ ERROR: {e}")
    
    return result


async def main():
    """Run form detection tests."""
    print("="*80)
    print("FORM DETECTOR V2 TEST SUITE")
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
        
        for name, url, expected in TEST_SITES:
            result = await test_single_site(detector, name, url, expected, page)
            results.append(result)
            await asyncio.sleep(1)
        
        await browser.close()
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    success_count = sum(1 for r in results if r["actual_success"])
    expected_success = sum(1 for r in results if r["expected_success"])
    match_count = sum(1 for r in results if r.get("matches_expected", False))
    
    print(f"\nForms detected: {success_count}/{len(results)}")
    print(f"Expected successes: {expected_success}")
    print(f"Matching expectations: {match_count}/{len(results)}")
    
    print("\nDetailed Results:")
    for r in results:
        expected = "✓" if r["expected_success"] else "✗"
        actual = "✓" if r["actual_success"] else "✗"
        match = "✅" if r.get("matches_expected") else "⚠️"
        fields = len(r["fields_found"])
        print(f"  {match} {r['name']:<20} Expected:{expected} Actual:{actual} Fields:{fields} Strategy:{r.get('detection_strategy', 'N/A')}")
    
    # Save results
    output_path = Path(__file__).parent.parent / "FORM_TEST_RESULTS.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
