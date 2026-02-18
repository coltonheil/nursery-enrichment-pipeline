"""
Test script to verify all enrichment buttons and routes are working.
Tests Flask API endpoints without requiring browser interaction.
"""

import requests
import time

BASE_URL = "http://localhost:5000"

def test_scrape_start():
    """Test scraping start endpoint."""
    print("Testing: POST /scrape/start")
    try:
        response = requests.post(f"{BASE_URL}/scrape/start")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"  Error: {e}")
        return False

def test_ai_enrich_start():
    """Test AI enrichment start endpoint."""
    print("\nTesting: POST /enrich-ai/start (all leads)")
    try:
        response = requests.post(f"{BASE_URL}/enrich-ai/start")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"  Error: {e}")
        return False

def test_ai_enrich_batch():
    """Test AI enrichment with batch size."""
    print("\nTesting: POST /enrich-ai/start (batch size: 5)")
    try:
        response = requests.post(
            f"{BASE_URL}/enrich-ai/start",
            json={"batch_size": 5},
            headers={"Content-Type": "application/json"}
        )
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"  Error: {e}")
        return False

def test_score_all():
    """Test scoring endpoint."""
    print("\nTesting: POST /score/all")
    try:
        response = requests.post(f"{BASE_URL}/score/all")
        print(f"  Status: {response.status_code}")
        data = response.json()
        print(f"  Response: {data.get('message', data)}")
        return response.status_code == 200
    except Exception as e:
        print(f"  Error: {e}")
        return False

def test_personalize_start():
    """Test personalization endpoint."""
    print("\nTesting: POST /personalize/start")
    try:
        response = requests.post(f"{BASE_URL}/personalize/start")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"  Error: {e}")
        return False

def test_health():
    """Test health endpoint."""
    print("\nTesting: GET /health")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"  Error: {e}")
        return False

def test_leads_page():
    """Test leads page loads."""
    print("\nTesting: GET /leads")
    try:
        response = requests.get(f"{BASE_URL}/leads")
        print(f"  Status: {response.status_code}")
        print(f"  Page size: {len(response.text)} bytes")
        return response.status_code == 200
    except Exception as e:
        print(f"  Error: {e}")
        return False

def main():
    print("=" * 60)
    print("Button & Route Testing")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print()

    results = {}

    # Test health first
    results['health'] = test_health()
    time.sleep(0.5)

    # Test leads page
    results['leads_page'] = test_leads_page()
    time.sleep(0.5)

    # Test score all (safe, no side effects)
    results['score_all'] = test_score_all()
    time.sleep(0.5)

    # Test AI enrich batch (safe with small batch)
    results['ai_enrich_batch'] = test_ai_enrich_batch()
    time.sleep(0.5)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {test_name}")

    print()
    print(f"Results: {passed}/{total} tests passed")
    print()

    if passed == total:
        print("All tests passed! Buttons should work in the UI.")
    else:
        print("Some tests failed. Check Flask app logs for errors.")
        print("\nCommon issues:")
        print("  - Flask app not running (start with: python app.py)")
        print("  - Jobs already running (stop them first)")
        print("  - Missing data (import leads first)")

    return passed == total

if __name__ == '__main__':
    main()
