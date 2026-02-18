import os
import requests
import time
import json
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
PLACES_API_URL = 'https://places.googleapis.com/v1/places:searchText'
PLACE_DETAILS_URL = 'https://places.googleapis.com/v1/places'

def search_place(business_name, city, state):
    """
    Search for a business using Google Places API (New).
    Returns the place_id if found, None otherwise.
    """
    if not GOOGLE_API_KEY:
        return {'error': 'Google API key not configured'}

    # Build search query
    query = f"{business_name}, {city}"
    if state:
        query += f", {state}"

    headers = {
        'Content-Type': 'application/json',
        'X-Goog-Api-Key': GOOGLE_API_KEY,
        'X-Goog-FieldMask': 'places.id,places.displayName,places.formattedAddress'
    }

    payload = {
        'textQuery': query
    }

    try:
        response = requests.post(PLACES_API_URL, headers=headers, json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if 'places' in data and len(data['places']) > 0:
                # Return the first result
                place = data['places'][0]
                return {
                    'place_id': place.get('id'),
                    'name': place.get('displayName', {}).get('text'),
                    'address': place.get('formattedAddress')
                }
            else:
                return {'error': 'No places found'}
        elif response.status_code == 429:
            return {'error': 'Rate limit exceeded', 'retry_after': 60}
        else:
            return {'error': f'API error: {response.status_code} - {response.text}'}

    except requests.exceptions.Timeout:
        return {'error': 'Request timeout'}
    except Exception as e:
        return {'error': f'Exception: {str(e)}'}

def get_place_details(place_id):
    """
    Get detailed information about a place.
    Returns a dictionary with phone, website, rating, etc.

    Note: Google Places API (New) does not expose email addresses directly.
    The 'places_email' field is populated via website scraping / regex extraction
    by the email hunter, not from the Places API response.
    """
    if not GOOGLE_API_KEY:
        return {'error': 'Google API key not configured'}

    headers = {
        'X-Goog-Api-Key': GOOGLE_API_KEY,
        # No 'email' field in Places API — kept for awareness
        'X-Goog-FieldMask': 'displayName,formattedAddress,internationalPhoneNumber,websiteUri,rating,userRatingCount,regularOpeningHours,googleMapsUri'
    }

    try:
        # Ensure place_id has 'places/' prefix
        place_resource = place_id if place_id.startswith('places/') else f'places/{place_id}'

        # Use correct API format: https://places.googleapis.com/v1/{place_id}
        url = f'https://places.googleapis.com/v1/{place_resource}'

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()

            # Extract hours if available
            hours = None
            if 'regularOpeningHours' in data:
                opening_hours = data['regularOpeningHours']
                if 'weekdayDescriptions' in opening_hours:
                    hours = json.dumps(opening_hours['weekdayDescriptions'])

            # Google Places API does not return email fields.
            # We set places_email=None here; the email hunter will
            # attempt to extract it from website text and contact pages.
            return {
                'phone': data.get('nationalPhoneNumber') or data.get('internationalPhoneNumber'),
                'website': data.get('websiteUri'),
                'rating': data.get('rating'),
                'review_count': data.get('userRatingCount'),
                'hours': hours,
                'google_maps_url': data.get('googleMapsUri'),
                'place_id': place_id,
                'places_email': None,  # Reserved for future API versions that expose email
            }
        elif response.status_code == 429:
            return {'error': 'Rate limit exceeded', 'retry_after': 60}
        else:
            return {'error': f'API error: {response.status_code} - {response.text}'}

    except requests.exceptions.Timeout:
        return {'error': 'Request timeout'}
    except Exception as e:
        return {'error': f'Exception: {str(e)}'}

def enrich_business(business_name, city, state):
    """
    Complete enrichment flow: search for business and get details.
    Returns enriched data dictionary or error.
    """
    # Step 1: Search for the place
    search_result = search_place(business_name, city, state)

    if 'error' in search_result:
        return search_result

    if 'place_id' not in search_result:
        return {'error': 'Place ID not found in search results'}

    place_id = search_result['place_id']

    # Add small delay to avoid rate limiting
    time.sleep(0.5)

    # Step 2: Get place details
    details = get_place_details(place_id)

    if 'error' in details:
        return details

    return details

def test_api_connection():
    """Test if the Google Places API is properly configured."""
    if not GOOGLE_API_KEY:
        return {'status': 'error', 'message': 'GOOGLE_API_KEY not found in environment'}

    # Try a simple search
    result = search_place('Google', 'Mountain View', 'CA')

    if 'error' in result:
        return {'status': 'error', 'message': result['error']}

    return {'status': 'success', 'message': 'Google Places API is working'}
