"""
Scoring Engine for Nursery Enrichment Pipeline - Phase 3 Overhaul

ICP-based scoring system with qualification gate. Scores leads based on:
1. ICP Qualification (must pass to score above Tier C)
2. Sample Requester Insights (real-world buying signals)
3. Negative Signals (disqualifiers)

Based on analysis of 23 companies that requested samples during cold calling.
"""

import json
from datetime import datetime

# ============================================================================
# ICP QUALIFICATION CONSTANTS
# ============================================================================

# A lead MUST have at least one primary or secondary ICP signal to qualify
# Disqualified leads are capped at Tier C regardless of positive signals

ICP_PRIMARY_SIGNALS = {
    # These indicate the business USES growing media in production
    "uses_growing_media": True,
    "production_method": ["container", "greenhouse", "mixed"],
    "container_production": True,
}

ICP_SECONDARY_SIGNALS = {
    # These indicate the business RESELLS growing media
    "business_type": ["soil_mixer", "farm_supply"],
}

DISQUALIFICATION_KEYWORDS = [
    "landscaping", "landscape installation", "lawn care", "mowing",
    "equipment dealer", "machinery", "parts dealer",
    "retail only", "gift shop", "home decor",
    "christmas tree", "sod", "turf",
]

DISQUALIFIED_BUSINESS_TYPES = [
    "landscaper", "equipment_dealer", "retail_only"
]

# ============================================================================
# GEOGRAPHIC SCORING CONSTANTS (Phase 4)
# ============================================================================

# Based on Wisconsin shipping logistics
# 100% of sample requesters were in Wisconsin
GEO_TIERS = {
    # Local - same state (100% of sample requesters)
    "WI": 25,

    # Regional - day-trip freight zone
    "IL": 20,  # Illinois (Chicago metro access)
    "MN": 20,  # Minnesota (Twin Cities)
    "IA": 20,  # Iowa (direct border)
    "MI": 20,  # Michigan (Upper Peninsula proximity)

    # Near - 2-day freight, manageable cost
    "IN": 10,  # Indiana
    "OH": 10,  # Ohio
    "MO": 10,  # Missouri
    "NE": 10,  # Nebraska
    "KY": 10,  # Kentucky

    # Mid - no modifier (viable but neutral)
    "ND": 0, "SD": 0, "KS": 0, "TN": 0,
    "WV": 0, "PA": 0, "NY": 0, "AR": 0,
    "VA": 0, "MT": 0, "WY": 0, "ID": 0,
    "UT": 0, "NV": 0, "OK": 0,

    # Far - higher shipping cost, still viable
    "TX": -5, "CO": -5, "CA": -5, "FL": -5,
    "AZ": -5, "NM": -5, "NC": -5, "SC": -5,
    "GA": -5, "AL": -5, "MS": -5, "LA": -5,
    "OR": -5, "WA": -5, "ME": -5, "NH": -5,
    "VT": -5, "MA": -5, "RI": -5, "CT": -5,
    "NJ": -5, "DE": -5, "MD": -5, "DC": -5,
    "AK": -5, "HI": -5,
}

# Default for unlisted states or territories
GEO_DEFAULT_SCORE = -5

