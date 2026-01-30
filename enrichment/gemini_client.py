import os
import time
import json
import re
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Gemini
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if not GEMINI_API_KEY:
    print("⚠️  GEMINI_API_KEY not found - Gemini enrichment will be disabled")
    GEMINI_CONFIGURED = False
else:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_CONFIGURED = True

# Use Gemini 2.5 Flash (January 2026) - Latest GA model
# Lightning-fast, highly capable, optimized for structured extraction
# Best for high-throughput tasks with balance of speed and quality
MODEL_NAME = 'gemini-2.0-flash'

def call_gemini(prompt, max_retries=5):
    """
    Call Gemini API with retry logic and error handling.

    Args:
        prompt: The prompt to send to Gemini
        max_retries: Maximum number of retry attempts (default 5)

    Returns:
        dict: Parsed JSON response from Gemini

    Raises:
        Exception: If all retries fail or response is invalid
    """
    if not GEMINI_CONFIGURED:
        raise ValueError("Gemini is not configured. Please set GEMINI_API_KEY environment variable.")
    
    model = genai.GenerativeModel(MODEL_NAME)

    for attempt in range(max_retries):
        try:
            # Call Gemini API with 30 second timeout
            response = model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.1,  # Low temperature for more deterministic output
                    'top_p': 0.8,
                    'top_k': 40,
                    'max_output_tokens': 2048,
                }
            )

            # Extract text from response
            if not response or not response.text:
                raise ValueError("Empty response from Gemini")

            response_text = response.text.strip()

            # Try to extract JSON from response
            # Sometimes Gemini wraps JSON in markdown code blocks
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)

            # Parse JSON
            try:
                data = json.loads(response_text)
                return data
            except json.JSONDecodeError as e:
                # Try to find JSON object in response
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1

                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    data = json.loads(json_str)
                    return data
                else:
                    raise ValueError(f"Could not parse JSON from response: {e}")

        except Exception as e:
            error_str = str(e).lower()

            # Check if rate limited (429)
            if '429' in error_str or 'rate limit' in error_str or 'quota' in error_str or 'resource' in error_str:
                # Longer exponential backoff for rate limits: 2s, 4s, 8s, 16s, 32s
                wait_time = 2 ** (attempt + 1)
                print(f"[RATE LIMIT] Waiting {wait_time}s before retry (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue

            # Other errors - retry with exponential backoff
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 1s, 2s, 4s, 8s, 16s
                print(f"[ERROR] {str(e)[:100]} - Retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
            else:
                # Final attempt failed
                raise Exception(f"Gemini API failed after {max_retries} attempts: {str(e)[:200]}")

    raise Exception(f"Gemini API failed after {max_retries} attempts")

def enrich_lead_with_gemini(website_text, business_name, city, state):
    """
    Enrich a lead using Gemini to analyze website content.

    Args:
        website_text: Extracted text from website
        business_name: Name of the business
        city: City location
        state: State location

    Returns:
        dict: Enriched data extracted from website

    Raises:
        Exception: If API call fails or data is invalid
    """

    # Validate input
    if not website_text or len(website_text) < 100:
        raise ValueError("Insufficient website text for analysis")

    # Build the enrichment prompt with ICP-specific signals
    prompt = f"""You are analyzing a nursery/grower business website to determine if they are a potential buyer of bulk worm castings (vermicompost) for agricultural or horticultural use.

Business Name: {business_name}
Location: {city}, {state}

Website Content:
{website_text[:15000]}

EXTRACTION FOCUS - ICP (Ideal Customer Profile) Signals:

1. GROWING MEDIA USAGE (Critical ICP Signal)
   - Do they use soil, potting mix, or growing media in production?
   - Container/pot production = YES
   - Greenhouse propagation = YES
   - Field grown non-organic = MAYBE
   - Hydroponic/no soil = NO

2. PRODUCTION METHOD (Determines soil needs)
   - Container: potted plants, plug trays, liner production
   - Greenhouse: heated/controlled environment growing
   - Field: direct ground planting
   - Hydroponic: water-based, no soil
   - Mixed: combination of methods

3. ORGANIC CERTIFICATION (Strong buying signal)
   - Look for: "Certified Organic", USDA Organic, organic certification
   - "Organic" in business name or prominent on site
   - Sustainable/regenerative farming language

4. SCALE INDICATORS (Volume potential - be specific!)
   - Greenhouse square footage: "180,000 sq ft greenhouse"
   - Number of facilities: "12 greenhouses", "4 hoop houses"
   - Acreage under production: "100 acres in production"
   - Production volume: "500,000 plants annually", "2 million plugs/year"
   - Employee count if mentioned
   - Multiple locations

5. SOIL PURCHASING SIGNALS (Confirmed soil buyer)
   - Mentions buying: potting soil, growing media, amendments, compost
   - Mentions brands: Pro-Mix, Sungro, Berger, Fox Farm, Miracle-Gro
   - "We mix our own soil" = HIGH priority
   - Soil health/building soil language
   - Any mention of vermicompost or worm castings = VERY HIGH priority

6. DISQUALIFICATION SIGNALS (Red flags)
   - Landscaping installation, lawn care, mowing services
   - Equipment dealer, machinery sales
   - Retail only with no growing operation
   - Florist with no production
   - Christmas tree farm (field grown)
   - Sod/turf production

Extract the following information and return ONLY a valid JSON object (no markdown, no explanation):

{{
  "owner_name": "Full name of owner/founder if mentioned, or null",
  "contact_name": "REQUIRED: Full name of ANY relevant contact who would purchase bulk growing media. Priority order: 1) Owner/President, 2) Operations Manager, 3) Head Grower, 4) Purchasing Manager, 5) Propagation Manager, 6) Greenhouse Manager, 7) Sales/Marketing. Return first match found, or null if none.",
  "contact_title": "The role/title of contact_name (e.g., 'Operations Manager', 'Head Grower', 'Owner'), or null",
  "contact_priority": "Integer 1-7 indicating which priority level (1=Owner, 2=Ops Mgr, 3=Grower, 4=Purchasing, 5=Propagation, 6=Greenhouse, 7=Sales/Marketing), or null",
  "email": "Contact email if found (not generic info@), or null",
  "business_type": "Choose ONE: wholesale_nursery, retail_nursery, container_production, greenhouse_propagation, grower_only, garden_center, cannabis_cultivator, hemp_grower, landscape_supplier, christmas_tree_farm, sod_farm, orchard, tree_farm, microgreens_specialty, soil_mixer, farm_supply, landscaper, other, unknown",
  "is_wholesale": true/false (do they sell to trade/wholesale customers?),
  "is_retail": true/false (do they sell direct to consumers?),
  "greenhouse_sqft": "Integer square footage if mentioned, or null",
  "acreage": "Number of acres if mentioned, or null",
  "multiple_locations": true/false (do they have multiple physical locations?),
  "size_signals": ["Array of specific quotes mentioning size, like '50 acre facility', '200,000 sq ft greenhouse'"],
  "container_production": true/false (do they grow in containers/pots?),
  "soil_relevance": true/false (would they use potting soil, growing media, or soil amendments?),
  "organic_focus": true/false (do they emphasize organic/sustainable practices?),
  "crops_grown": ["Array of main plant types they grow, e.g. 'annuals', 'perennials', 'trees', 'shrubs', 'vegetables', 'cannabis'"],
  "negative_indicators": {{
    "christmas_tree": true/false (are they primarily a Christmas tree farm?),
    "sod_turf": true/false (do they grow sod/turf grass?),
    "bare_root": true/false (do they mention bare root production?),
    "ball_and_burlap": true/false (do they mention ball and burlap (B&B) trees?),
    "landscaping_services": true/false (do they offer landscaping installation services?),
    "gift_shop": true/false (do they have a gift shop/home decor focus?),
    "workshops_classes": true/false (do they offer workshops, classes, or events?),
    "orchard_upick": true/false (are they a u-pick orchard/fruit farm?),
    "tree_farm_field": true/false (are they a field-grown tree farm?)
  }},
  "appointment_only": true/false (do they require appointments?),
  "closed_weekends": true/false (are they closed both Saturday AND Sunday based on website?),
  "confidence": "low/medium/high (your confidence in the extracted data)",

  "uses_growing_media": true/false (REQUIRED: Do they use soil/potting mix/growing media in production?),
  "production_method": "field/container/greenhouse/hydroponic/mixed/unknown (REQUIRED: Primary production method)",
  "is_organic_certified": true/false (Are they certified organic or explicitly organic-focused?),
  "scale_indicators": ["REQUIRED: Specific scale mentions like '12 greenhouses', '40 acres', '500k plants/year'. Empty array if none."],
  "purchases_soil": true/false (Any mention of purchasing soil, potting mix, amendments, or brands?),
  "soil_brands_mentioned": ["Specific brands: Pro-Mix, Sungro, Berger, Fox Farm, etc. Empty array if none."],
  "disqualification_signals": ["REQUIRED: Red flags like 'landscaping services', 'lawn care', 'retail only', 'no growing operation'. Empty array if clean."]
}}

IMPORTANT - CONTACT EXTRACTION (AGGRESSIVE MODE):
- **contact_name**: Look for ANY person who would buy bulk growing media/soil. Use 2-phase approach:

PHASE 1 - Search for TITLED positions (Priority 1-7):
  1. Owner/President/Founder (look for: "Owner", "President", "Founder", "Co-owner")
  2. Operations Manager (look for: "Operations Manager", "General Manager", "Production Manager")
  3. Head Grower/Master Grower (look for: "Head Grower", "Master Grower", "Lead Grower")
  4. Purchasing Manager (look for: "Purchasing", "Procurement", "Supply Chain")
  5. Propagation Manager (look for: "Propagation Manager", "Propagator")
  6. Greenhouse Manager (look for: "Greenhouse Manager", "Hoop House Manager")
  7. Sales/Marketing (last resort: "Sales Manager", "Marketing Director")

PHASE 2 - If NO titled position found, extract BEST GUESS name (Priority NULL):
  - Look for: Family names in "About Us", names in team photos, founders mentioned in history
  - Context clues: "Started by John Smith", "The Smith Family", "Meet the Growers: Jane Doe"
  - Names associated with business (e.g., "John's Greenhouse" → likely John is owner)
  - Email signatures, contact forms with names
  - **ALWAYS extract a name if you find ANY person mentioned** - even without title

- Extract the FIRST match found from Phase 1, OR best guess from Phase 2
- If multiple people at same level, pick the one with more context
- Look in: About Us, Team, Staff, Contact, History pages, email signatures, bios
- Require FULL name (first + last), not just "John" or "The Smith Family"
- **contact_priority**: 1-7 if titled position found, null if best guess
- **contact_title**: Extract their actual title, or "No role found" if best guess

OTHER RULES:
- Return ONLY the JSON object, no markdown formatting
- Use true/false for booleans (not "true"/"false")
- Use null for unknown/missing values
- For arrays, use [] if empty
- Be conservative - if unsure, mark as null or false
- "is_wholesale" should be true if they mention: trade customers, wholesale, nursery professionals, landscape contractors, growers
- "container_production" is true if they mention: containers, pots, potted plants, container-grown
- "soil_relevance" is true unless they only do bare-root, field-grown, or B&B with no container production
- "closed_weekends" should only be true if BOTH Saturday AND Sunday are closed (not just one day)

Few-shot Examples:

Example 1 - Wholesale Container Nursery:
Website: "Green Valley Growers - 45 acre wholesale nursery specializing in container-grown perennials and shrubs. We supply landscape professionals and garden centers throughout the Midwest. Contact: john@greenvalley.com. Trade customers only - appointments required."
Output:
{{
  "owner_name": null,
  "email": "john@greenvalley.com",
  "business_type": "wholesale_nursery",
  "is_wholesale": true,
  "is_retail": false,
  "greenhouse_sqft": null,
  "acreage": 45,
  "multiple_locations": false,
  "size_signals": ["45 acre wholesale nursery"],
  "container_production": true,
  "soil_relevance": true,
  "organic_focus": false,
  "crops_grown": ["perennials", "shrubs"],
  "negative_indicators": {{
    "christmas_tree": false,
    "sod_turf": false,
    "bare_root": false,
    "ball_and_burlap": false,
    "landscaping_services": false,
    "gift_shop": false,
    "workshops_classes": false,
    "orchard_upick": false,
    "tree_farm_field": false
  }},
  "appointment_only": true,
  "closed_weekends": false,
  "confidence": "high",
  "uses_growing_media": true,
  "production_method": "container",
  "is_organic_certified": false,
  "scale_indicators": ["45 acre wholesale nursery"],
  "purchases_soil": false,
  "soil_brands_mentioned": [],
  "disqualification_signals": []
}}

Example 2 - Retail Garden Center:
Website: "Bloom & Grow Garden Center - Your destination for plants, gifts, and garden inspiration! Open 7 days a week. Join us for our monthly workshops on container gardening. Beautiful selection of annuals, perennials, and home decor. We also offer full landscape design and installation services."
Output:
{{
  "owner_name": null,
  "email": null,
  "business_type": "garden_center",
  "is_wholesale": false,
  "is_retail": true,
  "greenhouse_sqft": null,
  "acreage": null,
  "multiple_locations": false,
  "size_signals": [],
  "container_production": false,
  "soil_relevance": true,
  "organic_focus": false,
  "crops_grown": ["annuals", "perennials"],
  "negative_indicators": {{
    "christmas_tree": false,
    "sod_turf": false,
    "bare_root": false,
    "ball_and_burlap": false,
    "landscaping_services": true,
    "gift_shop": true,
    "workshops_classes": true,
    "orchard_upick": false,
    "tree_farm_field": false
  }},
  "appointment_only": false,
  "closed_weekends": false,
  "confidence": "high",
  "uses_growing_media": false,
  "production_method": "unknown",
  "is_organic_certified": false,
  "scale_indicators": [],
  "purchases_soil": false,
  "soil_brands_mentioned": [],
  "disqualification_signals": ["landscaping services", "gift shop focused", "workshops (retail focus)"]
}}

Now analyze the business above and return the JSON:"""

    # Call Gemini
    try:
        data = call_gemini(prompt)

        # Validate required fields exist (including new ICP fields)
        required_fields = [
            'business_type', 'is_wholesale', 'is_retail', 'container_production',
            'soil_relevance', 'negative_indicators', 'confidence',
            # Phase 2: New ICP fields
            'uses_growing_media', 'production_method', 'scale_indicators', 'disqualification_signals'
        ]

        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        # Validate negative_indicators is a dict
        if not isinstance(data.get('negative_indicators'), dict):
            raise ValueError("negative_indicators must be a dictionary")

        # Ensure arrays are arrays
        if 'size_signals' not in data or data['size_signals'] is None:
            data['size_signals'] = []
        if 'crops_grown' not in data or data['crops_grown'] is None:
            data['crops_grown'] = []
        # Phase 2: New ICP array fields
        if 'scale_indicators' not in data or data['scale_indicators'] is None:
            data['scale_indicators'] = []
        if 'soil_brands_mentioned' not in data or data['soil_brands_mentioned'] is None:
            data['soil_brands_mentioned'] = []
        if 'disqualification_signals' not in data or data['disqualification_signals'] is None:
            data['disqualification_signals'] = []

        return data

    except Exception as e:
        raise Exception(f"Failed to enrich with Gemini: {str(e)[:200]}")

def test_gemini_enrichment():
    """Test Gemini enrichment on sample data."""

    # Test data
    test_text = """
    Green Valley Growers - Wholesale Container Nursery

    We are a 45-acre wholesale nursery specializing in container-grown perennials and shrubs.
    Founded by John Smith in 1995. We supply landscape professionals and garden centers
    throughout the Midwest.

    Our facility includes 200,000 square feet of greenhouse space and 30 acres of outdoor
    container growing area. We grow over 500 varieties of perennials, ornamental grasses,
    and flowering shrubs.

    Trade customers only. Appointments required for visits.
    Contact: john.smith@greenvalley.com
    """

    print("Testing Gemini Enrichment")
    print("=" * 80)
    print()

    try:
        result = enrich_lead_with_gemini(
            website_text=test_text,
            business_name="Green Valley Growers",
            city="Madison",
            state="WI"
        )

        print("[SUCCESS] Gemini enrichment completed")
        print()
        print("Extracted Data:")
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return False

    return True

def generate_personalization(business_name, business_type, organic_focus, crops_grown, size_signals, is_wholesale, container_production):
    """
    Generate a personalized email opening line using Gemini.

    Args:
        business_name: Name of the business
        business_type: Type of business (from Gemini enrichment)
        organic_focus: Boolean, organic/sustainable focus
        crops_grown: Array of crops/plants grown
        size_signals: Array of size indicators
        is_wholesale: Boolean, sells wholesale
        container_production: Boolean, container production

    Returns:
        dict: {
            'custom_line': 'Generated opening line',
            'email_angle': 'organic/wholesale/cannabis/size/container/general'
        }

    Raises:
        Exception: If generation fails
    """

    # Determine the best angle based on characteristics
    angle = 'general'
    if 'cannabis' in (business_type or '').lower():
        angle = 'cannabis'
    elif organic_focus:
        angle = 'organic'
    elif is_wholesale:
        angle = 'wholesale'
    elif size_signals and len(size_signals) > 0:
        angle = 'size'
    elif container_production:
        angle = 'container'

    # Build context for prompt
    crops_text = ', '.join(crops_grown) if crops_grown else 'various plants'
    size_text = size_signals[0] if size_signals and len(size_signals) > 0 else ''

    prompt = f"""You are writing the opening line of a cold email to a nursery/grower business.

Business: {business_name}
Type: {business_type or 'nursery'}
Wholesale: {is_wholesale}
Container Production: {container_production}
Organic Focus: {organic_focus}
Crops Grown: {crops_text}
Size: {size_text}

Generate a personalized opening line (max 15 words) that:
1. References something specific about their business
2. Is conversational and friendly, not salesy
3. Shows you've researched them
4. Leads naturally into discussing potting soil needs
5. Avoids generic phrases like "I noticed" or "I came across"

Good examples:
- "Your 50-acre organic perennial operation sounds like it goes through a lot of potting mix."
- "Growing cannabis in containers at your scale must require consistent, reliable growing media."
- "With your focus on sustainable practices, you probably value clean, organic soil components."
- "Supplying wholesale customers means you need dependable soil availability year-round."
- "200,000 sq ft of greenhouse production - that's impressive container growing capacity."

Bad examples (too generic):
- "I noticed you're a nursery and wanted to reach out."
- "I came across your business online."
- "I'd love to learn more about your operation."

Return ONLY the opening line, no explanation, no JSON, just the text (max 15 words):"""

    try:
        # Call Gemini with low temperature for consistency
        model = genai.GenerativeModel(MODEL_NAME)

        response = model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.3,  # Slightly higher for creativity
                'top_p': 0.9,
                'top_k': 40,
                'max_output_tokens': 50,  # Short response
            }
        )

        if not response or not response.text:
            raise ValueError("Empty response from Gemini")

        custom_line = response.text.strip()

        # Remove quotes if Gemini added them
        custom_line = custom_line.strip('"\'')

        # Validate length (15 words max)
        word_count = len(custom_line.split())
        if word_count > 18:  # Allow slight flexibility
            # Truncate to approximately 15 words
            words = custom_line.split()[:15]
            custom_line = ' '.join(words)
            if not custom_line.endswith('.'):
                custom_line += '.'

        return {
            'custom_line': custom_line,
            'email_angle': angle
        }

    except Exception as e:
        raise Exception(f"Failed to generate personalization: {str(e)[:200]}")

if __name__ == '__main__':
    test_gemini_enrichment()
