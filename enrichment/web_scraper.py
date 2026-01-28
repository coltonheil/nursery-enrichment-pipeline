import requests
import random
import time
from urllib.parse import urljoin, urlparse
import warnings
from bs4 import BeautifulSoup
import re

# Suppress SSL warnings
warnings.filterwarnings('ignore', message='Unverified HTTPS request')

# List of 10 rotating user agents (modern browsers)
USER_AGENTS = [
    # Chrome on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',

    # Chrome on Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',

    # Firefox on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',

    # Firefox on Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',

    # Safari on Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15',

    # Edge on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0'
]

# Maximum response size (5MB)
MAX_CONTENT_SIZE = 5 * 1024 * 1024

def get_random_user_agent():
    """Return a random user agent from the list."""
    return random.choice(USER_AGENTS)

def add_random_delay():
    """Add a random delay between requests to avoid bot detection."""
    # Reduced from 2-5s to 0.3-0.7s for faster batch processing
    # Nursery sites are low-traffic and unlikely to rate-limit
    delay = random.uniform(0.3, 0.7)
    time.sleep(delay)
    return delay

def normalize_url(url):
    """Ensure URL has a scheme (http/https)."""
    if not url:
        return None

    url = url.strip()

    # Add scheme if missing
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    return url

def scrape_website(url, retry_count=0):
    """
    Scrape a website with bot-avoidance measures.

    Args:
        url: The URL to scrape
        retry_count: Internal counter for retry attempts

    Returns:
        tuple: (html_content, status_code, error_message)
            - html_content: HTML string or None if failed
            - status_code: HTTP status code or None if request failed
            - error_message: Error description or None if successful
    """
    # Normalize URL
    url = normalize_url(url)
    if not url:
        return (None, None, 'Invalid URL: empty or None')

    # Validate URL format
    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return (None, None, f'Invalid URL format: {url}')
    except Exception as e:
        return (None, None, f'URL parsing error: {str(e)}')

    # Add random delay (skip on retries to avoid excessive delays)
    if retry_count == 0:
        delay = add_random_delay()

    # Pick random user agent
    user_agent = get_random_user_agent()

    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=15,
            verify=False,  # Disable SSL verification for sites with bad certs
            allow_redirects=True,
            stream=True  # Stream to check content size
        )

        # Check content size before loading
        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > MAX_CONTENT_SIZE:
            return (None, response.status_code, f'Content too large: {content_length} bytes (max {MAX_CONTENT_SIZE})')

        # Check content type
        content_type = response.headers.get('Content-Type', '').lower()
        if not any(t in content_type for t in ['text/html', 'text/plain', 'application/xhtml']):
            return (None, response.status_code, f'Non-HTML content type: {content_type}')

        # Load content with size limit
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > MAX_CONTENT_SIZE:
                return (None, response.status_code, f'Content exceeded size limit while downloading')

        html_content = content.decode('utf-8', errors='ignore')

        # Check HTTP status codes
        if response.status_code == 404:
            return (None, 404, 'Page not found (404)')
        elif response.status_code == 403:
            return (None, 403, 'Access forbidden (403)')
        elif response.status_code == 401:
            return (None, 401, 'Authentication required (401)')
        elif response.status_code >= 500:
            return (None, response.status_code, f'Server error ({response.status_code})')
        elif response.status_code != 200:
            return (None, response.status_code, f'HTTP error {response.status_code}')

        # Check if content is suspiciously small (might be blocked)
        if len(html_content) < 100:
            return (None, response.status_code, 'Content too small (possible block or empty page)')

        return (html_content, response.status_code, None)

    except requests.exceptions.SSLError as e:
        # If SSL error and this is first attempt, retry once with different approach
        if retry_count == 0:
            return scrape_website(url.replace('https://', 'http://'), retry_count=1)
        return (None, None, f'SSL error: {str(e)[:100]}')

    except requests.exceptions.TooManyRedirects:
        return (None, None, 'Too many redirects (>3)')

    except requests.exceptions.Timeout:
        # Retry once on timeout
        if retry_count == 0:
            time.sleep(2)
            return scrape_website(url, retry_count=1)
        return (None, None, 'Connection timeout (15s)')

    except requests.exceptions.ConnectionError as e:
        # Retry once on connection error
        if retry_count == 0:
            time.sleep(2)
            return scrape_website(url, retry_count=1)
        return (None, None, f'Connection error: {str(e)[:100]}')

    except requests.exceptions.RequestException as e:
        return (None, None, f'Request error: {str(e)[:100]}')

    except Exception as e:
        return (None, None, f'Unexpected error: {str(e)[:100]}')

