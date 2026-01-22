"""
Diagnostic script to understand why leads are scoring 0 points (Tier U).
Checks what data is available for scoring.
"""

from database.models import get_db_connection
from enrichment.scorer import calculate_score
import json

def diagnose_scoring_issue():
    """Check why leads are getting score 0 / Tier U."""

    print("=" * 80)
    print("SCORING DIAGNOSIS")
    print("=" * 80)
    print()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get a sample of 5 leads
    cursor.execute('''
        SELECT * FROM leads
        ORDER BY imported_at DESC
        LIMIT 5
    ''')
    sample_leads = cursor.fetchall()

    print(f"Checking {len(sample_leads)} sample leads...\n")

    for i, lead in enumerate(sample_leads, 1):
        print(f"Lead {i}: {lead['business_name']}")
        print("-" * 80)

        # Check enrichment status
        print(f"  Enrichment Status: {lead['enrichment_status']}")
        print(f"  Scrape Status: {lead['scrape_status']}")
        print(f"  Gemini Status: {lead['gemini_status']}")
        print()

        # Check key data fields for scoring
        has_data = False

        print("  Data Available for Scoring:")

        # Google Places data
        if lead['phone']:
            print(f"    [YES] Phone: {lead['phone']}")
            has_data = True
        else:
            print("    [NO] Phone: None")

        if lead['website']:
            print(f"    [YES] Website: {lead['website']}")
            has_data = True
        else:
            print("    [NO] Website: None")

        if lead['rating']:
            print(f"    [YES] Rating: {lead['rating']}")
            has_data = True
        else:
            print("    [NO] Rating: None")

        if lead['hours']:
            print(f"    [YES] Hours: Yes")
            has_data = True
        else:
            print("    [NO] Hours: None")

        # Gemini AI data
        if lead['business_type']:
            print(f"    [YES] Business Type: {lead['business_type']}")
            has_data = True
        else:
            print("    [NO] Business Type: None")

        if lead['is_wholesale']:
            print(f"    [YES] Is Wholesale: True")
            has_data = True
        else:
            print("    [NO] Is Wholesale: False/None")

        if lead['organic_focus']:
            print(f"    [YES] Organic Focus: True")
            has_data = True

        if lead['container_production']:
            print(f"    [YES] Container Production: True")
            has_data = True

        if lead['greenhouse_sqft']:
            print(f"    [YES] Greenhouse: {lead['greenhouse_sqft']} sq ft")
            has_data = True

        if lead['acreage']:
            print(f"    [YES] Acreage: {lead['acreage']}")
            has_data = True

        if lead['crops_grown']:
            try:
                crops = json.loads(lead['crops_grown'])
                if crops:
                    print(f"    [YES] Crops Grown: {len(crops)} crops")
                    has_data = True
            except:
                pass

        print()

        # Try to score this lead
        print("  Attempting to Score:")
        score_data = calculate_score(lead)

        print(f"    Score: {score_data['total']}")
        print(f"    Tier: {score_data['tier']}")
        print(f"    Has Data: {score_data['has_data']}")
        print(f"    Signals Triggered: {len(score_data['signals'])}")

        if score_data['signals']:
            print("    Active Signals:")
            for signal in score_data['signals']:
                print(f"      {signal['signal']}: {signal['points']} pts - {signal['description']}")
        else:
            print("    [!] NO SIGNALS TRIGGERED - This is why score is 0!")

        print()
        print()

    # Summary
    print("=" * 80)
    print("DIAGNOSIS SUMMARY")
    print("=" * 80)
    print()

    # Check overall enrichment status (reuse existing connection)
    cursor.execute('''
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN enrichment_status = 'enriched' THEN 1 ELSE 0 END) as google_enriched,
            SUM(CASE WHEN scrape_status = 'scraped' THEN 1 ELSE 0 END) as scraped,
            SUM(CASE WHEN gemini_status = 'enriched' THEN 1 ELSE 0 END) as gemini_enriched
        FROM leads
    ''')
    stats = cursor.fetchone()
    conn.close()

    print(f"Total Leads: {stats['total']}")
    print(f"Google Places Enriched: {stats['google_enriched']} ({stats['google_enriched']/stats['total']*100:.1f}%)")
    print(f"Website Scraped: {stats['scraped']} ({stats['scraped']/stats['total']*100:.1f}%)")
    print(f"Gemini AI Enriched: {stats['gemini_enriched']} ({stats['gemini_enriched']/stats['total']*100:.1f}%)")
    print()

    # Diagnosis
    if stats['gemini_enriched'] == 0:
        print("[!] PROBLEM IDENTIFIED:")
        print("   NO leads have been enriched with Gemini AI!")
        print()
        print("   The scoring engine needs Gemini enrichment data to work:")
        print("   - business_type (nursery, wholesale, retail, etc.)")
        print("   - is_wholesale (yes/no)")
        print("   - organic_focus (yes/no)")
        print("   - container_production (yes/no)")
        print("   - greenhouse_sqft, acreage, crops_grown, etc.")
        print()
        print("   Without this data, ALL leads will score 0 points = Tier U")
        print()
        print("[+] SOLUTION:")
        print("   1. Run 'Scrape Websites' first (if not done)")
        print("   2. Run 'AI Enrich' to extract business data")
        print("   3. THEN run 'Score Leads'")
        print()
    elif stats['google_enriched'] < stats['total'] * 0.5:
        print("[!] PROBLEM IDENTIFIED:")
        print(f"   Only {stats['google_enriched']} leads have Google Places data")
        print("   Scoring works better with more data")
        print()
    else:
        print("[+] Enrichment looks good!")
        print("   The scoring issue may be in the scoring logic itself.")
        print()

if __name__ == '__main__':
    diagnose_scoring_issue()
