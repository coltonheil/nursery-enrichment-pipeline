#!/usr/bin/env python3
"""
Investigate Failed Form Sites
Manually inspect each failed site to understand form structure.
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright


FAILED_SITES = [
    ("Sprig Native Plant", "https://sprignativenursery.com"),
    ("Dulcet Farm", "https://dulcetfarm.com"),
    ("Andy Mast", "https://andymastgreenhouses.com/contact"),
    ("Bear Creek Organics", "https://bearcreekorganicfarm.com"),
    ("Botanically Correct", "https://goodvibescannabiscompany.com/contact-us"),
    ("Bruce Helsel", "https://brucehelsel.com/contact-us"),
    ("City Farmer", "https://thecityfarmergrandhaven.org/contact"),
]

SUCCESS_SITE = ("Carpenter Farms", "https://carpenterfarmsadrian.com/contact")


async def investigate_site(page, name: str, url: str) -> dict:
    """Investigate a single site's form structure."""
    result = {
        "name": name,
        "url": url,
        "status": "unknown",
        "platform": None,
        "forms_found": [],
        "iframes": [],
        "all_inputs": [],
        "all_textareas": [],
        "all_buttons": [],
        "page_html_snippet": "",
        "error": None,
    }
    
    try:
        print(f"\n{'='*60}")
        print(f"Investigating: {name} - {url}")
        print(f"{'='*60}")
        
        response = await page.goto(url, wait_until='networkidle', timeout=30000)
        result["http_status"] = response.status if response else None
        
        # Wait for dynamic content
        await asyncio.sleep(3)
        
        # Get page HTML for platform detection
        html = await page.content()
        html_lower = html.lower()
        
        # Detect platform
        platforms = {
            "wix": ["wix.com", "wixsite", "_wix"],
            "squarespace": ["squarespace", "static1.squarespace"],
            "wordpress": ["wp-content", "wp-includes", "wordpress"],
            "shopify": ["cdn.shopify", "shopify"],
            "webflow": ["webflow", ".w-form"],
            "godaddy": ["godaddy", "secureserver.net"],
            "weebly": ["weebly"],
            "contact_form_7": ["wpcf7", "contact-form-7"],
            "gravity_forms": ["gform", "gravityforms"],
            "wpforms": ["wpforms"],
            "jotform": ["jotform"],
            "typeform": ["typeform"],
            "hubspot": ["hsforms", "hubspot"],
            "google_forms": ["docs.google.com/forms"],
        }
        
        for platform, markers in platforms.items():
            if any(marker in html_lower for marker in markers):
                result["platform"] = platform
                print(f"  Platform: {platform}")
                break
        
        # Find all forms
        forms = await page.query_selector_all('form')
        print(f"  Found {len(forms)} <form> elements")
        
        for i, form in enumerate(forms):
            form_info = {
                "index": i,
                "id": await form.get_attribute("id"),
                "class": await form.get_attribute("class"),
                "action": await form.get_attribute("action"),
                "method": await form.get_attribute("method"),
                "inputs": [],
                "textareas": [],
                "buttons": [],
            }
            
            # Get inputs in this form
            inputs = await form.query_selector_all('input')
            for inp in inputs:
                input_info = {
                    "type": await inp.get_attribute("type"),
                    "name": await inp.get_attribute("name"),
                    "id": await inp.get_attribute("id"),
                    "placeholder": await inp.get_attribute("placeholder"),
                    "visible": await inp.is_visible(),
                }
                form_info["inputs"].append(input_info)
            
            # Get textareas
            textareas = await form.query_selector_all('textarea')
            for ta in textareas:
                ta_info = {
                    "name": await ta.get_attribute("name"),
                    "id": await ta.get_attribute("id"),
                    "placeholder": await ta.get_attribute("placeholder"),
                    "visible": await ta.is_visible(),
                }
                form_info["textareas"].append(ta_info)
            
            # Get buttons
            buttons = await form.query_selector_all('button, input[type="submit"]')
            for btn in buttons:
                btn_info = {
                    "type": await btn.get_attribute("type"),
                    "text": await btn.inner_text() if await btn.evaluate("el => el.tagName") == "BUTTON" else await btn.get_attribute("value"),
                    "visible": await btn.is_visible(),
                }
                form_info["buttons"].append(btn_info)
            
            result["forms_found"].append(form_info)
            print(f"    Form {i}: {len(inputs)} inputs, {len(textareas)} textareas, {len(buttons)} buttons")
        
        # Find iframes (potential embedded forms)
        iframes = await page.query_selector_all('iframe')
        print(f"  Found {len(iframes)} iframes")
        
        for iframe in iframes:
            iframe_info = {
                "src": await iframe.get_attribute("src"),
                "id": await iframe.get_attribute("id"),
                "class": await iframe.get_attribute("class"),
                "title": await iframe.get_attribute("title"),
            }
            result["iframes"].append(iframe_info)
            if iframe_info["src"]:
                print(f"    iframe src: {iframe_info['src'][:80]}...")
        
        # Find ALL inputs on page (not just in forms)
        all_inputs = await page.query_selector_all('input:not([type="hidden"])')
        for inp in all_inputs[:20]:  # Limit to 20
            try:
                input_info = {
                    "type": await inp.get_attribute("type"),
                    "name": await inp.get_attribute("name"),
                    "id": await inp.get_attribute("id"),
                    "placeholder": await inp.get_attribute("placeholder"),
                    "visible": await inp.is_visible(),
                    "in_form": await inp.evaluate("el => !!el.closest('form')"),
                }
                result["all_inputs"].append(input_info)
            except:
                pass
        
        print(f"  Total visible inputs on page: {len([i for i in result['all_inputs'] if i.get('visible')])}")
        
        # Find ALL textareas
        all_textareas = await page.query_selector_all('textarea')
        for ta in all_textareas:
            try:
                ta_info = {
                    "name": await ta.get_attribute("name"),
                    "id": await ta.get_attribute("id"),
                    "placeholder": await ta.get_attribute("placeholder"),
                    "visible": await ta.is_visible(),
                    "in_form": await ta.evaluate("el => !!el.closest('form')"),
                }
                result["all_textareas"].append(ta_info)
            except:
                pass
        
        print(f"  Total visible textareas on page: {len([t for t in result['all_textareas'] if t.get('visible')])}")
        
        # Find ALL buttons
        all_buttons = await page.query_selector_all('button, [role="button"], input[type="submit"]')
        for btn in all_buttons[:20]:
            try:
                tag = await btn.evaluate("el => el.tagName")
                btn_info = {
                    "tag": tag,
                    "type": await btn.get_attribute("type"),
                    "text": (await btn.inner_text()).strip()[:50] if tag == "BUTTON" else await btn.get_attribute("value"),
                    "visible": await btn.is_visible(),
                    "class": await btn.get_attribute("class"),
                }
                result["all_buttons"].append(btn_info)
            except:
                pass
        
        print(f"  Total buttons on page: {len(result['all_buttons'])}")
        
        # Look for common form field patterns even without form tag
        email_inputs = await page.query_selector_all('input[type="email"], input[name*="email"], input[placeholder*="email" i]')
        print(f"  Email-like inputs: {len(email_inputs)}")
        
        # Check for Wix-specific form structure
        if result["platform"] == "wix":
            wix_forms = await page.query_selector_all('[data-hook*="form"]')
            print(f"  Wix form hooks: {len(wix_forms)}")
        
        # Check for Squarespace-specific form structure
        if result["platform"] == "squarespace":
            sqs_forms = await page.query_selector_all('.form-wrapper, .sqs-block-form')
            print(f"  Squarespace form blocks: {len(sqs_forms)}")
        
        # Save a snippet of the page HTML around form elements
        if not result["forms_found"] and not result["all_inputs"]:
            # Get body text to see what's there
            body_text = await page.evaluate("() => document.body.innerText.substring(0, 2000)")
            result["page_text_sample"] = body_text
            print(f"\n  Page text sample:\n  {body_text[:500]}...")
        
        result["status"] = "analyzed"
        
    except Exception as e:
        result["error"] = str(e)
        result["status"] = "error"
        print(f"  ERROR: {e}")
    
    return result


