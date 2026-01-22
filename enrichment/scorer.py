"""
Scoring Engine for Nursery Enrichment Pipeline

Scores leads based on positive and negative signals to identify
the best wholesale prospects for potting soil.
"""

import json
from datetime import datetime

# Scoring Rules (from strategy doc)
SCORING_RULES = {
    'positive': {
        'is_wholesale': {
            'points': 35,
            'description': 'Sells to wholesale/trade customers'
        },
        'cannabis_business': {
            'points': 30,
            'description': 'Cannabis cultivation business'
        },
        'closed_weekends': {
            'points': 25,
            'description': 'Closed both Saturday and Sunday'
        },
        'large_greenhouse': {
            'points': 25,
            'description': 'Greenhouse > 5,000 sq ft'
        },
        'container_production': {
            'points': 25,
            'description': 'Container/pot production'
        },
        'acreage_mentioned': {
            'points': 20,
            'description': 'Acreage mentioned (significant size)'
        },
        'appointment_only': {
            'points': 20,
            'description': 'Appointment only (not retail-focused)'
        },
        'multiple_locations': {
            'points': 20,
            'description': 'Multiple physical locations'
        },
        'soil_relevance': {
            'points': 15,
            'description': 'Uses potting soil/growing media'
        },
        'closed_saturday': {
            'points': 10,
            'description': 'Closed on Saturday'
        },
        'closed_sunday': {
            'points': 10,
            'description': 'Closed on Sunday'
        },
        'state_wi': {
            'points': 10,
            'description': 'Located in Wisconsin'
        },
        'no_hours_listed': {
            'points': 5,
            'description': 'No hours listed (wholesale indicator)'
        }
    },
    'negative': {
        'christmas_tree': {
            'points': -30,
            'description': 'Christmas tree farm'
        },
        'sod_turf': {
            'points': -30,
            'description': 'Sod/turf grass production'
        },
        'bare_root': {
            'points': -20,
            'description': 'Bare root production'
        },
        'ball_and_burlap': {
            'points': -20,
            'description': 'Ball and burlap (B&B) trees'
        },
        'landscaping_services': {
            'points': -20,
            'description': 'Landscaping installation services'
        },
        'gift_shop': {
            'points': -15,
            'description': 'Gift shop/home decor focus'
        },
        'workshops_classes': {
            'points': -15,
            'description': 'Workshops, classes, or events'
        },
        'high_reviews': {
            'points': -10,
            'description': 'High review count (> 100)'
        },
        'orchard_upick': {
            'points': -10,
            'description': 'U-pick orchard/fruit farm'
        },
        'tree_farm_field': {
            'points': -10,
            'description': 'Field-grown tree farm'
        }
    }
}

def parse_hours(hours_json):
    """
    Parse Google Places hours JSON to determine if closed on weekends.

    Args:
        hours_json: JSON string or dict with weekday schedule

    Returns:
        dict with keys: closed_saturday, closed_sunday, closed_weekends, no_hours_listed
    """
    result = {
        'closed_saturday': False,
        'closed_sunday': False,
        'closed_weekends': False,
        'no_hours_listed': False
    }

    if not hours_json:
        result['no_hours_listed'] = True
        return result

    try:
        if isinstance(hours_json, str):
            hours = json.loads(hours_json)
        else:
            hours = hours_json

        # Check if hours is a dict with weekday keys
        if isinstance(hours, dict):
            # Look for Saturday (6) and Sunday (0)
            closed_saturday = not hours.get('6') or hours.get('6') == 'Closed'
            closed_sunday = not hours.get('0') or hours.get('0') == 'Closed'

            result['closed_saturday'] = closed_saturday
            result['closed_sunday'] = closed_sunday
            result['closed_weekends'] = closed_saturday and closed_sunday

    except (json.JSONDecodeError, AttributeError, TypeError):
        result['no_hours_listed'] = True

    return result

