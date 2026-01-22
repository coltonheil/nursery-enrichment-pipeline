import os
from dotenv import load_dotenv
import requests

# Debug: show current directory and .env file existence
print(f"Current directory: {os.getcwd()}")
print(f".env file exists: {os.path.exists('.env')}")

# Load environment variables
loaded = load_dotenv()
print(f"load_dotenv() returned: {loaded}")

api_key = os.getenv("GOOGLE_API_KEY")
print(f"API key found: {api_key is not None}")
print(f"API key value: {api_key[:20] if api_key else 'None'}...")

if not api_key:
    print("[ERROR] GOOGLE_API_KEY not found in .env")
    exit(1)

print("\nTesting Google Places API...")
response = requests.post(
    "https://places.googleapis.com/v1/places:searchText",
    headers={
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName"
    },
    json={"textQuery": "nursery Madison WI"}
)

if response.status_code == 200:
    print("[SUCCESS] Google Places API is working!")
    print(f"   Found: {response.json()['places'][0]['displayName']['text']}")
else:
    print(f"[ERROR] Google Places API error: {response.status_code}")
    print(response.text)
