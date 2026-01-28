"""Quick batch re-extraction - no prompts, just run."""
import time
from database.models import get_db_connection, log_action
from enrichment.gemini_client import enrich_lead_with_gemini

# Get leads
conn = get_db_connection()
cursor = conn.cursor()

query = """
    SELECT id, business_name, city, state, website_text, tier
    FROM leads
    WHERE (tier = 'A' OR tier = 'B')
      AND (owner_email IS NULL OR owner_email = '')
      AND website_text IS NOT NULL
      AND LENGTH(website_text) > 1000
    ORDER BY 
        CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 END,
        score DESC
    LIMIT 50
"""

cursor.execute(query)
leads = cursor.fetchall()

print(f"Processing {len(leads)} leads...")
print()

success = 0
errors = 0
new_contacts = 0
new_emails = 0

for idx, lead in enumerate(leads, 1):
    lead_id, business_name, city, state, website_text, tier = lead
    
    print(f"[{idx}/{len(leads)}] {business_name} (Tier {tier})", flush=True)
    
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
            new_contacts += 1
            print(f"   ✅ Contact: {contact_name}", end="", flush=True)
            if contact_title:
                print(f" ({contact_title})", end="", flush=True)
            print(flush=True)
        
        if owner_email:
            new_emails += 1
            print(f"   📧 Email: {owner_email}", flush=True)
        
        if not contact_name and not owner_email:
            print(f"   ⚠️  No improvements", flush=True)
        
        # Update database (with timeout)
        conn.execute("PRAGMA busy_timeout = 5000")  # 5 second timeout
        cursor.execute("""
            UPDATE leads
            SET contact_name = ?, contact_title = ?, contact_priority = ?, owner_email = ?
            WHERE id = ?
        """, (contact_name, contact_title, contact_priority, owner_email, lead_id))
        
        conn.commit()
        success += 1
        
    except Exception as e:
        errors += 1
        print(f"   ❌ Error: {str(e)[:100]}", flush=True)
    
    time.sleep(1.2)

conn.close()

print()
print(f"Complete: {success} success, {errors} errors")
print(f"New contacts: {new_contacts}, New emails: {new_emails}")