async def main():
    """Run investigation on all failed sites."""
    results = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Investigate success case first
        print("\n" + "="*80)
        print("INVESTIGATING SUCCESS CASE FOR COMPARISON")
        print("="*80)
        success_result = await investigate_site(page, SUCCESS_SITE[0], SUCCESS_SITE[1])
        results.append(success_result)
        
        # Investigate failed sites
        print("\n" + "="*80)
        print("INVESTIGATING FAILED SITES")
        print("="*80)
        
        for name, url in FAILED_SITES:
            result = await investigate_site(page, name, url)
            results.append(result)
            await asyncio.sleep(1)
        
        await browser.close()
    
    # Save results
    output_path = Path(__file__).parent.parent / "FORM_INVESTIGATION_REPORT.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n\nResults saved to {output_path}")
    
    # Generate summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    for r in results:
        status = "✅" if r["name"] == "Carpenter Farms" else "❌"
        forms = len(r.get("forms_found", []))
        inputs = len([i for i in r.get("all_inputs", []) if i.get("visible")])
        textareas = len([t for t in r.get("all_textareas", []) if t.get("visible")])
        iframes = len(r.get("iframes", []))
        platform = r.get("platform", "unknown")
        
        print(f"{status} {r['name']:<25} | Platform: {platform:<15} | Forms: {forms} | Inputs: {inputs} | Textareas: {textareas} | Iframes: {iframes}")
    
    return results


if __name__ == "__main__":
    asyncio.run(main())
