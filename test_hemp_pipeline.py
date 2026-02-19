"""
Hemp Pipeline End-to-End Test
Runs 5 hemp leads through all 4 pipeline steps directly.
"""
import sys
import time
import sqlite3
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.models import get_db_connection
from enrichment.enrichment_router import enrich_lead_step1
from enrichment.web_scraper import scrape_and_extract
from enrichment.gemini_client import enrich_lead_with_gemini
from enrichment.scorer import calculate_score

HEMP_LEAD_IDS = [10812, 10813, 10814, 10815, 10816]

def get_lead(lead_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def update_lead(lead_id, **fields):
    conn = get_db_connection()
    c = conn.cursor()
    set_clause = ', '.join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [lead_id]
    c.execute(f"UPDATE leads SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()

def run_google_places(lead):
    segment = lead.get('segment', 'nursery')
    source_label = 'Web Search' if segment in ('hemp', 'cannabis') else 'Google Places'
    print(f"\n  [Step 1: {source_label}]")
    try:
        result = enrich_lead_step1(lead)
        if 'error' in result:
            update_lead(lead['id'], enrichment_status='failed')
            print(f"  ❌ Failed: {result['error']}")
            return False
        # Update DB with places data
        update_fields = {
            'enrichment_status': 'enriched',
            'phone': result.get('phone'),
            'website': result.get('website'),
            'rating': result.get('rating'),
            'review_count': result.get('review_count'),
            'place_id': result.get('place_id'),
            'google_maps_url': result.get('google_maps_url'),
        }
        update_lead(lead['id'], **{k: v for k, v in update_fields.items() if v is not None})
        src = result.get('enrichment_source', 'unknown')
        print(f"  ✅ [{src}] website={result.get('website')} | phone={result.get('phone')} | rating={result.get('rating')}")
        return True
    except Exception as e:
        update_lead(lead['id'], enrichment_status='failed')
        print(f"  ❌ Exception: {str(e)[:100]}")
        return False

def run_scraper(lead):
    print(f"  [Step 2: Web Scrape]")
    lead = get_lead(lead['id'])  # Re-fetch to get website from Google Places
    website = lead.get('website')
    if not website:
        update_lead(lead['id'], scrape_status='failed', scrape_error='No website found')
        print(f"  ⚠️  No website — skipping scrape")
        return False
    try:
        text, status_info = scrape_and_extract(website)
        if text and len(text) > 100:
            update_lead(lead['id'],
                scrape_status='scraped',
                website_text=text[:50000],
                scraped_at=time.strftime('%Y-%m-%d %H:%M:%S'))
            print(f"  ✅ Scraped {len(text)} chars from {website}")
            return True
        else:
            err = status_info.get('error', 'Insufficient content') if isinstance(status_info, dict) else 'Insufficient content'
            update_lead(lead['id'], scrape_status='failed', scrape_error=err[:200])
            print(f"  ❌ Insufficient content: {err[:80]}")
            return False
    except Exception as e:
        update_lead(lead['id'], scrape_status='failed', scrape_error=str(e)[:200])
        print(f"  ❌ Exception: {str(e)[:100]}")
        return False

def run_gemini(lead):
    print(f"  [Step 3: Gemini AI (hemp prompt)]")
    lead = get_lead(lead['id'])  # Re-fetch with website_text
    website_text = lead.get('website_text')
    if not website_text or len(website_text) < 100:
        update_lead(lead['id'], gemini_status='failed', gemini_error='No website text')
        print(f"  ❌ No website text available")
        return False
    try:
        result = enrich_lead_with_gemini(
            website_text=website_text,
            business_name=lead['business_name'],
            city=lead['city'],
            state=lead['state'],
            segment='hemp'  # Will be normalized to hemp_producer in gemini_client
        )
        # Save enrichment
        update_fields = {
            'gemini_status': 'enriched',
            'business_type': result.get('business_type'),
            'is_wholesale': result.get('is_wholesale'),
            'is_retail': result.get('is_retail'),
            'organic_focus': result.get('organic_focus') or result.get('organic_certified') or result.get('is_organic_certified'),
            'crops_grown': str(result.get('crops_grown', [])),
            # Hemp prompt returns 'uses_amendments'; nursery returns 'uses_growing_media' — handle both
            'uses_growing_media': result.get('uses_growing_media') or result.get('uses_amendments'),
            'production_method': result.get('production_method'),
            'is_organic_certified': result.get('is_organic_certified') or result.get('organic_certified'),
            'acreage': result.get('acreage'),
            'gemini_confidence': result.get('confidence'),
            'gemini_enriched_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'disqualification_signals': str(result.get('disqualification_signals', [])),
            'scale_indicators': str(result.get('scale_indicators', [])),
        }
        if result.get('email'):
            update_fields['owner_email'] = result['email']
        if result.get('contact_name'):
            update_fields['owner_name'] = result['contact_name']
        update_lead(lead['id'], **{k: v for k, v in update_fields.items() if v is not None})
        print(f"  ✅ type={result.get('business_type')} | hemp_type={result.get('hemp_type')} | acreage={result.get('acreage')} | organic={result.get('organic_certified')} | disqualifiers={result.get('disqualification_signals')}")
        time.sleep(1)  # Rate limit
        return True
    except Exception as e:
        update_lead(lead['id'], gemini_status='failed', gemini_error=str(e)[:200])
        print(f"  ❌ Exception: {str(e)[:150]}")
        return False

def run_scoring(lead):
    print(f"  [Step 4: Scoring]")
    try:
        lead = get_lead(lead['id'])
        score_result = calculate_score(lead)
        score = score_result.get('total', 0)
        tier = score_result.get('tier', 'U')
        icp_type = score_result.get('icp_type', '')
        update_lead(lead['id'],
            score=score,
            tier=tier,
            icp_type=icp_type,
            score_breakdown=str(score_result.get('signals', [])),
            scored_at=time.strftime('%Y-%m-%d %H:%M:%S'))
        print(f"  ✅ Score={score} | Tier={tier} | ICP={icp_type}")
        return True
    except Exception as e:
        print(f"  ❌ Scoring failed: {str(e)[:100]}")
        return False

def main():
    print("=" * 60)
    print("Hemp Pipeline End-to-End Test — 5 Leads")
    print("=" * 60)

    results = []

    for lead_id in HEMP_LEAD_IDS:
        lead = get_lead(lead_id)
        if not lead:
            print(f"\n[{lead_id}] NOT FOUND")
            continue

        print(f"\n[{lead_id}] {lead['business_name']}, {lead['city']} {lead['state']}")

        gp_ok = run_google_places(lead)
        sc_ok = run_scraper(lead)
        gm_ok = run_gemini(lead) if sc_ok else False
        sg_ok = run_scoring(lead) if gm_ok else False

        lead = get_lead(lead_id)
        results.append({
            'id': lead_id,
            'name': lead['business_name'],
            'steps': f"places={'✅' if gp_ok else '❌'} scrape={'✅' if sc_ok else '❌'} gemini={'✅' if gm_ok else '❌'} score={'✅' if sg_ok else '❌'}",
            'tier': lead.get('tier'),
            'score': lead.get('score'),
            'type': lead.get('business_type'),
            'email': lead.get('owner_email'),
            'website': lead.get('website'),
        })

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for r in results:
        print(f"\n[{r['id']}] {r['name']}")
        print(f"  Steps: {r['steps']}")
        print(f"  Tier={r['tier']} | Score={r['score']} | Type={r['type']}")
        print(f"  Website: {r['website']}")
        print(f"  Email: {r['email']}")

if __name__ == '__main__':
    main()