# Full state name to abbreviation mapping
STATE_NAMES_TO_ABBR = {
    "WISCONSIN": "WI", "ILLINOIS": "IL", "MINNESOTA": "MN",
    "IOWA": "IA", "MICHIGAN": "MI", "INDIANA": "IN",
    "OHIO": "OH", "MISSOURI": "MO", "NEBRASKA": "NE",
    "KENTUCKY": "KY", "TEXAS": "TX", "COLORADO": "CO",
    "CALIFORNIA": "CA", "FLORIDA": "FL", "ARIZONA": "AZ",
    "NEW MEXICO": "NM", "NORTH CAROLINA": "NC", "SOUTH CAROLINA": "SC",
    "GEORGIA": "GA", "ALABAMA": "AL", "MISSISSIPPI": "MS",
    "LOUISIANA": "LA", "NORTH DAKOTA": "ND", "SOUTH DAKOTA": "SD",
    "KANSAS": "KS", "TENNESSEE": "TN", "WEST VIRGINIA": "WV",
    "PENNSYLVANIA": "PA", "NEW YORK": "NY", "ARKANSAS": "AR",
    "VIRGINIA": "VA", "MONTANA": "MT", "WYOMING": "WY",
    "IDAHO": "ID", "UTAH": "UT", "NEVADA": "NV", "OKLAHOMA": "OK",
    "OREGON": "OR", "WASHINGTON": "WA", "MAINE": "ME",
    "NEW HAMPSHIRE": "NH", "VERMONT": "VT", "MASSACHUSETTS": "MA",
    "RHODE ISLAND": "RI", "CONNECTICUT": "CT", "NEW JERSEY": "NJ",
    "DELAWARE": "DE", "MARYLAND": "MD", "ALASKA": "AK", "HAWAII": "HI",
}

# ============================================================================
# SCORING RULES - Based on Sample Requester Analysis
# ============================================================================

SCORING_RULES = {
    # === HIGH-VALUE SIGNALS (from sample requesters) ===

    # Organic signals (26% of sample requesters had "Organic" in name)
    "organic_in_name": {
        "points": 30,
        "description": "Organic in business name (26% of sample requesters)"
    },
    "is_organic_certified": {
        "points": 25,
        "description": "Certified organic operation"
    },
    "organic_focus": {
        "points": 15,
        "description": "Emphasizes organic/sustainable practices"
    },

    # Production method signals
    "greenhouse_production": {
        "points": 25,
        "description": "Greenhouse or container production"
    },
    "uses_growing_media": {
        "points": 20,
        "description": "Uses growing media in production (Core ICP signal)"
    },

    # Business naming signals (from sample requesters)
    "farm_in_name": {
        "points": 15,
        "description": "Farm in business name (43% of sample requesters)"
    },
    "growers_in_name": {
        "points": 15,
        "description": "Grower(s) in business name (17% of sample requesters)"
    },

    # Hemp/Cannabis (9% of sample requesters)
    "hemp_cannabis": {
        "points": 25,
        "description": "Hemp/cannabis operation (9% of sample requesters)"
    },

    # Geographic (100% of sample requesters were in WI)
    "wisconsin_location": {
        "points": 25,
        "description": "Located in Wisconsin (100% of sample requesters)"
    },

    # Wholesale signals
    "is_wholesale": {
        "points": 20,
        "description": "Sells to wholesale/trade customers"
    },

    # Soil purchasing signals (confirms they buy inputs)
    "purchases_soil": {
        "points": 20,
        "description": "Purchases potting soil/amendments"
    },
    "soil_brands_mentioned": {
        "points": 15,
        "description": "Mentions soil brands (Pro-Mix, Sungro, etc.)"
    },

    # Scale signals
    "large_scale": {
        "points": 15,
        "description": "Multiple scale indicators (2+ signals)"
    },
    "acreage_mentioned": {
        "points": 10,
        "description": "Acreage mentioned"
    },
    "large_greenhouse": {
        "points": 10,
        "description": "Greenhouse > 10,000 sq ft"
    },
    "multiple_locations": {
        "points": 10,
        "description": "Multiple physical locations"
    },

    # Business model signals
    "appointment_only": {
        "points": 10,
        "description": "Appointment only (wholesale indicator)"
    },
    "closed_weekends": {
        "points": 10,
        "description": "Closed both Saturday and Sunday"
    },

    # === NEGATIVE SIGNALS (Disqualifiers) ===

    "landscaping_services": {
        "points": -50,
        "description": "Landscaping/lawn care services"
    },
    "christmas_tree": {
        "points": -40,
        "description": "Christmas tree farm"
    },
    "sod_turf": {
        "points": -40,
        "description": "Sod/turf production"
    },
    "gift_shop": {
        "points": -30,
        "description": "Gift shop/home decor focus"
    },
    "retail_only": {
        "points": -20,
        "description": "Retail only, no wholesale or growing operation"
    },
}