def calculate_score(lead):
    """
    Calculate score for a lead based on all signals.

    Args:
        lead: Database row (sqlite3.Row) with all lead data

    Returns:
        dict with keys:
            - total: Total score (integer)
            - signals: List of signal dicts (signal, points, value, description)
            - tier: Assigned tier (A/B/C/U)
            - has_data: Whether lead has sufficient data for scoring
    """
    signals = []
    total_score = 0

    # Helper to safely get lead values
    def get_value(key, default=None):
        if hasattr(lead, 'get'):
            return lead.get(key, default)
        else:
            return lead[key] if lead[key] is not None else default

    # Check if lead has sufficient data (needs website OR Google enrichment OR Gemini enrichment)
    gemini_status = get_value('gemini_status')
    has_website = get_value('website')
    google_enrichment = get_value('enrichment_status')

    # Lead has data if it has a website OR has been enriched (Google or Gemini)
    has_data = bool(has_website) or gemini_status == 'enriched' or google_enrichment == 'enriched'

    if not has_data:
        # Insufficient data - assign Tier U (no website, no enrichment at all)
        return {
            'total': 0,
            'signals': [],
            'tier': 'U',
            'has_data': False,
            'reason': 'No website or enrichment data available'
        }

    # Parse negative indicators JSON
    negative_indicators = {}
    neg_json = get_value('negative_indicators')
    if neg_json:
        try:
            negative_indicators = json.loads(neg_json) if isinstance(neg_json, str) else neg_json
        except (json.JSONDecodeError, TypeError):
            negative_indicators = {}

    # Parse hours
    hours_info = parse_hours(get_value('hours'))

    # === POSITIVE SIGNALS ===

    # is_wholesale
    if get_value('is_wholesale'):
        signals.append({
            'signal': 'is_wholesale',
            'points': SCORING_RULES['positive']['is_wholesale']['points'],
            'value': True,
            'description': SCORING_RULES['positive']['is_wholesale']['description']
        })
        total_score += SCORING_RULES['positive']['is_wholesale']['points']

    # cannabis_business
    business_type = get_value('business_type', '')
    if 'cannabis' in business_type.lower():
        signals.append({
            'signal': 'cannabis_business',
            'points': SCORING_RULES['positive']['cannabis_business']['points'],
            'value': True,
            'description': SCORING_RULES['positive']['cannabis_business']['description']
        })
        total_score += SCORING_RULES['positive']['cannabis_business']['points']

    # closed_weekends (both Saturday AND Sunday)
    if hours_info['closed_weekends']:
        signals.append({
            'signal': 'closed_weekends',
            'points': SCORING_RULES['positive']['closed_weekends']['points'],
            'value': True,
            'description': SCORING_RULES['positive']['closed_weekends']['description']
        })
        total_score += SCORING_RULES['positive']['closed_weekends']['points']
    elif hours_info['closed_saturday']:
        # Partial credit for Saturday only
        signals.append({
            'signal': 'closed_saturday',
            'points': SCORING_RULES['positive']['closed_saturday']['points'],
            'value': True,
            'description': SCORING_RULES['positive']['closed_saturday']['description']
        })
        total_score += SCORING_RULES['positive']['closed_saturday']['points']
    elif hours_info['closed_sunday']:
        # Partial credit for Sunday only
        signals.append({
            'signal': 'closed_sunday',
            'points': SCORING_RULES['positive']['closed_sunday']['points'],
            'value': True,
            'description': SCORING_RULES['positive']['closed_sunday']['description']
        })
        total_score += SCORING_RULES['positive']['closed_sunday']['points']

    # large_greenhouse (> 5000 sq ft)
    greenhouse_sqft = get_value('greenhouse_sqft', 0)
    if greenhouse_sqft and greenhouse_sqft > 5000:
        signals.append({
            'signal': 'large_greenhouse',
            'points': SCORING_RULES['positive']['large_greenhouse']['points'],
            'value': greenhouse_sqft,
            'description': SCORING_RULES['positive']['large_greenhouse']['description']
        })
        total_score += SCORING_RULES['positive']['large_greenhouse']['points']

    # container_production
    if get_value('container_production'):
        signals.append({
            'signal': 'container_production',
            'points': SCORING_RULES['positive']['container_production']['points'],
            'value': True,
            'description': SCORING_RULES['positive']['container_production']['description']
        })
        total_score += SCORING_RULES['positive']['container_production']['points']

    # acreage_mentioned
    acreage = get_value('acreage', 0)
    if acreage and acreage > 0:
        signals.append({
            'signal': 'acreage_mentioned',
            'points': SCORING_RULES['positive']['acreage_mentioned']['points'],
            'value': acreage,
            'description': SCORING_RULES['positive']['acreage_mentioned']['description']
        })
        total_score += SCORING_RULES['positive']['acreage_mentioned']['points']

    # appointment_only
    if get_value('appointment_only'):
        signals.append({
            'signal': 'appointment_only',
            'points': SCORING_RULES['positive']['appointment_only']['points'],
            'value': True,
            'description': SCORING_RULES['positive']['appointment_only']['description']
        })
        total_score += SCORING_RULES['positive']['appointment_only']['points']

    # multiple_locations
    if get_value('multiple_locations'):
        signals.append({
            'signal': 'multiple_locations',
            'points': SCORING_RULES['positive']['multiple_locations']['points'],
            'value': True,
            'description': SCORING_RULES['positive']['multiple_locations']['description']
        })
        total_score += SCORING_RULES['positive']['multiple_locations']['points']

    # soil_relevance
    if get_value('soil_relevance'):
        signals.append({
            'signal': 'soil_relevance',
            'points': SCORING_RULES['positive']['soil_relevance']['points'],
            'value': True,
            'description': SCORING_RULES['positive']['soil_relevance']['description']
        })
        total_score += SCORING_RULES['positive']['soil_relevance']['points']

    # state_wi
    state = get_value('state', '')
    if state and state.upper() == 'WI':
        signals.append({
            'signal': 'state_wi',
            'points': SCORING_RULES['positive']['state_wi']['points'],
            'value': True,
            'description': SCORING_RULES['positive']['state_wi']['description']
        })
        total_score += SCORING_RULES['positive']['state_wi']['points']

    # no_hours_listed
    if hours_info['no_hours_listed']:
        signals.append({
            'signal': 'no_hours_listed',
            'points': SCORING_RULES['positive']['no_hours_listed']['points'],
            'value': True,
            'description': SCORING_RULES['positive']['no_hours_listed']['description']
        })
        total_score += SCORING_RULES['positive']['no_hours_listed']['points']

    # === NEGATIVE SIGNALS ===

    # christmas_tree
    if negative_indicators.get('christmas_tree'):
        signals.append({
            'signal': 'christmas_tree',
            'points': SCORING_RULES['negative']['christmas_tree']['points'],
            'value': True,
            'description': SCORING_RULES['negative']['christmas_tree']['description']
        })
        total_score += SCORING_RULES['negative']['christmas_tree']['points']

    # sod_turf
    if negative_indicators.get('sod_turf'):
        signals.append({
            'signal': 'sod_turf',
            'points': SCORING_RULES['negative']['sod_turf']['points'],
            'value': True,
            'description': SCORING_RULES['negative']['sod_turf']['description']
        })
        total_score += SCORING_RULES['negative']['sod_turf']['points']

    # bare_root
    if negative_indicators.get('bare_root'):
        signals.append({
            'signal': 'bare_root',
            'points': SCORING_RULES['negative']['bare_root']['points'],
            'value': True,
            'description': SCORING_RULES['negative']['bare_root']['description']
        })
        total_score += SCORING_RULES['negative']['bare_root']['points']

    # ball_and_burlap
    if negative_indicators.get('ball_and_burlap'):
        signals.append({
            'signal': 'ball_and_burlap',
            'points': SCORING_RULES['negative']['ball_and_burlap']['points'],
            'value': True,
            'description': SCORING_RULES['negative']['ball_and_burlap']['description']
        })
        total_score += SCORING_RULES['negative']['ball_and_burlap']['points']

    # landscaping_services
    if negative_indicators.get('landscaping_services'):
        signals.append({
            'signal': 'landscaping_services',
            'points': SCORING_RULES['negative']['landscaping_services']['points'],
            'value': True,
            'description': SCORING_RULES['negative']['landscaping_services']['description']
        })
        total_score += SCORING_RULES['negative']['landscaping_services']['points']

    # gift_shop
    if negative_indicators.get('gift_shop'):
        signals.append({
            'signal': 'gift_shop',
            'points': SCORING_RULES['negative']['gift_shop']['points'],
            'value': True,
            'description': SCORING_RULES['negative']['gift_shop']['description']
        })
        total_score += SCORING_RULES['negative']['gift_shop']['points']

    # workshops_classes
    if negative_indicators.get('workshops_classes'):
        signals.append({
            'signal': 'workshops_classes',
            'points': SCORING_RULES['negative']['workshops_classes']['points'],
            'value': True,
            'description': SCORING_RULES['negative']['workshops_classes']['description']
        })
        total_score += SCORING_RULES['negative']['workshops_classes']['points']

    # high_reviews (> 100)
    review_count = get_value('review_count', 0)
    if review_count and review_count > 100:
        signals.append({
            'signal': 'high_reviews',
            'points': SCORING_RULES['negative']['high_reviews']['points'],
            'value': review_count,
            'description': SCORING_RULES['negative']['high_reviews']['description']
        })
        total_score += SCORING_RULES['negative']['high_reviews']['points']

    # orchard_upick
    if negative_indicators.get('orchard_upick'):
        signals.append({
            'signal': 'orchard_upick',
            'points': SCORING_RULES['negative']['orchard_upick']['points'],
            'value': True,
            'description': SCORING_RULES['negative']['orchard_upick']['description']
        })
        total_score += SCORING_RULES['negative']['orchard_upick']['points']

    # tree_farm_field
    if negative_indicators.get('tree_farm_field'):
        signals.append({
            'signal': 'tree_farm_field',
            'points': SCORING_RULES['negative']['tree_farm_field']['points'],
            'value': True,
            'description': SCORING_RULES['negative']['tree_farm_field']['description']
        })
        total_score += SCORING_RULES['negative']['tree_farm_field']['points']

    # Assign tier based on total score
    tier = assign_tier(total_score, has_data)

    return {
        'total': total_score,
        'signals': signals,
        'tier': tier,
        'has_data': has_data
    }

