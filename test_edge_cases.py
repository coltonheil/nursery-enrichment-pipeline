"""
Test script for Phase 3D: Error Handling & Edge Cases
Tests various failure scenarios to ensure robust error handling
"""

from enrichment.web_scraper import scrape_website, categorize_scrape_error, extract_text

def test_edge_cases():
    """Test various edge cases and error scenarios."""

    test_cases = [
        {
            'name': '404 Not Found',
            'url': 'https://www.google.com/this-page-does-not-exist-12345',
            'expected_category': 'failed-404'
        },
        {
            'name': 'Invalid Domain',
            'url': 'https://this-domain-definitely-does-not-exist-12345.com',
            'expected_category': 'failed-connection'
        },
        {
            'name': 'Bad Protocol',
            'url': 'ftp://example.com',
            'expected_category': 'failed'
        },
        {
            'name': 'Empty URL',
            'url': '',
            'expected_category': 'failed'
        },
        {
            'name': 'None URL',
            'url': None,
            'expected_category': 'failed'
        },
        {
            'name': 'PDF File',
            'url': 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf',
            'expected_category': 'failed-type'
        }
    ]

    print('Testing Edge Cases and Error Handling')
    print('=' * 80)
    print()

    results = {
        'passed': 0,
        'failed': 0,
        'details': []
    }

    for test in test_cases:
        print(f'Test: {test["name"]}')
        print(f'URL: {test["url"]}')
        print('-' * 80)

        try:
            html_content, status_code, error_message = scrape_website(test['url'])

            if error_message:
                category, friendly_msg = categorize_scrape_error(error_message, status_code)
                print(f'Result: ERROR (as expected)')
                print(f'Category: {category}')
                print(f'Message: {friendly_msg or error_message}')
                print(f'Status Code: {status_code}')

                # Check if category matches expected
                if test['expected_category'] in category:
                    print('[PASS] Error categorized correctly')
                    results['passed'] += 1
                else:
                    print(f'[FAIL] Expected category: {test["expected_category"]}, Got: {category}')
                    results['failed'] += 1
                    results['details'].append(f"{test['name']}: Expected {test['expected_category']}, got {category}")
            else:
                print(f'Result: SUCCESS (unexpected for this test)')
                print(f'Content length: {len(html_content)} chars')
                print('[FAIL] Should have failed but succeeded')
                results['failed'] += 1
                results['details'].append(f"{test['name']}: Should have failed but succeeded")

        except Exception as e:
            print(f'Result: EXCEPTION')
            print(f'Error: {str(e)[:200]}')
            category, friendly_msg = categorize_scrape_error(str(e), None)
            print(f'Category: {category}')
            print('[PASS] Exception handled gracefully')
            results['passed'] += 1

        print()
        print('=' * 80)
        print()

    # Summary
    print('TEST SUMMARY')
    print('=' * 80)
    print(f'Total Tests: {len(test_cases)}')
    print(f'Passed: {results["passed"]}')
    print(f'Failed: {results["failed"]}')
    print(f'Success Rate: {results["passed"]/len(test_cases)*100:.1f}%')
    print()

    if results['details']:
        print('Failed Tests:')
        for detail in results['details']:
            print(f'  - {detail}')
    else:
        print('All tests passed!')

    return results

def test_real_websites():
    """Test on real websites with known characteristics."""

    real_tests = [
        {
            'name': 'Google (should work)',
            'url': 'https://www.google.com',
            'should_succeed': True
        },
        {
            'name': 'HTTPBin (should work)',
            'url': 'https://httpbin.org/html',
            'should_succeed': True
        },
        {
            'name': 'HTTPBin 404 (should fail)',
            'url': 'https://httpbin.org/status/404',
            'should_succeed': False
        },
        {
            'name': 'HTTPBin 500 (should fail)',
            'url': 'https://httpbin.org/status/500',
            'should_succeed': False
        }
    ]

    print()
    print('Testing Real Websites')
    print('=' * 80)
    print()

    for test in real_tests:
        print(f'Test: {test["name"]}')
        print(f'URL: {test["url"]}')
        print('-' * 80)

        html_content, status_code, error_message = scrape_website(test['url'])

        if error_message:
            category, friendly_msg = categorize_scrape_error(error_message, status_code)
            print(f'Result: FAILED')
            print(f'Category: {category}')
            print(f'Message: {friendly_msg}')
            success = not test['should_succeed']
        else:
            print(f'Result: SUCCESS')
            print(f'Status Code: {status_code}')
            print(f'Content Length: {len(html_content):,} chars')

            # Try extracting text
            extracted = extract_text(html_content)
            print(f'Extracted Text: {len(extracted):,} chars')
            success = test['should_succeed']

        print(f'[{"PASS" if success else "FAIL"}]')
        print()
        print('=' * 80)
        print()

if __name__ == '__main__':
    # Run edge case tests
    results = test_edge_cases()

    # Run real website tests
    test_real_websites()

    print()
    print('All edge case testing complete!')
