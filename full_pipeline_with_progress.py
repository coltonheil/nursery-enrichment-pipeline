"""
Full enrichment pipeline: Phase 1 (Gemini extraction) + Phase 2 (Email search)
Reports progress every 50 leads.
"""

import time
from database.models import get_db_connection, log_action
from enrichment.gemini_client import enrich_lead_with_gemini
from email_search_enrichment import (
    brave_search, fetch_page, extract_emails_from_text,
    find_best_email, calculate_email_confidence
)

def run_full_pipeline(batch_size=500, progress_interval=50):
    """Run Phase 1 + Phase 2 on all Tier A+B leads."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get leads needing contact extraction
    cursor.execute(f"""
        SELECT id, business_name, city, state, website_text, tier, score
        FROM leads
        WHERE tier IN ('A', 'B')
          AND (contact_name IS NULL OR contact_name = '')
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 1000
        ORDER BY 
          CASE tier WHEN 'A' THEN 1 WHEN 'B' THEN 2 END,
          score DESC
        LIMIT {batch_size}
    """)
    
    leads = cursor.fetchall()
    
    print("=" * 80)
    print("FULL ENRICHMENT PIPELINE (Phase 1 + Phase 2)")
    print("=" * 80)
    print(f"Total leads to process: {len(leads)}")
    print()
    
    stats = {
        'total': len(leads),
        'contacts_found': 0,
        'emails_found': 0,
        'high_conf': 0,
        'medium_conf': 0,
        'low_conf': 0,
        'very_low_conf': 0,
        'phase1_errors': 0,
        'phase2_errors': 0
    }
    
    for idx, lead in enumerate(leads, 1):
        lead_id, business_name, city, state, website_text, tier, score = lead
        
        print(f"[{idx}/{len(leads)}] {business_name} (Tier {tier}, Score: {score})", flush=True)
        
        # PHASE 1: Extract contact via Gemini
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
            gemini_email = enriched.get('email')
            
            if contact_name:
                stats['contacts_found'] += 1
                print(f"   ✅ Contact: {contact_name}", end="", flush=True)
                if contact_title:
                    print(f" ({contact_title})", end="", flush=True)
                print(flush=True)
                
                # Update database with contact
                cursor.execute("""
                    UPDATE leads
                    SET contact_name = ?, contact_title = ?, contact_priority = ?
                    WHERE id = ?
                """, (contact_name, contact_title, contact_priority, lead_id))
                conn.commit()
                
                # PHASE 2: Search for email if Gemini didn't find one
                if not gemini_email:
                    print(f"   🔍 Searching for email...", flush=True)
                    
                    try:
                        # Search
                        query = f'{business_name} {contact_name} email'
                        results = brave_search(query, count=2)
                        
                        found_email = None
                        found_confidence = 0
                        
                        # Check snippets
                        for result in results:
                            snippet = result.get('description', '')
                            title = result.get('title', '')
                            combined = f"{title} {snippet}"
                            
                            emails = extract_emails_from_text(combined)
                            if emails:
                                best = find_best_email(emails, contact_name, business_name)
                                if best:
                                    confidence = calculate_email_confidence(best, contact_name, business_name, 'snippet')
                                    found_email = best
                                    found_confidence = confidence
                                    break
                        
                        # Fetch pages if needed
                        if not found_email:
                            for result in results[:2]:
                                url = result.get('url', '')
                                if not url or 'spokeo.com' in url.lower():
                                    continue
                                
                                try:
                                    page_text = fetch_page(url, timeout=5)
                                    emails = extract_emails_from_text(page_text)
                                    
                                    if emails:
                                        best = find_best_email(emails, contact_name, business_name)
                                        if best:
                                            confidence = calculate_email_confidence(best, contact_name, business_name, 'page')
                                            found_email = best
                                            found_confidence = confidence
                                            break
                                except:
                                    pass
                        
                        if found_email:
                            # Confidence indicator
                            if found_confidence >= 80:
                                conf_icon = "✅"
                                stats['high_conf'] += 1
                            elif found_confidence >= 50:
                                conf_icon = "⚠️ "
                                stats['medium_conf'] += 1
                            elif found_confidence >= 20:
                                conf_icon = "⚙️ "
                                stats['low_conf'] += 1
                            else:
                                conf_icon = "❓"
                                stats['very_low_conf'] += 1
                            
                            print(f"   {conf_icon} Email: {found_email} ({found_confidence}%)", flush=True)
                            
                            # Update database with email
                            cursor.execute("""
                                UPDATE leads
                                SET owner_email = ?, email_confidence = ?
                                WHERE id = ?
                            """, (found_email, found_confidence, lead_id))
                            conn.commit()
                            
                            stats['emails_found'] += 1
                    
                    except Exception as e:
                        stats['phase2_errors'] += 1
                        print(f"   ⚠️  Email search failed: {str(e)[:50]}", flush=True)
                
                else:
                    # Gemini found email
                    print(f"   📧 Email (Gemini): {gemini_email}", flush=True)
                    cursor.execute("""
                        UPDATE leads
                        SET owner_email = ?, email_confidence = 85
                        WHERE id = ?
                    """, (gemini_email, lead_id))
                    conn.commit()
                    stats['emails_found'] += 1
                    stats['medium_conf'] += 1
            
            else:
                print(f"   ⚠️  No contact found", flush=True)
        
        except Exception as e:
            stats['phase1_errors'] += 1
            print(f"   ❌ Phase 1 error: {str(e)[:80]}", flush=True)
        
        # Progress report every 50 leads
        if idx % progress_interval == 0 or idx == len(leads):
            print()
            print("=" * 80)
            print(f"PROGRESS REPORT: {idx}/{len(leads)} leads processed ({idx/len(leads)*100:.1f}%)")
            print("=" * 80)
            print(f"Contacts found: {stats['contacts_found']} ({stats['contacts_found']/idx*100:.1f}%)")
            print(f"Emails found: {stats['emails_found']} ({stats['emails_found']/idx*100:.1f}%)")
            print()
            print("Email confidence breakdown:")
            print(f"  High (80-100): {stats['high_conf']} ✅")
            print(f"  Medium (50-79): {stats['medium_conf']} ⚠️ ")
            print(f"  Low (20-49): {stats['low_conf']} ⚙️ ")
            print(f"  Very Low (0-19): {stats['very_low_conf']} ❓")
            print()
            print(f"Errors: Phase 1: {stats['phase1_errors']}, Phase 2: {stats['phase2_errors']}")
            print("=" * 80)
            print()
        
        # Rate limiting
        time.sleep(1.2)
    
    conn.close()
    
    # Final summary
    print()
    print("=" * 80)
    print("PIPELINE COMPLETE")
    print("=" * 80)
    print(f"Total processed: {stats['total']}")
    print(f"Contacts found: {stats['contacts_found']} ({stats['contacts_found']/stats['total']*100:.1f}%)")
    print(f"Emails found: {stats['emails_found']} ({stats['emails_found']/stats['total']*100:.1f}%)")
    print()

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    
    run_full_pipeline(batch_size=500, progress_interval=50)
