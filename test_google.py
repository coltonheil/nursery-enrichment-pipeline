import os
from dotenv import load_dotenv
import requests

load_dotenv()

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    print("❌ GOOGLE_API_KEY not found in .env")
    exit(1)

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
    print("✅ Google Places API is working!")
    print(f"   Found: {response.json()['places'][0]['displayName']['text']}")
else:
    print(f"❌ Google Places API error: {response.status_code}")
    print(response.text)