# ============================================================================
# ICP QUALIFICATION GATE
# ============================================================================

def check_icp_qualification(lead: dict) -> tuple:
    """
    Check if lead passes ICP qualification gate.

    Returns:
        tuple: (is_qualified: bool, icp_type: str)

    ICP Types:
    - "primary": Uses growing media in production (HIGH priority)
    - "secondary": Resells growing media (MEDIUM priority)
    - "tertiary": Field farm with organic focus (LOWER priority)
    - "disqualified": Has disqualification signals or no ICP fit
    """

    # Helper to safely get lead values
    def get_value(key, default=None):
        if hasattr(lead, 'get'):
            return lead.get(key, default)
        else:
            try:
                return lead[key] if lead[key] is not None else default
            except (KeyError, TypeError):
                return default

    # Check for disqualification FIRST
    disqual_signals = []
    try:
        disqual_signals_json = get_value('disqualification_signals')
        if disqual_signals_json:
            disqual_signals = json.loads(disqual_signals_json) if isinstance(disqual_signals_json, str) else disqual_signals_json
    except (json.JSONDecodeError, TypeError):
        disqual_signals = []

    business_type = get_value('business_type') or ""
    business_name = get_value('business_name') or ""

    # Check disqualification keywords
    for keyword in DISQUALIFICATION_KEYWORDS:
        if keyword in business_type.lower():
            return False, "disqualified"
        if keyword in business_name.lower():
            return False, "disqualified"
        for signal in disqual_signals:
            if keyword in signal.lower():
                return False, "disqualified"

    # Check disqualified business types
    if business_type in DISQUALIFIED_BUSINESS_TYPES:
        return False, "disqualified"

    # Check PRIMARY ICP signals (uses growing media)
    if get_value('uses_growing_media') == True:
        return True, "primary"

    production_method = get_value('production_method') or ""
    if production_method in ["container", "greenhouse", "mixed"]:
        return True, "primary"

    if get_value('container_production') == True:
        return True, "primary"

    # Check SECONDARY ICP signals (resells growing media)
    if business_type in ["soil_mixer", "farm_supply"]:
        return True, "secondary"

    # Check TERTIARY signals (field farms that might still buy)
    if get_value('is_organic_certified') == True:
        return True, "tertiary"

    if "organic" in business_name.lower():
        return True, "tertiary"

    if production_method == "field" and get_value('acreage', 0) > 0:
        return True, "tertiary"

    # No ICP signals detected
    return False, "disqualified"

# ============================================================================
# GEOGRAPHIC SCORING FUNCTIONS (Phase 4)
# ============================================================================

def normalize_state(state: str) -> str:
    """
    Convert state name or abbreviation to 2-letter code.

    Args:
        state: State name (full or abbreviated)

    Returns:
        str: 2-letter state code or None
    """
    if not state:
        return None

    state = state.strip().upper()

    # Already 2-letter code
    if len(state) == 2 and state.isalpha():
        return state

    # Full state name lookup
    return STATE_NAMES_TO_ABBR.get(state, None)


def extract_state_from_address(address: str) -> str:
    """
    Extract state from address string.

    Handles common patterns:
    - "City, ST 12345"
    - "City, State"
    - "123 Main St, City, ST"

    Args:
        address: Full address string

    Returns:
        str: 2-letter state code or None
    """
    if not address:
        return None

    import re

    address_upper = address.upper()

    # Pattern 1: 2-letter state code before zip (most common)
    # Example: "Madison, WI 53703"
    match = re.search(r',\s*([A-Z]{2})\s+\d{5}', address_upper)
    if match:
        return match.group(1)

    # Pattern 2: 2-letter state code at end or before last comma
    # Example: "123 Main St, Madison, WI"
    match = re.search(r',\s*([A-Z]{2})\s*$', address_upper)
    if match:
        return match.group(1)

    # Pattern 3: Full state name before zip
    # Example: "Madison, Wisconsin 53703"
    for state_name, state_abbr in STATE_NAMES_TO_ABBR.items():
        if state_name in address_upper:
            return state_abbr

    return None