def assign_tier(score, has_data):
    """
    Assign tier based on score.

    Args:
        score: Total score (integer)
        has_data: Whether lead has sufficient data

    Returns:
        str: Tier (A/B/C/U)
    """
    if not has_data:
        return 'U'

    if score >= 60:
        return 'A'
    elif score >= 30:
        return 'B'
    else:
        return 'C'

def test_scorer():
    """Test the scoring function with sample data."""

    print("Testing Scoring Engine")
    print("=" * 80)
    print()

    # Test case 1: High-scoring wholesale nursery
    test_lead_1 = {
        'gemini_status': 'enriched',
        'website': 'http://example.com',
        'is_wholesale': True,
        'business_type': 'wholesale_nursery',
        'container_production': True,
        'soil_relevance': True,
        'acreage': 45,
        'greenhouse_sqft': 10000,
        'appointment_only': True,
        'multiple_locations': False,
        'state': 'WI',
        'hours': None,  # No hours listed
        'review_count': 15,
        'negative_indicators': json.dumps({
            'christmas_tree': False,
            'sod_turf': False,
            'gift_shop': False,
            'workshops_classes': False,
            'landscaping_services': False,
            'orchard_upick': False,
            'bare_root': False,
            'ball_and_burlap': False,
            'tree_farm_field': False
        })
    }

    result_1 = calculate_score(test_lead_1)
    print("Test 1: Wholesale Nursery (Expected: Tier A)")
    print(f"Score: {result_1['total']}")
    print(f"Tier: {result_1['tier']}")
    print(f"Signals triggered: {len(result_1['signals'])}")
    for signal in result_1['signals']:
        print(f"  {signal['signal']}: {signal['points']} points - {signal['description']}")
    print()

    # Test case 2: Retail garden center with negatives
    test_lead_2 = {
        'gemini_status': 'enriched',
        'website': 'http://example.com',
        'is_wholesale': False,
        'business_type': 'garden_center',
        'container_production': True,
        'soil_relevance': True,
        'acreage': None,
        'greenhouse_sqft': None,
        'appointment_only': False,
        'multiple_locations': False,
        'state': 'WI',
        'hours': json.dumps({'0': 'Closed', '6': 'Closed'}),  # Closed weekends
        'review_count': 150,
        'negative_indicators': json.dumps({
            'christmas_tree': False,
            'sod_turf': False,
            'gift_shop': True,
            'workshops_classes': True,
            'landscaping_services': False,
            'orchard_upick': False,
            'bare_root': False,
            'ball_and_burlap': False,
            'tree_farm_field': False
        })
    }

    result_2 = calculate_score(test_lead_2)
    print("Test 2: Retail Garden Center (Expected: Tier B or C)")
    print(f"Score: {result_2['total']}")
    print(f"Tier: {result_2['tier']}")
    print(f"Signals triggered: {len(result_2['signals'])}")
    for signal in result_2['signals']:
        print(f"  {signal['signal']}: {signal['points']} points - {signal['description']}")
    print()

    # Test case 3: No data
    test_lead_3 = {
        'gemini_status': 'pending',
        'website': None
    }

    result_3 = calculate_score(test_lead_3)
    print("Test 3: No Data (Expected: Tier U)")
    print(f"Score: {result_3['total']}")
    print(f"Tier: {result_3['tier']}")
    print(f"Reason: {result_3.get('reason', 'N/A')}")
    print()

    print("Scoring engine tests complete!")

if __name__ == '__main__':
    test_scorer()
