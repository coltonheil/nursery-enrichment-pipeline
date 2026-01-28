"""Quick test of updated contact extraction on 5 leads."""

import sys
from database.models import get_db_connection
from enrichment.gemini_client import enrich_lead_with_gemini

def test_sample():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get 5 random leads without emails
    query = """
        SELECT id, business_name, city, state, website_text, tier
        FROM leads
        WHERE (tier = 'A' OR tier = 'B')
          AND (owner_email IS NULL OR owner_email = '')
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 1000
        ORDER BY RANDOM()
        LIMIT 5
    """
    
    cursor.execute(query)
    leads = cursor.fetchall()
    
    print("Testing updated extraction on 5 random leads...")
    print()
    
    for idx, lead in enumerate(leads, 1):
        lead_id, business_name, city, state, website_text, tier = lead
        
        print(f"[{idx}/5] {business_name} (Tier {tier})")
        print(f"   Website text: {len(website_text)} chars")
        
        try:
            enriched = enrich_lead_with_gemini(
                website_text=website_text,
                business_name=business_name,
                city=city,
                state=state
            )
            
            contact_name = enriched.get('contact_name')
            contact_title = enriched.get('contact_title')
            contact_priority = enriched.get('contact_priority')
            owner_email = enriched.get('email')
            
            if contact_name:
                print(f"   ✅ Contact: {contact_name}", end="")
                if contact_title:
                    print(f" ({contact_title})", end="")
                if contact_priority:
                    print(f" [Priority {contact_priority}]", end="")
                print()
            else:
                print(f"   ⚠️  No contact found")
            
            if owner_email:
                print(f"   📧 Email: {owner_email}")
            
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:100]}")
        
        print()
    
    conn.close()

if __name__ == '__main__':
    test_sample()
