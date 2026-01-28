"""
Re-extract contacts for Tier A+B leads that don't have emails yet.
Uses updated aggressive extraction prompt.
"""

import sys
import time
from database.models import get_db_connection, log_action
from enrichment.gemini_client import enrich_lead_with_gemini

def reextract_contacts():
    """Re-extract contacts for leads without emails."""
    
    print("=" * 80)
    print("RE-EXTRACTING CONTACTS (No Email Leads)")
    print("=" * 80)
    print()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get Tier A+B leads without emails, with website text
    query = """
        SELECT id, business_name, city, state, website_text, tier
        FROM leads
        WHERE (tier = 'A' OR tier = 'B')
          AND (owner_email IS NULL OR owner_email = '')
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 1000
        ORDER BY 
            CASE tier 
                WHEN 'A' THEN 1 
                WHEN 'B' THEN 2 
            END,
            score DESC
    """
    
    cursor.execute(query)
    leads = cursor.fetchall()
    
    total = len(leads)
    print(f"Found {total} Tier A+B leads without emails")
    print()
    
    if total == 0:
        print("✅ All Tier A+B leads already have emails!")
        return
    
    # Confirm
    print("This will:")
    print(f"  • Re-run Gemini extraction on {total} leads")
    print(f"  • Cost: ~${total * 0.001:.2f} (Gemini 2.0 Flash)")
    print(f"  • Time: ~{total * 2 / 60:.1f} minutes (2s per lead)")
    print()
    print("Auto-starting (batch mode)...")
    
    print()
    print("Starting re-extraction...")
    print()
    
    success_count = 0
    error_count = 0
    new_contacts_found = 0
    new_emails_found = 0
    
    for idx, lead in enumerate(leads, 1):
        lead_id, business_name, city, state, website_text, tier = lead
        
        print(f"[{idx}/{total}] {business_name} (Tier {tier})")
        
        try:
            # Call Gemini with updated prompt
            enriched = enrich_lead_with_gemini(
                website_text=website_text,
                business_name=business_name,
                city=city,
                state=state
            )
            
            # Update contact fields
            contact_name = enriched.get('contact_name')
            contact_title = enriched.get('contact_title')
            contact_priority = enriched.get('contact_priority')
            owner_email = enriched.get('email')
            
            # Count improvements
            if contact_name:
                new_contacts_found += 1
                print(f"   ✅ Contact: {contact_name}", end="")
                if contact_title:
                    print(f" ({contact_title})", end="")
                if contact_priority:
                    print(f" [Priority {contact_priority}]", end="")
                print()
            
            if owner_email:
                new_emails_found += 1
                print(f"   📧 Email: {owner_email}")
            
            if not contact_name and not owner_email:
                print(f"   ⚠️  No improvements")
            
            # Update database
            update_query = """
                UPDATE leads
                SET contact_name = ?,
                    contact_title = ?,
                    contact_priority = ?,
                    owner_email = ?,
                    gemini_status = 'enriched'
                WHERE id = ?
            """
            cursor.execute(update_query, (
                contact_name,
                contact_title,
                contact_priority,
                owner_email,
                lead_id
            ))
            
            conn.commit()
            success_count += 1
            
            # Log processing
            log_action(
                lead_id=lead_id,
                action='contact_reextraction',
                details=f"Contact: {contact_name or 'None'}, Email: {owner_email or 'None'}",
                cursor=cursor
            )
            
        except Exception as e:
            error_count += 1
            error_msg = str(e)[:200]
            print(f"   ❌ Error: {error_msg}")
            
            log_action(
                lead_id=lead_id,
                action='contact_reextraction_failed',
                details=error_msg,
                cursor=cursor
            )
        
        # Rate limiting (1 request per second)
        if idx < total:
            time.sleep(1.2)
    
    conn.close()
    
    # Summary
    print()
    print("=" * 80)
    print("RE-EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"Total processed: {total}")
    print(f"Success: {success_count}")
    print(f"Errors: {error_count}")
    print()
    print(f"New contacts found: {new_contacts_found} ({new_contacts_found/total*100:.1f}%)")
    print(f"New emails found: {new_emails_found} ({new_emails_found/total*100:.1f}%)")
    print()
    
    if new_contacts_found > 0:
        print("✅ Next step: Run email hunting on new contacts")
        print("   Command: python email_hunter.py")
    
    print()

if __name__ == '__main__':
    reextract_contacts()
