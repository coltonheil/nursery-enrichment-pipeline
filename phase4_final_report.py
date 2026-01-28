#!/usr/bin/env python3
"""
Phase 4: Generate final report and summary.
"""

import sqlite3
from datetime import datetime

DB_PATH = 'data/leads.db'

def generate_report():
    """Generate final project report."""
    
    print("=" * 70)
    print("PHASE 4: FINAL REPORT - NURSERY ENRICHMENT PIPELINE")
    print("=" * 70)
    print()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Overall statistics
    print("📊 OVERALL STATISTICS")
    print("-" * 70)
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B')")
    total_ab = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B') AND contact_name IS NOT NULL AND contact_name != ''")
    total_contacts = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B') AND contact_email IS NOT NULL AND contact_email != ''")
    total_personal_emails = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM leads WHERE tier IN ('A', 'B') AND owner_email IS NOT NULL")
    total_generic_emails = cursor.fetchone()[0]
    
    print(f"Total Tier A+B leads: {total_ab}")
    print(f"Contacts extracted: {total_contacts} ({total_contacts/total_ab*100:.1f}%)")
    print(f"Personal emails: {total_personal_emails} ({total_personal_emails/total_ab*100:.1f}%)")
    print(f"Generic emails: {total_generic_emails} ({total_generic_emails/total_ab*100:.1f}%)")
    print(f"Total email coverage: {total_generic_emails} ({total_generic_emails/total_ab*100:.1f}%)")
    print()
    
    # Tier breakdown
    print("📈 TIER BREAKDOWN")
    print("-" * 70)
    
    cursor.execute("""
        SELECT 
            tier,
            COUNT(*) as total,
            SUM(CASE WHEN contact_name IS NOT NULL AND contact_name != '' THEN 1 ELSE 0 END) as contacts,
            SUM(CASE WHEN contact_email IS NOT NULL AND contact_email != '' THEN 1 ELSE 0 END) as personal_emails,
            SUM(CASE WHEN owner_email IS NOT NULL THEN 1 ELSE 0 END) as generic_emails
        FROM leads 
        WHERE tier IN ('A', 'B')
        GROUP BY tier
        ORDER BY tier
    """)
    
    for row in cursor.fetchall():
        tier, total, contacts, personal, generic = row
        print(f"\nTier {tier}: {total} leads")
        print(f"  Contacts: {contacts} ({contacts/total*100:.1f}%)")
        print(f"  Personal emails: {personal} ({personal/total*100:.1f}%)")
        print(f"  Generic emails: {generic} ({generic/total*100:.1f}%)")
    
    print()
    
    # Before/After comparison
    print("🔄 IMPROVEMENT SUMMARY")
    print("-" * 70)
    print("Before pipeline enhancement:")
    print("  Contacts: 2 (0.3%)")
    print("  Personal emails: 4 (0.6%)")
    print()
    print("After Phase 2-3 completion:")
    print(f"  Contacts: {total_contacts} ({total_contacts/total_ab*100:.1f}%) → {total_contacts/2:.1f}x improvement")
    print(f"  Personal emails: {total_personal_emails} ({total_personal_emails/total_ab*100:.1f}%) → {total_personal_emails/4:.1f}x improvement")
    print()
    
    # Email confidence breakdown
    print("🎯 EMAIL CONFIDENCE BREAKDOWN")
    print("-" * 70)
    
    cursor.execute("""
        SELECT 
            CASE 
                WHEN email_confidence >= 70 THEN 'High (≥70%)'
                WHEN email_confidence >= 50 THEN 'Medium (50-69%)'
                WHEN email_confidence >= 20 THEN 'Low (20-49%)'
                ELSE 'Generic (<20%)'
            END as confidence_level,
            COUNT(*) as count
        FROM leads
        WHERE tier IN ('A', 'B') 
          AND contact_email IS NOT NULL 
          AND contact_email != ''
        GROUP BY confidence_level
        ORDER BY MIN(email_confidence) DESC
    """)
    
    for row in cursor.fetchall():
        level, count = row
        print(f"  {level}: {count}")
    
    print()
    
    # Sample contacts
    print("👥 SAMPLE CONTACTS EXTRACTED (Top 10 Tier A)")
    print("-" * 70)
    
    cursor.execute("""
        SELECT business_name, contact_name, contact_title, contact_email, tier
        FROM leads
        WHERE tier = 'A'
          AND contact_name IS NOT NULL
          AND contact_name != ''
        ORDER BY score DESC
        LIMIT 10
    """)
    
    for idx, row in enumerate(cursor.fetchall(), 1):
        business, name, title, email, tier = row
        title_str = f" ({title})" if title else ""
        email_str = f" - {email}" if email else ""
        print(f"  {idx}. {name}{title_str} - {business}{email_str}")
    
    print()
    
    # Cost/Value analysis
    print("💰 COST/VALUE ANALYSIS")
    print("-" * 70)
    print("Total cost: $0.40 (Gemini API)")
    print(f"Contacts extracted: {total_contacts}")
    print(f"Cost per contact: ${0.40/total_contacts:.4f}")
    print()
    print(f"Value (@ $5/contact): ${total_contacts * 5:.2f}")
    print(f"ROI: {(total_contacts * 5 / 0.40):.0f}x")
    print()
    
    # Next steps
    print("✅ NEXT STEPS")
    print("-" * 70)
    print("1. Export Tier A+B leads to CSV for Instantly.ai")
    print("2. Prioritize Tier A (highest scores) for first outreach")
    print("3. Use contact names for personalization")
    print("4. Fall back to generic emails where personal not available")
    print()
    
    print("=" * 70)
    print(f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    conn.close()
    return True

if __name__ == '__main__':
    generate_report()
