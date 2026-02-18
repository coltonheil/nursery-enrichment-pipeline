import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('BRAVE_API_KEY')
print(f"API Key: {api_key[:10]}...")

query = '"BOS WILLIAM GREENHOUSE" "William Bos" email'
print(f"Query: {query}")
print()

url = "https://api.search.brave.com/res/v1/web/search"
headers = {
    "Accept": "application/json",
    "X-Subscription-Token": api_key
}
params = {
    "q": query,
    "count": 2
}

response = requests.get(url, headers=headers, params=params, timeout=10)
print(f"Status: {response.status_code}")

data = response.json()
results = data.get('web', {}).get('results', [])
print(f"Results count: {len(results)}")
print()

for idx, result in enumerate(results, 1):
    print(f"Result {idx}:")
    print(f"  Title: {result.get('title', 'N/A')}")
    print(f"  URL: {result.get('url', 'N/A')}")
    print(f"  Description: {result.get('description', 'N/A')[:200]}")
    print()