def test_scraper(url):
    """Test the scraper on a single URL and print results."""
    print(f"\nTesting scraper on: {url}")
    print("=" * 60)

    start_time = time.time()
    html_content, status_code, error_message = scrape_website(url)
    elapsed_time = time.time() - start_time

    print(f"Time taken: {elapsed_time:.2f}s")

    if error_message:
        print(f"[ERROR] {error_message}")
        if status_code:
            print(f"   Status code: {status_code}")
    else:
        print(f"[SUCCESS]")
        print(f"   Status code: {status_code}")
        print(f"   Content length: {len(html_content):,} characters")
        print(f"   First 200 chars: {html_content[:200]}")

    return (html_content, status_code, error_message)

def extract_text(html):
    """
    Extract clean text from HTML content.

    Args:
        html: Raw HTML string

    Returns:
        str: Cleaned text content (max 15,000 characters)
    """
    if not html:
        return ""

    try:
        # Parse HTML
        soup = BeautifulSoup(html, 'lxml')

        # Remove unwanted tags
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside',
                        'iframe', 'noscript', 'form', 'button', 'input']):
            tag.decompose()

        # Extract text from useful tags
        text_parts = []

        # Get meta description (often has good summary)
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            text_parts.append(meta_desc['content'])

        # Get title
        if soup.title and soup.title.string:
            text_parts.append(soup.title.string)

        # Extract text from main content tags
        content_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li',
                       'article', 'main', 'section', 'div']

        for tag_name in content_tags:
            for tag in soup.find_all(tag_name):
                text = tag.get_text(strip=True)
                if text and len(text) > 20:  # Only keep substantial text
                    text_parts.append(text)

        # Combine all text
        full_text = ' '.join(text_parts)

        # Clean whitespace
        full_text = re.sub(r'\s+', ' ', full_text)  # Collapse multiple spaces
        full_text = full_text.strip()

        # Limit to 15,000 characters
        if len(full_text) > 15000:
            full_text = full_text[:15000]

        return full_text

    except Exception as e:
        print(f"[WARNING] Text extraction error: {str(e)[:100]}")
        return ""

def categorize_scrape_error(error_message, status_code):
    """
    Categorize scrape errors into specific types for better handling.

    Returns: (category, user_friendly_message)
    Categories: 'failed-404', 'failed-403', 'failed-500', 'failed-timeout',
                'failed-ssl', 'failed-empty', 'failed-js', 'failed-redirect',
                'failed-size', 'failed-type', 'failed-connection', 'failed'
    """
    if not error_message:
        return ('scraped', None)

    error_lower = error_message.lower()

    # HTTP errors
    if '404' in error_lower or 'not found' in error_lower:
        return ('failed-404', 'Page not found (404)')
    if '403' in error_lower or 'forbidden' in error_lower:
        return ('failed-403', 'Access forbidden (403)')
    if '401' in error_lower or 'authentication' in error_lower:
        return ('failed-401', 'Authentication required (401)')
    if status_code and status_code >= 500:
        return ('failed-500', f'Server error ({status_code})')

    # Connection errors
    if 'timeout' in error_lower:
        return ('failed-timeout', 'Connection timeout')
    if 'connection' in error_lower:
        return ('failed-connection', 'Connection failed')
    if 'ssl' in error_lower or 'certificate' in error_lower:
        return ('failed-ssl', 'SSL certificate error')

    # Content errors
    if 'too small' in error_lower or 'empty' in error_lower:
        return ('failed-empty', 'No content found (empty page)')
    if 'js-only' in error_lower or 'javascript' in error_lower:
        return ('failed-js', 'JavaScript-only site (no static content)')
    if 'redirect' in error_lower:
        return ('failed-redirect', 'Too many redirects')
    if 'too large' in error_lower or 'size limit' in error_lower:
        return ('failed-size', 'Content too large')
    if 'non-html' in error_lower or 'content type' in error_lower:
        return ('failed-type', 'Non-HTML content (PDF, image, etc.)')

    # Generic failure
    return ('failed', error_message)

