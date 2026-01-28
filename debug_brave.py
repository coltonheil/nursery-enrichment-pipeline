import os
import sys
from dotenv import load_dotenv

# Load from script's directory
load_dotenv()

api_key = os.getenv('BRAVE_API_KEY')
print(f"API Key loaded: {api_key is not None}")
if api_key:
    print(f"API Key starts with: {api_key[:10]}...")

# Try the function from email_search_enrichment
sys.path.insert(0, '.')
from email_search_enrichment import brave_search

try:
    results = brave_search('"BOS WILLIAM GREENHOUSE" "William Bos" email', count=2)
    print(f"Results: {len(results)}")
    for r in results:
        print(f"  - {r.get('title', 'NO TITLE')}")
except Exception as e:
    print(f"Error: {e}")