def calculate_geo_score(lead: dict) -> int:
    """
    Calculate geographic proximity score based on state.

    Tries multiple sources for state:
    1. lead["state"] column
    2. Parse from lead["address"]

    Args:
        lead: Lead dict or database row

    Returns:
        int: Geographic score modifier (-5 to +25)
    """
    # Helper to safely get lead values
    def get_value(key, default=None):
        if hasattr(lead, 'get'):
            return lead.get(key, default)
        else:
            try:
                return lead[key] if lead[key] is not None else default
            except (KeyError, TypeError):
                return default

    state = get_value('state')

    # Try to extract from address if state is missing
    if not state:
        address = get_value('address')
        if address:
            state = extract_state_from_address(address)

    if not state:
        return 0  # Can't determine, no modifier

    # Normalize state to 2-letter code
    state = normalize_state(state)

    if not state:
        return 0

    # Return geo score from tier mapping
    return GEO_TIERS.get(state, GEO_DEFAULT_SCORE)

# ============================================================================
# SCORING CALCULATION
# ============================================================================

def calculate_score(lead) -> dict:
    """
    Calculate score for a lead with ICP qualification gate.

    Args:
        lead: Database row (sqlite3.Row) or dict with lead data

    Returns:
        dict with keys:
            - total: Total score (integer)
            - signals: List of signal dicts (signal, points, value, description)
            - tier: Assigned tier (A/B/C/U)
            - has_data: Whether lead has sufficient data
            - icp_qualified: Boolean, passed ICP gate
            - icp_type: primary/secondary/tertiary/disqualified
    """
    signals = []
    total_score = 0

    # Helper to safely get lead values
    def get_value(key, default=None):
        if hasattr(lead, 'get'):
            return lead.get(key, default)
        else:
            try:
                return lead[key] if lead[key] is not None else default
            except (KeyError, TypeError):
                return default

    # Check if lead has sufficient data
    gemini_status = get_value('gemini_status')
    has_website = get_value('website')
    google_enrichment = get_value('enrichment_status')

    has_data = bool(has_website) or gemini_status == 'enriched' or google_enrichment == 'enriched'

    if not has_data:
        return {
            'total': 0,
            'signals': [],
            'tier': 'U',
            'has_data': False,
            'icp_qualified': False,
            'icp_type': 'disqualified',
            'geo_score': 0,  # Phase 4: No geo score for leads without data
            'reason': 'No website or enrichment data available'
        }

    # === ICP QUALIFICATION GATE ===
    icp_qualified, icp_type = check_icp_qualification(lead)

    # If disqualified, cap at Tier C regardless of positive signals
    if not icp_qualified or icp_type == "disqualified":
        return {
            'total': 0,
            'signals': [{
                'signal': 'icp_disqualified',
                'points': 0,
                'value': icp_type,
                'description': 'Does not match ICP criteria (no growing media usage or resale)'
            }],
            'tier': 'C',
            'has_data': True,
            'icp_qualified': False,
            'icp_type': icp_type,
            'geo_score': 0  # Phase 4: No geo score for disqualified leads
        }

    # === SCORE QUALIFIED LEADS ===

    business_name = get_value('business_name') or ""
    business_type = get_value('business_type') or ""

    # Organic in business name (26% of sample requesters)
    if "organic" in business_name.lower():
        signals.append({
            'signal': 'organic_in_name',
            'points': SCORING_RULES['organic_in_name']['points'],
            'value': True,
            'description': SCORING_RULES['organic_in_name']['description']
        })
        total_score += SCORING_RULES['organic_in_name']['points']

    # Certified organic
    if get_value('is_organic_certified') == True:
        signals.append({
            'signal': 'is_organic_certified',
            'points': SCORING_RULES['is_organic_certified']['points'],
            'value': True,
            'description': SCORING_RULES['is_organic_certified']['description']
        })
        total_score += SCORING_RULES['is_organic_certified']['points']

    # Organic focus
    if get_value('organic_focus') == True:
        signals.append({
            'signal': 'organic_focus',
            'points': SCORING_RULES['organic_focus']['points'],
            'value': True,
            'description': SCORING_RULES['organic_focus']['description']
        })
        total_score += SCORING_RULES['organic_focus']['points']

    # Greenhouse/container production
    production_method = get_value('production_method') or ""
    if production_method in ["greenhouse", "container", "mixed"]:
        signals.append({
            'signal': 'greenhouse_production',
            'points': SCORING_RULES['greenhouse_production']['points'],
            'value': production_method,
            'description': SCORING_RULES['greenhouse_production']['description']
        })
        total_score += SCORING_RULES['greenhouse_production']['points']

    # Uses growing media (Core ICP signal)
    if get_value('uses_growing_media') == True:
        signals.append({
            'signal': 'uses_growing_media',
            'points': SCORING_RULES['uses_growing_media']['points'],
            'value': True,
            'description': SCORING_RULES['uses_growing_media']['description']
        })
        total_score += SCORING_RULES['uses_growing_media']['points']

    # Farm in business name (43% of sample requesters)
    if "farm" in business_name.lower():
        signals.append({
            'signal': 'farm_in_name',
            'points': SCORING_RULES['farm_in_name']['points'],
            'value': True,
            'description': SCORING_RULES['farm_in_name']['description']
        })
        total_score += SCORING_RULES['farm_in_name']['points']

    # Grower(s) in business name (17% of sample requesters)
    if "grower" in business_name.lower():
        signals.append({
            'signal': 'growers_in_name',
            'points': SCORING_RULES['growers_in_name']['points'],
            'value': True,
            'description': SCORING_RULES['growers_in_name']['description']
        })
        total_score += SCORING_RULES['growers_in_name']['points']

    # Hemp/Cannabis (9% of sample requesters)
    if ("hemp" in business_name.lower() or "cannabis" in business_name.lower() or
        "hemp" in business_type.lower() or "cannabis" in business_type.lower()):
        signals.append({
            'signal': 'hemp_cannabis',
            'points': SCORING_RULES['hemp_cannabis']['points'],
            'value': True,
            'description': SCORING_RULES['hemp_cannabis']['description']
        })
        total_score += SCORING_RULES['hemp_cannabis']['points']

    # === GEOGRAPHIC PROXIMITY (Phase 4) ===
    # Calculate geo score based on state proximity to Wisconsin
    geo_score = calculate_geo_score(lead)
    if geo_score != 0:
        state = get_value('state', '')
        if not state:
            address = get_value('address', '')
            if address:
                state = extract_state_from_address(address)

        state_display = normalize_state(state) if state else "Unknown"

        if geo_score > 0:
            description = f"Geographic proximity: {state_display} (+{geo_score} pts)"
        else:
            description = f"Geographic proximity: {state_display} ({geo_score} pts)"

        signals.append({
            'signal': 'geographic_proximity',
            'points': geo_score,
            'value': state_display,
            'description': description
        })
        total_score += geo_score

    # Wholesale operation
    if get_value('is_wholesale') == True:
        signals.append({
            'signal': 'is_wholesale',
            'points': SCORING_RULES['is_wholesale']['points'],
            'value': True,
            'description': SCORING_RULES['is_wholesale']['description']
        })
        total_score += SCORING_RULES['is_wholesale']['points']

    # Purchases soil/amendments
    if get_value('purchases_soil') == True:
        signals.append({
            'signal': 'purchases_soil',
            'points': SCORING_RULES['purchases_soil']['points'],
            'value': True,
            'description': SCORING_RULES['purchases_soil']['description']
        })
        total_score += SCORING_RULES['purchases_soil']['points']

    # Soil brands mentioned
    try:
        soil_brands = json.loads(get_value('soil_brands_mentioned') or "[]")
        if len(soil_brands) > 0:
            signals.append({
                'signal': 'soil_brands_mentioned',
                'points': SCORING_RULES['soil_brands_mentioned']['points'],
                'value': ", ".join(soil_brands),
                'description': SCORING_RULES['soil_brands_mentioned']['description']
            })
            total_score += SCORING_RULES['soil_brands_mentioned']['points']
    except (json.JSONDecodeError, TypeError):
        pass

    # Large scale (2+ scale indicators)
    try:
        scale_indicators = json.loads(get_value('scale_indicators') or "[]")
        if len(scale_indicators) >= 2:
            signals.append({
                'signal': 'large_scale',
                'points': SCORING_RULES['large_scale']['points'],
                'value': len(scale_indicators),
                'description': SCORING_RULES['large_scale']['description']
            })
            total_score += SCORING_RULES['large_scale']['points']
    except (json.JSONDecodeError, TypeError):
        pass

    # Acreage mentioned
    acreage = get_value('acreage', 0)
    if acreage and acreage > 0:
        signals.append({
            'signal': 'acreage_mentioned',
            'points': SCORING_RULES['acreage_mentioned']['points'],
            'value': acreage,
            'description': SCORING_RULES['acreage_mentioned']['description']
        })
        total_score += SCORING_RULES['acreage_mentioned']['points']

    # Large greenhouse (> 10,000 sq ft)
    greenhouse_sqft = get_value('greenhouse_sqft', 0)
    if greenhouse_sqft and greenhouse_sqft > 10000:
        signals.append({
            'signal': 'large_greenhouse',
            'points': SCORING_RULES['large_greenhouse']['points'],
            'value': greenhouse_sqft,
            'description': SCORING_RULES['large_greenhouse']['description']
        })
        total_score += SCORING_RULES['large_greenhouse']['points']

    # Multiple locations
    if get_value('multiple_locations') == True:
        signals.append({
            'signal': 'multiple_locations',
            'points': SCORING_RULES['multiple_locations']['points'],
            'value': True,
            'description': SCORING_RULES['multiple_locations']['description']
        })
        total_score += SCORING_RULES['multiple_locations']['points']

    # Appointment only
    if get_value('appointment_only') == True:
        signals.append({
            'signal': 'appointment_only',
            'points': SCORING_RULES['appointment_only']['points'],
            'value': True,
            'description': SCORING_RULES['appointment_only']['description']
        })
        total_score += SCORING_RULES['appointment_only']['points']

    # Closed weekends
    if get_value('closed_weekends') == True:
        signals.append({
            'signal': 'closed_weekends',
            'points': SCORING_RULES['closed_weekends']['points'],
            'value': True,
            'description': SCORING_RULES['closed_weekends']['description']
        })
        total_score += SCORING_RULES['closed_weekends']['points']

    # === NEGATIVE SIGNALS ===

    # Parse negative indicators
    negative_indicators = {}
    try:
        neg_json = get_value('negative_indicators')
        if neg_json:
            negative_indicators = json.loads(neg_json) if isinstance(neg_json, str) else neg_json
    except (json.JSONDecodeError, TypeError):
        negative_indicators = {}

    # Landscaping services
    if negative_indicators.get('landscaping_services') or "landscap" in business_type.lower():
        signals.append({
            'signal': 'landscaping_services',
            'points': SCORING_RULES['landscaping_services']['points'],
            'value': True,
            'description': SCORING_RULES['landscaping_services']['description']
        })
        total_score += SCORING_RULES['landscaping_services']['points']

    # Christmas tree farm
    if negative_indicators.get('christmas_tree') or "christmas" in business_type.lower():
        signals.append({
            'signal': 'christmas_tree',
            'points': SCORING_RULES['christmas_tree']['points'],
            'value': True,
            'description': SCORING_RULES['christmas_tree']['description']
        })
        total_score += SCORING_RULES['christmas_tree']['points']

    # Sod/turf production
    if negative_indicators.get('sod_turf') or "sod" in business_type.lower() or "turf" in business_type.lower():
        signals.append({
            'signal': 'sod_turf',
            'points': SCORING_RULES['sod_turf']['points'],
            'value': True,
            'description': SCORING_RULES['sod_turf']['description']
        })
        total_score += SCORING_RULES['sod_turf']['points']

    # Gift shop focus
    if negative_indicators.get('gift_shop') or "gift" in business_type.lower():
        signals.append({
            'signal': 'gift_shop',
            'points': SCORING_RULES['gift_shop']['points'],
            'value': True,
            'description': SCORING_RULES['gift_shop']['description']
        })
        total_score += SCORING_RULES['gift_shop']['points']

    # Retail only (no wholesale, no growing)
    if (business_type == "nursery_retail" and not get_value('is_wholesale') and
        not get_value('container_production')):
        signals.append({
            'signal': 'retail_only',
            'points': SCORING_RULES['retail_only']['points'],
            'value': True,
            'description': SCORING_RULES['retail_only']['description']
        })
        total_score += SCORING_RULES['retail_only']['points']

    # Assign tier based on score and ICP type
    tier = assign_tier(total_score, icp_type)

    return {
        'total': total_score,
        'signals': signals,
        'tier': tier,
        'has_data': True,
        'icp_qualified': icp_qualified,
        'icp_type': icp_type,
        'geo_score': geo_score  # Phase 4: Geographic proximity score
    }

