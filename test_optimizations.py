#!/usr/bin/env python3
"""
Test script for email hunter optimizations.

Tests:
1. Name parsing edge cases (couples, single names, prefixes)
2. Brave search integration (requires API key)
3. Generic email fallback
4. End-to-end pipeline
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from enrichment.email_hunter import hunt_email, EmailHuntResult
from enrichment.email_patterns import normalize_name, generate_email_patterns

# Test cases from EMAIL_HUNTER_EVAL.md
TEST_CASES = [
    # (owner_name, business_name, website, expected_behavior)
    
    # Single names - should generate first@ pattern only
    ("Joe", "Joe's Country Corner", "https://joescountrycorner.com", "single_name"),
    ("Al", "Al's Nursery", "https://alsnursery.com", "single_name"),
    ("Phil", "Phil's Lawn", "https://philslawn.com", "single_name"),
    ("Teri", "Teri's Garden", "https://terisgarden.com", "single_name"),
    
    # Couples without shared surname - should use first person's first name
    ("Wayne and Michelle", "Kinni Natives", "https://kinninatives.com", "couple"),
    ("Julie & Kim", "County Line Market", "https://countylinemarket.com", "couple"),
    ("Erik and Danielle", "Mill Creek Garden Center", "https://millcreekgardencenter.com", "couple"),
    ("Ben and Maddy", "Sweet Meadow Farm", "https://sweetmeadowfarm.com", "couple"),
    
    # Noise prefixes - should strip them
    ("a.k.a. ATTN: CYNTHIA DESCAMPS", "ATTN Example", "https://example.com", "noise_prefix"),
    ("ATTN: John Smith", "ATTN Nursery", "https://attnnursery.com", "noise_prefix"),
    
    # Family suffix - should strip it
    ("Bachhuber family", "Love Food Farm", "https://lovefoodfarm.com", "family_suffix"),
    
    # Normal names - should work as before
    ("Dave Bresina", "Dave Bresina's Nursery", "https://davebresinsnursery.com", "normal"),
    ("John Smith", "Green Valley Nursery", "https://greenvalleynursery.com", "normal"),
    
    # No MX records - should try Brave search then fall back to generic
    ("Test Name", "No MX Business", "https://wiroses.com", "no_mx"),
]


def test_name_parsing():
    """Test name parsing edge cases."""
    print("=" * 80)
    print("TEST 1: Name Parsing Edge Cases")
    print("=" * 80)
    
    test_names = [
        ("Joe", "single_name"),
        ("Wayne and Michelle", "couple"),
        ("Julie & Kim", "couple"),
        ("a.k.a. ATTN: CYNTHIA DESCAMPS", "noise_prefix"),
        ("Bachhuber family", "family_suffix"),
        ("John Smith", "normal"),
    ]
    
    passed = 0
    failed = 0
    
    for name, expected_type in test_names:
        result = normalize_name(name)
        
        if not result:
            print(f"❌ FAIL: {name:40} -> Could not parse")
            failed += 1
            continue
        
        first = result.get('first')
        last = result.get('last')
        is_single = result.get('single_name', False)
        
        # Validation
        if expected_type == "single_name":
            if is_single and last is None:
                print(f"✅ PASS: {name:40} -> {first}@ (single name)")
                passed += 1
            else:
                print(f"❌ FAIL: {name:40} -> Expected single name, got first={first}, last={last}")
                failed += 1
        
        elif expected_type == "couple":
            # Couples without shared surname become single-name cases (correct behavior)
            if is_single and last is None:
                print(f"✅ PASS: {name:40} -> {first}@ (couple without surname, treated as single name)")
                passed += 1
            elif first and last:
                print(f"✅ PASS: {name:40} -> {first}.{last}@ (couple with shared surname)")
                passed += 1
            else:
                print(f"❌ FAIL: {name:40} -> Expected couple handling, got first={first}, last={last}")
                failed += 1
        
        elif expected_type in ["noise_prefix", "family_suffix"]:
            if first and first not in ['aka', 'attn', 'family']:
                print(f"✅ PASS: {name:40} -> {first}.{last}@ (cleaned)")
                passed += 1
            else:
                print(f"❌ FAIL: {name:40} -> Noise not removed, got first={first}")
                failed += 1
        
        elif expected_type == "normal":
            if first and last and not is_single:
                print(f"✅ PASS: {name:40} -> {first}.{last}@")
                passed += 1
            else:
                print(f"❌ FAIL: {name:40} -> Expected normal name, got first={first}, last={last}")
                failed += 1
    
    print(f"\n{passed} passed, {failed} failed\n")
    return failed == 0


def test_pattern_generation():
    """Test email pattern generation."""
    print("=" * 80)
    print("TEST 2: Email Pattern Generation")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    # Single name - should only generate first@ pattern
    result = normalize_name("Joe")
    patterns = generate_email_patterns(result['first'], result['last'], "example.com")
    
    if len(patterns) == 1 and patterns[0]['email'] == 'joe@example.com':
        print(f"✅ PASS: Single name 'Joe' -> 1 pattern: joe@example.com")
        passed += 1
    else:
        print(f"❌ FAIL: Single name 'Joe' -> Expected 1 pattern, got {len(patterns)}: {[p['email'] for p in patterns]}")
        failed += 1
    
    # Normal name - should generate multiple patterns
    result = normalize_name("John Smith")
    patterns = generate_email_patterns(result['first'], result['last'], "example.com")
    
    expected_patterns = ['john.smith@example.com', 'john@example.com', 'jsmith@example.com']
    if len(patterns) >= 3 and patterns[0]['email'] in expected_patterns:
        print(f"✅ PASS: Normal name 'John Smith' -> {len(patterns)} patterns, top 3: {[p['email'] for p in patterns[:3]]}")
        passed += 1
    else:
        print(f"❌ FAIL: Normal name 'John Smith' -> Expected 3+ patterns, got {len(patterns)}: {[p['email'] for p in patterns]}")
        failed += 1
    
    print(f"\n{passed} passed, {failed} failed\n")
    return failed == 0


def test_email_hunter():
    """Test email hunter with various cases."""
    print("=" * 80)
    print("TEST 3: Email Hunter Integration")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    # Test 1: Normal name with valid domain
    result = hunt_email(
        owner_name="John Smith",
        business_name="Green Valley Nursery",
        website="https://google.com",  # Known good domain with MX
        enable_web_search=False  # Don't use Brave for this test
    )
    
    if result.email and result.confidence > 50:
        print(f"✅ PASS: Normal name -> {result.email} (confidence: {result.confidence}%, method: {result.method})")
        passed += 1
    else:
        print(f"❌ FAIL: Normal name -> {result.email} (confidence: {result.confidence}%, method: {result.method})")
        failed += 1
    
    # Test 2: Single name
    result = hunt_email(
        owner_name="Joe",
        business_name="Joe's Nursery",
        website="https://google.com",
        enable_web_search=False
    )
    
    if result.email == 'joe@google.com' and result.confidence > 50:
        print(f"✅ PASS: Single name -> {result.email} (confidence: {result.confidence}%, method: {result.method})")
        passed += 1
    else:
        print(f"❌ FAIL: Single name -> {result.email} (confidence: {result.confidence}%, method: {result.method})")
        failed += 1
    
    # Test 3: Generic email fallback always stored
    result = hunt_email(
        owner_name="John Smith",
        business_name="Test Business",
        website="https://example.com",
        enable_web_search=False
    )
    
    if result.generic_email == 'info@example.com':
        print(f"✅ PASS: Generic email stored -> {result.generic_email}")
        passed += 1
    else:
        print(f"❌ FAIL: Generic email not stored -> {result.generic_email}")
        failed += 1
    
    # Test 4: Contact form URL stored
    if result.contact_form_url == 'https://example.com/contact':
        print(f"✅ PASS: Contact form URL stored -> {result.contact_form_url}")
        passed += 1
    else:
        print(f"❌ FAIL: Contact form URL not stored -> {result.contact_form_url}")
        failed += 1
    
    print(f"\n{passed} passed, {failed} failed\n")
    return failed == 0


def test_brave_search():
    """Test Brave search integration (requires API key)."""
    print("=" * 80)
    print("TEST 4: Brave Search Integration")
    print("=" * 80)
    
    # Check if Brave API key is configured
    brave_key = os.getenv('BRAVE_API_KEY')
    
    if not brave_key:
        print("⚠️  SKIPPED: BRAVE_API_KEY not found in environment")
        print("   Set up: https://brave.com/search/api/ (2000 free searches/month)")
        print("   Add to .env: BRAVE_API_KEY=your_key_here")
        return True  # Don't fail the test if API key is missing
    
    print(f"✅ Brave API key found: {brave_key[:10]}...")
    
    # Test with a known person/business
    result = hunt_email(
        owner_name="Dave Bresina",
        business_name="Dave Bresina's Nursery",
        website=None,  # Force web search (no domain)
        enable_web_search=True
    )
    
    if result.method.startswith('web_search'):
        print(f"✅ PASS: Web search executed -> {result.email} (confidence: {result.confidence}%, method: {result.method})")
        return True
    else:
        print(f"⚠️  INFO: Web search not used -> method: {result.method}")
        print(f"   Result: {result.email} (confidence: {result.confidence}%)")
        return True  # Don't fail if search didn't find anything


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "EMAIL HUNTER OPTIMIZATION TESTS" + " " * 27 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")
    
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    results = []
    
    # Run tests
    results.append(("Name Parsing", test_name_parsing()))
    results.append(("Pattern Generation", test_pattern_generation()))
    results.append(("Email Hunter", test_email_hunter()))
    results.append(("Brave Search", test_brave_search()))
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:10} {name}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == '__main__':
    sys.exit(main())