def scrape_and_extract(url):
    """
    Scrape homepage and common pages (/about, /contact) and extract text.

    Args:
        url: The base URL to scrape

    Returns:
        tuple: (extracted_text, status_info)
            - extracted_text: Combined cleaned text from all pages
            - status_info: Dict with scraping details
    """
    if not url:
        return ("", {"error": "No URL provided"})

    # Normalize base URL
    url = normalize_url(url)
    parsed_base = urlparse(url)
    base_domain = f"{parsed_base.scheme}://{parsed_base.netloc}"

    # Pages to try - prioritized for finding staff/contact information
    # Reordered to prioritize team pages earlier (before hitting 5-page limit)
    pages_to_scrape = [
        (url, "homepage"),
        # Team/Staff pages FIRST - most valuable for finding contacts
        (urljoin(base_domain, '/team'), "team"),
        (urljoin(base_domain, '/our-team'), "our-team"),
        (urljoin(base_domain, '/staff'), "staff"),
        (urljoin(base_domain, '/meet-the-team'), "meet-team"),
        (urljoin(base_domain, '/people'), "people"),
        # Additional common patterns for nurseries
        (urljoin(base_domain, '/meet-us'), "meet-us"),
        (urljoin(base_domain, '/who-we-are'), "who-we-are"),
        (urljoin(base_domain, '/our-story'), "our-story"),
        # About pages (owner/founder info)
        (urljoin(base_domain, '/about'), "about"),
        (urljoin(base_domain, '/about-us'), "about-us"),
        (urljoin(base_domain, '/aboutus'), "about-us-2"),
        # Contact pages (sometimes have names)
        (urljoin(base_domain, '/contact'), "contact"),
        (urljoin(base_domain, '/contact-us'), "contact-us"),
        (urljoin(base_domain, '/contactus'), "contact-us-2"),
    ]

    all_text = []
    pages_scraped = 0
    pages_failed = 0
    status_codes = []
    request_count = 0  # Track total requests for rate limiting

    for page_url, page_name in pages_to_scrape:
        # Stop after successfully scraping 5 pages
        if pages_scraped >= 5:
            break
        
        # Stop after too many failures (likely site is blocking us)
        if pages_failed >= 6:
            break

        # Add delay between ALL requests (not just successful ones)
        # This prevents rate limiting even when pages fail
        if request_count > 0:
            time.sleep(random.uniform(0.5, 1.0))  # Consistent delay between requests
        request_count += 1

        # FIX: Use retry_count=0 to enable retries on transient errors
        # The delay is handled above, so we still skip the internal delay
        html_content, status_code, error_message = scrape_website(page_url, retry_count=0)

        if error_message:
            pages_failed += 1
            continue

        if status_code and status_code == 200:
            # Extract text
            text = extract_text(html_content)
            if text and len(text) > 100:  # Only keep pages with substantial content
                all_text.append(f"[{page_name.upper()}] {text}")
                pages_scraped += 1
                status_codes.append(status_code)

    # Combine all text
    combined_text = ' '.join(all_text)

    # Final length check
    if len(combined_text) > 15000:
        combined_text = combined_text[:15000]

    status_info = {
        "pages_scraped": pages_scraped,
        "pages_failed": pages_failed,
        "total_chars": len(combined_text),
        "status_codes": status_codes
    }

    return (combined_text, status_info)
