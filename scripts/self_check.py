#!/usr/bin/env python3
"""
Self-Check Validator
===================
Automated validation that pipeline outputs meet quality targets.
"""

import sqlite3
import sys
from typing import Dict, List, Tuple

DB_PATH = 'data/leads.db'

# Target thresholds
TARGETS = {
    'campaign_ready_min': 1000,
    'extraction_rate_min': 0.25,
    'error_rate_max': 0.10,
    'avg_text_length_min': 1500,
    'email_confidence_high_min': 0.40
}


def get_stats() -> Dict:
    """Get current pipeline statistics."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Campaign-ready count
    cursor.execute("""
        SELECT COUNT(*) 
        FROM leads
        WHERE tier IN ('A', 'B', 'C', 'U')
          AND (owner_name IS NOT NULL OR contact_name IS NOT NULL)
          AND (owner_email IS NOT NULL OR contact_email IS NOT NULL)
    """)
    campaign_ready = cursor.fetchone()[0]
    
    # Enrichment stats
    cursor.execute("""
        SELECT 
            COUNT(*) as total_with_text,
            SUM(CASE WHEN owner_name IS NOT NULL OR contact_name IS NOT NULL THEN 1 ELSE 0 END) as extracted,
            AVG(LENGTH(website_text)) as avg_text_len
        FROM leads
        WHERE tier IN ('A', 'B', 'C', 'U')
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 1000
    """)
    row = cursor.fetchone()
    total_with_text = row[0]
    extracted = row[1]
    avg_text_len = row[2]
    
    extraction_rate = extracted / total_with_text if total_with_text > 0 else 0
    
    # Email confidence
    cursor.execute("""
        SELECT 
            COUNT(*) as total_emails,
            SUM(CASE WHEN email_confidence >= 80 THEN 1 ELSE 0 END) as high_confidence
        FROM leads
        WHERE tier IN ('A', 'B', 'C', 'U')
          AND (owner_email IS NOT NULL OR contact_email IS NOT NULL)
          AND email_confidence IS NOT NULL
    """)
    row = cursor.fetchone()
    total_emails = row[0] or 0
    high_confidence = row[1] or 0
    
    email_confidence_high_rate = high_confidence / total_emails if total_emails > 0 else 0
    
    conn.close()
    
    return {
        'campaign_ready': campaign_ready,
        'total_with_text': total_with_text,
        'extracted': extracted,
        'extraction_rate': extraction_rate,
        'avg_text_length': avg_text_len or 0,
        'total_emails': total_emails,
        'high_confidence_emails': high_confidence,
        'email_confidence_high_rate': email_confidence_high_rate
    }


def run_checks(stats: Dict) -> Tuple[bool, List[str], List[str]]:
    """Run all validation checks. Returns (all_passed, failures, warnings)."""
    failures = []
    warnings = []
    
    # Check 1: Campaign-ready count
    if stats['campaign_ready'] < TARGETS['campaign_ready_min']:
        failures.append(
            f"❌ Campaign-ready: {stats['campaign_ready']} < {TARGETS['campaign_ready_min']} target"
        )
    else:
        print(f"✅ Campaign-ready: {stats['campaign_ready']} >= {TARGETS['campaign_ready_min']}")
    
    # Check 2: Extraction rate
    if stats['extraction_rate'] < TARGETS['extraction_rate_min']:
        failures.append(
            f"❌ Extraction rate: {stats['extraction_rate']:.1%} < {TARGETS['extraction_rate_min']:.0%} target"
        )
    else:
        print(f"✅ Extraction rate: {stats['extraction_rate']:.1%} >= {TARGETS['extraction_rate_min']:.0%}")
    
    # Check 3: Average text length
    if stats['avg_text_length'] < TARGETS['avg_text_length_min']:
        warnings.append(
            f"⚠️  Avg text length: {stats['avg_text_length']:.0f} chars < {TARGETS['avg_text_length_min']} target"
        )
    else:
        print(f"✅ Avg text length: {stats['avg_text_length']:.0f} chars >= {TARGETS['avg_text_length_min']}")
    
    # Check 4: Email confidence
    if stats['total_emails'] > 0:
        if stats['email_confidence_high_rate'] < TARGETS['email_confidence_high_min']:
            warnings.append(
                f"⚠️  High-confidence emails: {stats['email_confidence_high_rate']:.1%} < {TARGETS['email_confidence_high_min']:.0%} target"
            )
        else:
            print(f"✅ High-confidence emails: {stats['email_confidence_high_rate']:.1%} >= {TARGETS['email_confidence_high_min']:.0%}")
    else:
        warnings.append("⚠️  No email confidence data available")
    
    all_passed = len(failures) == 0
    return all_passed, failures, warnings


def main():
    print("=" * 80)
    print("PIPELINE SELF-CHECK")
    print("=" * 80)
    print()
    
    stats = get_stats()
    
    print("Current Statistics:")
    print(f"  Campaign-ready: {stats['campaign_ready']}")
    print(f"  Leads with content: {stats['total_with_text']}")
    print(f"  Contacts extracted: {stats['extracted']} ({stats['extraction_rate']:.1%})")
    print(f"  Avg text length: {stats['avg_text_length']:.0f} chars")
    print(f"  Emails with confidence: {stats['total_emails']}")
    print(f"  High-confidence (≥80%): {stats['high_confidence_emails']} ({stats['email_confidence_high_rate']:.1%})")
    print()
    
    print("Running Checks:")
    print("-" * 80)
    
    all_passed, failures, warnings = run_checks(stats)
    
    print()
    
    if failures:
        print("FAILURES:")
        for fail in failures:
            print(f"  {fail}")
        print()
    
    if warnings:
        print("WARNINGS:")
        for warn in warnings:
            print(f"  {warn}")
        print()
    
    if all_passed and not warnings:
        print("=" * 80)
        print("✅ ALL CHECKS PASSED - Pipeline output is good!")
        print("=" * 80)
        return 0
    elif all_passed and warnings:
        print("=" * 80)
        print("⚠️  CHECKS PASSED WITH WARNINGS - Review warnings above")
        print("=" * 80)
        return 0
    else:
        print("=" * 80)
        print("❌ CHECKS FAILED - Fix issues before deploying")
        print("=" * 80)
        return 1


if __name__ == '__main__':
    sys.exit(main())
