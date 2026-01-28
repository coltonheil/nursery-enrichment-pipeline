#!/usr/bin/env python3
"""
Test the enhanced contact extraction on 10 sample leads.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import sqlite3
from enrichment.gemini_client import enrich_lead_with_gemini
import time

def test_contact_extraction():
    """Test contact extraction on leads with website text but no owner name."""
    
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get 10 high-value leads with no owner name but have website text
    cursor.execute("""
        SELECT id, business_name, city, state, website_text, tier, owner_name
        FROM leads
        WHERE tier IN ('A', 'B')
            AND (owner_name IS NULL OR owner_name = '')
            AND website_text IS NOT NULL
            AND LENGTH(website_text) > 500
        ORDER BY tier ASC, score DESC
        LIMIT 10
    """)
    
    leads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    if not leads:
        print("❌ No suitable test leads found")
        return
    
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "CONTACT EXTRACTION TEST" + " "*30 + "║")
    print("╚" + "="*68 + "╝")
    print()
    print(f"Testing on {len(leads)} Tier A/B leads with no owner name")
    print("="*70)
    
    results = {
        'processed': 0,
        'contact_found': 0,
        'by_priority': {},
        'errors': 0
    }
    
    for i, lead in enumerate(leads, 1):
        print(f"\n[{i}/10] {lead['business_name'][:50]} (Tier {lead['tier']})")
        
        try:
            # Call Gemini with enhanced prompt
            enriched = enrich_lead_with_gemini(
                website_text=lead['website_text'],
                business_name=lead['business_name'],
                city=lead['city'],
                state=lead['state']
            )
            
            contact_name = enriched.get('contact_name')
            contact_title = enriched.get('contact_title')
            contact_priority = enriched.get('contact_priority')
            
            if contact_name:
                print(f"  ✅ Contact: {contact_name}")
                print(f"     Title: {contact_title or 'N/A'}")
                print(f"     Priority: {contact_priority} ({get_priority_label(contact_priority)})")
                results['contact_found'] += 1
                results['by_priority'][contact_priority] = results['by_priority'].get(contact_priority, 0) + 1
            else:
                print(f"  ❌ No contact found")
            
            results['processed'] += 1
            
            # Rate limit
            time.sleep(2)
            
        except Exception as e:
            print(f"  ❌ Error: {str(e)[:100]}")
            results['errors'] += 1
    
    # Summary
    print()
    print("="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Processed: {results['processed']}/10")
    print(f"Contacts found: {results['contact_found']}/10 ({results['contact_found']/10*100:.0f}%)")
    print()
    print("By Priority Level:")
    for priority in sorted(results['by_priority'].keys()):
        count = results['by_priority'][priority]
        label = get_priority_label(priority)
        print(f"  Priority {priority} ({label}): {count}")
    print()
    print(f"Errors: {results['errors']}")
    print("="*70)
    
    if results['contact_found'] >= 7:
        print("\n✅ SUCCESS: Contact extraction is working well!")
        print("   Ready to run on full 1,220 lead batch")
    elif results['contact_found'] >= 5:
        print("\n⚠️  PARTIAL: Contact extraction working but could be better")
        print("   Consider prompt refinement before full run")
    else:
        print("\n❌ FAILURE: Contact extraction needs improvement")
        print("   Review prompt and test again")

def get_priority_label(priority):
    """Get label for priority level."""
    labels = {
        1: "Owner/President",
        2: "Operations Manager",
        3: "Head Grower",
        4: "Purchasing Manager",
        5: "Propagation Manager",
        6: "Greenhouse Manager",
        7: "Sales/Marketing"
    }
    return labels.get(priority, "Unknown")

if __name__ == '__main__':
    test_contact_extraction()