# ============================================================================
# TIER ASSIGNMENT
# ============================================================================

def assign_tier(score: int, icp_type: str) -> str:
    """
    Assign tier based on ICP qualification and score.

    Philosophy: ICP qualification is the primary filter. The tier system
    separates qualified leads by score, not by qualification.

    Tier logic:
    - Tier A: ICP qualified + strong signals (40+ points)
    - Tier B: ICP qualified (any score) - meets core business criteria
    - Tier C: ICP disqualified - doesn't use/resell growing media

    Target distribution (~90 enriched leads):
    - Tier A: ~10% (hot prospects with multiple positive signals)
    - Tier B: ~25-30% (qualified, may need nurturing)
    - Tier C: ~60-65% (wrong business model)

    Args:
        score: Total score (integer)
        icp_type: primary/secondary/tertiary/disqualified

    Returns:
        str: Tier (A/B/C)
    """
    # Disqualified leads always go to Tier C
    if icp_type == "disqualified":
        return 'C'

    # All ICP-qualified leads get at least Tier B
    # Only score determines A vs B
    if score >= 40:
        return 'A'
    else:
        return 'B'

# ============================================================================
# TEST FUNCTION
# ============================================================================

def test_scorer():
    """Test the ICP-based scoring function with geographic intelligence."""

    print("Testing ICP-Based Scoring Engine (Phase 4 - With Geographic Intelligence)")
    print("=" * 80)
    print()

    # Test case 1: PRIMARY ICP - Organic container nursery in Wisconsin
    test_lead_1 = {
        'gemini_status': 'enriched',
        'website': 'http://example.com',
        'business_name': 'Green Valley Organic Farm',
        'business_type': 'wholesale_nursery',
        'state': 'WI',
        'is_wholesale': True,
        'uses_growing_media': True,
        'production_method': 'container',
        'is_organic_certified': True,
        'organic_focus': True,
        'container_production': True,
        'purchases_soil': True,
        'soil_brands_mentioned': json.dumps(['Pro-Mix', 'Sungro']),
        'scale_indicators': json.dumps(['45 acres', '200,000 sq ft greenhouse']),
        'acreage': 45,
        'greenhouse_sqft': 200000,
        'multiple_locations': False,
        'appointment_only': True,
        'closed_weekends': False,
        'disqualification_signals': json.dumps([]),
        'negative_indicators': json.dumps({
            'landscaping_services': False,
            'christmas_tree': False,
            'sod_turf': False,
            'gift_shop': False
        })
    }

    result_1 = calculate_score(test_lead_1)
    print("Test 1: Organic Container Farm in WI (Expected: Tier A)")
    print(f"ICP Qualified: {result_1['icp_qualified']}")
    print(f"ICP Type: {result_1['icp_type']}")
    print(f"Score: {result_1['total']}")
    print(f"Tier: {result_1['tier']}")
    print(f"Signals triggered: {len(result_1['signals'])}")
    for signal in result_1['signals']:
        print(f"  {signal['signal']}: {signal['points']} points - {signal['description']}")
    print()

    # Test case 2: DISQUALIFIED - Landscaping company
    test_lead_2 = {
        'gemini_status': 'enriched',
        'website': 'http://example.com',
        'business_name': 'Beautiful Landscapes Inc',
        'business_type': 'landscaper',
        'state': 'WI',
        'is_wholesale': False,
        'uses_growing_media': False,
        'production_method': 'unknown',
        'disqualification_signals': json.dumps(['landscaping services', 'lawn care']),
        'negative_indicators': json.dumps({
            'landscaping_services': True,
            'christmas_tree': False
        })
    }

    result_2 = calculate_score(test_lead_2)
    print("Test 2: Landscaping Company (Expected: Tier C - Disqualified)")
    print(f"ICP Qualified: {result_2['icp_qualified']}")
    print(f"ICP Type: {result_2['icp_type']}")
    print(f"Score: {result_2['total']}")
    print(f"Tier: {result_2['tier']}")
    print()

    # Test case 3: TERTIARY ICP - Field farm with organic cert
    test_lead_3 = {
        'gemini_status': 'enriched',
        'website': 'http://example.com',
        'business_name': 'Sunny Acres Organic Farm',
        'business_type': 'organic_vegetable_farm',
        'state': 'IA',
        'is_wholesale': False,
        'uses_growing_media': False,
        'production_method': 'field',
        'is_organic_certified': True,
        'organic_focus': True,
        'acreage': 80,
        'scale_indicators': json.dumps(['80 acres']),
        'disqualification_signals': json.dumps([]),
        'negative_indicators': json.dumps({})
    }

    result_3 = calculate_score(test_lead_3)
    print("Test 3: Organic Field Farm in Iowa (Expected: Tier B or C - Tertiary ICP, +20 geo)")
    print(f"ICP Qualified: {result_3['icp_qualified']}")
    print(f"ICP Type: {result_3['icp_type']}")
    print(f"Score: {result_3['total']}")
    print(f"Geo Score: {result_3['geo_score']}")
    print(f"Tier: {result_3['tier']}")
    for signal in result_3['signals']:
        print(f"  {signal['signal']}: {signal['points']} points")
    print()

    # Test case 4: GEOGRAPHIC SCORING TEST
    print("Test 4: Geographic Scoring Validation")
    print("-" * 40)
    geo_test_cases = [
        {"name": "Wisconsin (Local)", "state": "WI", "expected": 25},
        {"name": "Illinois (Regional)", "state": "IL", "expected": 20},
        {"name": "Minnesota (Regional)", "state": "MN", "expected": 20},
        {"name": "Indiana (Near)", "state": "IN", "expected": 10},
        {"name": "Kansas (Mid)", "state": "KS", "expected": 0},
        {"name": "Texas (Far)", "state": "TX", "expected": -5},
        {"name": "California (Far)", "state": "CA", "expected": -5},
        {"name": "No State", "state": None, "expected": 0},
        {"name": "From Address", "state": None, "address": "123 Main St, Madison, WI 53703", "expected": 25},
    ]

    for test in geo_test_cases:
        lead = {'state': test.get('state'), 'address': test.get('address')}
        score = calculate_geo_score(lead)
        status = "PASS" if score == test['expected'] else "FAIL"
        print(f"  [{status}] {test['name']}: {score} (expected: {test['expected']})")
    print()

    print("ICP-Based Scoring Engine tests complete!")
    print()
    print("Key Features:")
    print("- [X] ICP qualification is primary filter (qualified = Tier B minimum)")
    print("- [X] Sample requester insights (organic, farm, growers, hemp)")
    print("- [X] Geographic proximity scoring (WI: +25, Regional: +20, Far: -5)")
    print("- [X] Tier assignment: A=40+ pts, B=ICP qualified, C=disqualified")
    print("- [X] Disqualification signals enforced")
    print("- [X] State extraction from address strings")

if __name__ == '__main__':
    test_scorer()
