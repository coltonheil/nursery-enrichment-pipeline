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

def build_nursery_prompt(website_text, business_name, city, state):
    """
    Build the nursery/grower enrichment prompt.
    This is the original nursery-focused prompt — do NOT modify.

    Args:
        website_text: Extracted text from website
        business_name: Name of the business
        city: City location
        state: State location

    Returns:
        str: Prompt string to send to Gemini
    """
    return f"""You are analyzing a nursery/grower business website to determine if they are a potential buyer of bulk worm castings (vermicompost) for agricultural or horticultural use.

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


# =============================================================================
# Phase 3: Segment-Aware Prompt Builders
# Cannabis and hemp websites use different language than nursery sites.
# These prompt builders extract the same ICP signals in segment-appropriate language.
# The existing build_nursery_prompt() above is UNCHANGED.
# =============================================================================

def build_cannabis_prompt(website_text, business_name='', city='', state=''):
    """
    Build a cannabis cultivator enrichment prompt.

    Extracts ICP signals specific to cannabis cultivation operations.
    Key difference from nursery prompt: cannabis uses 'canopy sqft', 'grow room',
    'cultivation', 'flower', 'clone', 'veg', 'harvest' — not 'potting mix' or 'greenhouse'.

    Field mapping to existing DB columns:
      cultivation_type  → production_method
      indoor_sqft       → greenhouse_sqft  (reused — indoor sq ft is analogous)
      canopy_sqft       → greenhouse_sqft  (same)
      uses_amendments   → uses_growing_media
      dispensary_only   → negative_indicators.dispensary_only
      organic_certified → is_organic_certified

    Args:
        website_text: Extracted text from cannabis business website
        business_name: Name of the business (optional)
        city: City location (optional)
        state: State location (optional)

    Returns:
        str: Prompt string to send to Gemini
    """
    business_context = ''
    if business_name:
        business_context += f'\nBusiness Name: {business_name}'
    if city and state:
        business_context += f'\nLocation: {city}, {state}'

    return f"""You are analyzing a cannabis business website to determine if they are a potential buyer of bulk worm castings (vermicompost) for use as a soil amendment in cannabis cultivation.

Sweet Leaf Soil sells premium worm castings that cannabis cultivators use to:
- Improve soil structure in grow media
- Add microbial life to coco coir and soil blends
- Feed plants organically throughout the grow cycle
- Reduce synthetic nutrient inputs{business_context}

Website Content:
{website_text[:15000]}

EXTRACTION FOCUS — Cannabis Cultivator ICP Signals:

1. CULTIVATION TYPE (Critical — determines if they need amendments)
   - Indoor: climate-controlled grow rooms, LED/HPS lights, environmental controls → HIGH value
   - Greenhouse: hoop houses, light dep greenhouses, sun+supplemental light → HIGH value
   - Outdoor: sun-grown, full-sun fields → MEDIUM value (seasonal amendments)
   - Mixed: combination of indoor + outdoor + greenhouse → HIGH value
   - If they ONLY dispense (no grow mentioned) → DISQUALIFY

2. FACILITY SIZE (Volume potential)
   - indoor_sqft: total square footage of indoor grow space ("50,000 sq ft facility", "10,000 sqft canopy")
   - canopy_sqft: licensed canopy square footage (Michigan uses "canopy" specifically)
   - plant_count: licensed plant count if mentioned ("1,500 plants", "Class C = 1,500 plant limit")
   - Multiple locations = higher volume

3. GROWING MEDIA & AMENDMENT SIGNALS (Direct buying signal)
   - Do they mention soil, coco coir, peat, growing media, substrates?
   - Do they mention organic inputs, compost, amendments, top dressing?
   - "We amend our soil with..." = HIGH priority
   - "Organic growing practices" = HIGH priority
   - Any explicit mention of worm castings / vermicompost = VERY HIGH priority

4. ORGANIC / CLEAN CERTIFICATION (Premium buyer signal)
   - Clean Green Certified (cannabis-specific organic cert)
   - Sun+Earth Certified
   - "Craft cannabis", "sun-grown", "living soil" language
   - "No pesticides", "organic practices" = positive signal

5. BUSINESS TYPE (Critical qualifier)
   - cannabis_cultivator: licensed to grow (Class A/B/C in MI, Tier 1/2/3 in OR, Craft Grower in IL)
   - dispensary: sells cannabis but has NO grow license or facility — DISQUALIFY
   - processor: extracts/processes cannabis, may or may not grow
   - mixed: cultivates AND dispenses AND/OR processes — qualify if they cultivate

6. DISQUALIFICATION SIGNALS
   - Dispensary only (no cultivation): they buy wholesale, don't grow → DO NOT SELL GROWING MEDIA
   - Processing only (extraction, no plants): no soil needed
   - Cannabis tech company / software / delivery service

Extract and return ONLY a valid JSON object (no markdown, no explanation):

{{
  "business_type": "cannabis_cultivator / dispensary / processor / mixed / unknown",
  "cultivation_type": "indoor / outdoor / greenhouse / mixed / unknown (primary cultivation method)",
  "indoor_sqft": "Integer square footage of indoor grow space, or null if not mentioned",
  "canopy_sqft": "Integer licensed canopy square footage if mentioned (common in Michigan), or null",
  "plant_count": "Integer licensed plant count if mentioned, or null",
  "license_type": "Class A/B/C cultivator, Tier 1/2/3, Craft Grower, etc. if mentioned, or null",
  "uses_amendments": true/false (Do they mention soil amendments, compost, organic inputs, growing media?),
  "uses_worm_castings": true/false (Explicit mention of worm castings, vermicompost, earthworm castings?),
  "organic_certified": true/false (Clean Green, Sun+Earth, or stated organic practices?),
  "dispensary_only": true/false (DISQUALIFY: they sell cannabis but have NO grow operation),
  "multiple_locations": true/false (Do they operate from multiple locations?),
  "crops_grown": ["cannabis"],
  "scale_indicators": ["Array of specific size/scale quotes from the website, e.g. '50,000 sqft indoor facility', '1,500 plant license'"],
  "disqualification_signals": ["Array of red flags, e.g. 'dispensary only', 'no grow license', 'delivery service only'"],
  "contact_name": "REQUIRED: Full name of ANY relevant contact — owner, head grower, operations manager, or any named person. Return first match found, or null.",
  "contact_title": "Their role/title if known, or 'No role found' if name found without title, or null",
  "email": "ANY contact email on the site — info@, contact@, hello@, sales@ are ALL VALID. Only skip noreply@/donotreply@. Return the best one found, or null.",
  "confidence": "low / medium / high (confidence in extracted data)"
}}

IMPORTANT - CONTACT & EMAIL EXTRACTION (AGGRESSIVE MODE):
- **email**: Accept info@, contact@, sales@, hello@ — ALL are valid cold outreach targets.
  Look in: footer, header, contact page, about page, mailto: links.
  ONLY skip: noreply@, donotreply@, mailer-daemon@
- **contact_name**: Look in About Us, Team, Staff, Contact, History pages, bios, email signatures.
  If no titled position found, extract best guess (family name, founder mention, any named person).

IMPORTANT RULES:
- Return ONLY the JSON object, no markdown formatting
- Use true/false for booleans (not strings)
- Use null for unknown/missing values (not empty string)
- For arrays, use [] if empty
- If they are ONLY a dispensary with no cultivation, set dispensary_only=true and business_type="dispensary"
- If they grow AND dispense, set dispensary_only=false and business_type="mixed"
- cultivation_type should reflect their PRIMARY method; use "mixed" if they clearly do multiple
- indoor_sqft and canopy_sqft are different: indoor_sqft = total facility footprint; canopy_sqft = licensed plant canopy area

Now analyze the cannabis business above and return the JSON:"""


def build_hemp_prompt(website_text, business_name='', city='', state=''):
    """
    Build a hemp producer enrichment prompt.

    Extracts ICP signals specific to hemp farming operations.
    Hemp growers use field terminology: 'acres', 'harvest', 'CBD', 'fiber', 'seed',
    'cover crop', 'rotation' — very different from nursery or cannabis language.

    Field mapping to existing DB columns:
      hemp_type         → crops_grown (stored as list, e.g. ['hemp_CBD', 'hemp_fiber'])
      acreage           → acreage (existing column)
      uses_amendments   → uses_growing_media
      organic_certified → is_organic_certified

    Args:
        website_text: Extracted text from hemp business website
        business_name: Name of the business (optional)
        city: City location (optional)
        state: State location (optional)

    Returns:
        str: Prompt string to send to Gemini
    """
    business_context = ''
    if business_name:
        business_context += f'\nBusiness Name: {business_name}'
    if city and state:
        business_context += f'\nLocation: {city}, {state}'

    return f"""You are analyzing a hemp business website to determine if they are a potential buyer of bulk worm castings (vermicompost) for use as a field soil amendment in hemp production.

Sweet Leaf Soil sells premium worm castings that hemp producers use to:
- Amend soil between crop cycles to restore microbial life
- Apply as a top dressing around hemp plants
- Improve soil tilth and water retention on sandy or compacted ground
- Transition toward organic or regenerative practices{business_context}

Website Content:
{website_text[:15000]}

EXTRACTION FOCUS — Hemp Producer ICP Signals:

1. HEMP TYPE (Determines amendment need and buying window)
   - CBD / Flower: high-value crop, usually small acreage, best organic inputs → HIGH value
   - Fiber: large acreage, commodity crop, lower margin → MEDIUM value
   - Seed / Grain: food hemp, dual-purpose → MEDIUM value
   - Dual-purpose: fiber + CBD, or grain + fiber → MEDIUM-HIGH value
   - If type is unclear but they clearly grow hemp, mark as "mixed"

2. ACREAGE (Volume signal — larger = more amendments needed)
   - Look for: "200 acres of hemp", "planted 50 acres", "our farm is 1,000 acres"
   - Fractional/small acreage (< 10 acres) = test buyer; larger = commercial buyer
   - If no acreage mentioned, extract farm size if available

3. PROCESSING & VALUE ADD (Signals sophistication and premium practices)
   - Do they process on-site? (extraction, drying, decorticating, baling)
   - On-site processing = more invested in quality → more likely to buy premium inputs

4. AMENDMENT & ORGANIC SIGNALS (Direct buying signal)
   - Do they mention soil health, amendments, compost, organic matter?
   - Cover cropping, crop rotation, no-till = regenerative practices → HIGH signal
   - "USDA Organic certified" or state organic cert = premium buyer
   - Any explicit mention of worm castings / vermicompost = VERY HIGH priority

5. BUSINESS TYPE (Qualifier)
   - hemp_grower: farms hemp (primary target)
   - hemp_processor: buys raw hemp and processes it, does not grow → qualify only if also grows
   - hemp_retailer: sells hemp products (CBD store, etc.) — no grow operation → DISQUALIFY
   - If they grow AND process, use hemp_grower

6. DISQUALIFICATION SIGNALS
   - Retail CBD store with no farm: no soil needs
   - Hemp consulting / software / compliance company
   - Processor-only with no grow operations

Extract and return ONLY a valid JSON object (no markdown, no explanation):

{{
  "business_type": "hemp_grower / hemp_processor / hemp_retailer / mixed / unknown",
  "hemp_type": "fiber / CBD / seed / grain / dual-purpose / mixed / unknown (primary hemp crop type)",
  "acreage": "Number of acres under hemp cultivation (float), or null if not mentioned",
  "processing_on_site": true/false (Do they process hemp on site — extraction, drying, baling, decorticating?),
  "uses_amendments": true/false (Do they mention soil amendments, compost, organic matter, cover crops?),
  "organic_certified": true/false (USDA Organic, state cert, or explicitly stated organic practices?),
  "market_channel": "wholesale / retail / both / unknown (How do they sell their hemp/products?)",
  "multiple_locations": true/false (Multiple farm locations or facilities?),
  "crops_grown": ["hemp — include specific type like 'hemp_CBD', 'hemp_fiber', 'hemp_grain' if known"],
  "scale_indicators": ["Array of specific scale quotes: '200 acres', '50,000 lb harvest', 'family farm since 1985'"],
  "disqualification_signals": ["Array of red flags: 'retail CBD store', 'no grow operation', 'processor only'"],
  "contact_name": "REQUIRED: Full name of ANY relevant contact. Priority: 1) Owner/Founder, 2) Farm Manager, 3) Operations Manager, 4) Head Grower, 5) Any named person. Return first match found, or null.",
  "contact_title": "The role/title of contact_name, or 'No role found' if name found without title, or null",
  "email": "ANY contact email found on the site — info@, contact@, hello@, sales@ are ALL VALID. Only skip noreply@/donotreply@. Return the best one found, or null.",
  "confidence": "low / medium / high (confidence in extracted data)"
}}

IMPORTANT - CONTACT & EMAIL EXTRACTION (AGGRESSIVE MODE):
- **email**: Extract ANY email address found anywhere. info@domain.com IS VALID — return it.
  Priority: 1) Named person's email, 2) info@/contact@/hello@/sales@, 3) Any other email.
  Look in: footer, header, contact page text, about page, mailto: links.
  ONLY skip: noreply@, donotreply@, mailer-daemon@

- **contact_name**: Use 2-phase approach:

PHASE 1 - Search for TITLED positions (Priority 1-5):
  1. Owner/Founder/President (look for: "Owner", "Founder", "President", "Proprietor")
  2. Farm Manager (look for: "Farm Manager", "Ranch Manager", "General Manager")
  3. Operations Manager (look for: "Operations Manager", "Production Manager")
  4. Head Grower (look for: "Head Grower", "Lead Grower", "Master Grower")
  5. Sales/Marketing (look for: "Sales Manager", "Marketing", "Business Development")

PHASE 2 - If NO titled position found, extract BEST GUESS name:
  - Look for: Family names in "About Us", names in team/founder sections
  - Context clues: "Started by John Smith", "The Smith Family Farm", "Meet the Farmers"
  - Names linked to the business ("Smith Hemp Farm" → Smith is likely owner)
  - Email signatures, contact forms with names
  - ALWAYS extract a name if ANY person is mentioned — even without title
  - Require FULL name (first + last)

Look in: About Us, Our Story, Team, Staff, Contact, History pages, footer, bios

OTHER RULES:
- Return ONLY the JSON object, no markdown formatting
- Use true/false for booleans (not strings)
- Use null for unknown/missing values (not empty string)
- For arrays, use [] if empty
- hemp_type should reflect their PRIMARY crop type; use "dual-purpose" or "mixed" if they clearly do multiple
- acreage should be a number (e.g., 200 not "200 acres") — extract the number only
- hemp_retailer with no grow operation = disqualify (no soil needs)

Now analyze the hemp business above and return the JSON:"""


def _normalize_cannabis_response(data):
    """
    Map cannabis prompt response fields to existing DB column names.

    This ensures the response from the cannabis prompt is compatible with
    the existing leads table schema without requiring any schema changes.

    Mapping:
      cultivation_type  → production_method
      indoor_sqft       → greenhouse_sqft  (if canopy_sqft is null)
      canopy_sqft       → greenhouse_sqft  (preferred; indoor_sqft as fallback)
      uses_amendments   → uses_growing_media
      dispensary_only   → negative_indicators.dispensary_only
      organic_certified → is_organic_certified

    Args:
        data: Raw dict from Gemini cannabis response

    Returns:
        dict: Normalized dict with existing column names
    """
    normalized = dict(data)

    # cultivation_type → production_method
    if 'cultivation_type' in normalized:
        normalized['production_method'] = normalized.pop('cultivation_type')

    # canopy_sqft / indoor_sqft → greenhouse_sqft (canopy_sqft preferred)
    canopy = normalized.pop('canopy_sqft', None)
    indoor = normalized.pop('indoor_sqft', None)
    if canopy is not None:
        normalized['greenhouse_sqft'] = canopy
    elif indoor is not None:
        normalized['greenhouse_sqft'] = indoor

    # uses_amendments → uses_growing_media
    if 'uses_amendments' in normalized:
        normalized['uses_growing_media'] = normalized.pop('uses_amendments')

    # organic_certified → is_organic_certified
    if 'organic_certified' in normalized:
        normalized['is_organic_certified'] = normalized.pop('organic_certified')

    # dispensary_only → negative_indicators.dispensary_only (JSON dict)
    dispensary_only = normalized.pop('dispensary_only', None)
    if dispensary_only is not None:
        neg_indicators = normalized.get('negative_indicators', {}) or {}
        if not isinstance(neg_indicators, dict):
            neg_indicators = {}
        neg_indicators['dispensary_only'] = dispensary_only
        normalized['negative_indicators'] = neg_indicators

    # Ensure standard nursery-compatible fields exist with sensible defaults
    if 'is_wholesale' not in normalized:
        normalized['is_wholesale'] = False
    if 'is_retail' not in normalized:
        normalized['is_retail'] = False
    if 'container_production' not in normalized:
        # Cannabis cultivators use containers — default true if indoor/greenhouse
        pm = normalized.get('production_method', '')
        normalized['container_production'] = pm in ('indoor', 'greenhouse', 'mixed')
    if 'soil_relevance' not in normalized:
        normalized['soil_relevance'] = True  # Cannabis cultivators always relevant
    if 'size_signals' not in normalized:
        normalized['size_signals'] = []
    if 'organic_focus' not in normalized:
        normalized['organic_focus'] = normalized.get('is_organic_certified', False) or False
    if 'multiple_locations' not in normalized:
        normalized['multiple_locations'] = False
    if 'appointment_only' not in normalized:
        normalized['appointment_only'] = False
    if 'closed_weekends' not in normalized:
        normalized['closed_weekends'] = False
    if 'purchases_soil' not in normalized:
        normalized['purchases_soil'] = normalized.get('uses_growing_media', False) or False
    if 'soil_brands_mentioned' not in normalized:
        normalized['soil_brands_mentioned'] = []

    # Ensure arrays
    for field in ['crops_grown', 'scale_indicators', 'size_signals',
                  'disqualification_signals', 'soil_brands_mentioned']:
        if field not in normalized or normalized[field] is None:
            normalized[field] = []

    # Ensure negative_indicators is a dict
    if not isinstance(normalized.get('negative_indicators'), dict):
        normalized['negative_indicators'] = {}

    return normalized


def _normalize_hemp_response(data):
    """
    Map hemp prompt response fields to existing DB column names.

    Mapping:
      hemp_type         → prepended to crops_grown list (e.g., 'hemp_CBD')
      acreage           → acreage (already a column)
      uses_amendments   → uses_growing_media
      organic_certified → is_organic_certified
      processing_on_site→ stored in negative_indicators (positive signal, not a disqualifier)

    Args:
        data: Raw dict from Gemini hemp response

    Returns:
        dict: Normalized dict with existing column names
    """
    normalized = dict(data)

    # hemp_type → prepend to crops_grown with 'hemp_' prefix for clarity
    hemp_type = normalized.pop('hemp_type', None)
    crops_grown = normalized.get('crops_grown', []) or []
    if hemp_type and hemp_type not in ('unknown', 'mixed'):
        typed_crop = f'hemp_{hemp_type}' if not hemp_type.startswith('hemp') else hemp_type
        if typed_crop not in crops_grown:
            crops_grown = [typed_crop] + [c for c in crops_grown if c != typed_crop]
    elif 'hemp' not in crops_grown:
        crops_grown = ['hemp'] + crops_grown
    normalized['crops_grown'] = crops_grown

    # acreage stays as acreage (existing column)
    # Nothing to map — already correct field name

    # uses_amendments → uses_growing_media
    if 'uses_amendments' in normalized:
        normalized['uses_growing_media'] = normalized.pop('uses_amendments')

    # organic_certified → is_organic_certified
    if 'organic_certified' in normalized:
        normalized['is_organic_certified'] = normalized.pop('organic_certified')

    # processing_on_site → stored in negative_indicators for now (not a disqualifier, just context)
    processing_on_site = normalized.pop('processing_on_site', None)
    if processing_on_site is not None:
        neg_indicators = normalized.get('negative_indicators', {}) or {}
        if not isinstance(neg_indicators, dict):
            neg_indicators = {}
        neg_indicators['processing_on_site'] = processing_on_site
        normalized['negative_indicators'] = neg_indicators

    # Hemp producers are field-grown by default
    if 'production_method' not in normalized:
        normalized['production_method'] = 'field'

    # Ensure standard nursery-compatible fields exist with sensible defaults
    if 'is_wholesale' not in normalized:
        mc = normalized.get('market_channel', '')
        normalized['is_wholesale'] = mc in ('wholesale', 'both')
    if 'is_retail' not in normalized:
        mc = normalized.get('market_channel', '')
        normalized['is_retail'] = mc in ('retail', 'both')
    if 'container_production' not in normalized:
        normalized['container_production'] = False  # Hemp is field-grown
    if 'soil_relevance' not in normalized:
        normalized['soil_relevance'] = True
    if 'size_signals' not in normalized:
        normalized['size_signals'] = []
    if 'organic_focus' not in normalized:
        normalized['organic_focus'] = normalized.get('is_organic_certified', False) or False
    if 'multiple_locations' not in normalized:
        normalized['multiple_locations'] = False
    if 'appointment_only' not in normalized:
        normalized['appointment_only'] = False
    if 'closed_weekends' not in normalized:
        normalized['closed_weekends'] = False
    if 'purchases_soil' not in normalized:
        normalized['purchases_soil'] = normalized.get('uses_growing_media', False) or False
    if 'soil_brands_mentioned' not in normalized:
        normalized['soil_brands_mentioned'] = []

    # Ensure arrays
    for field in ['crops_grown', 'scale_indicators', 'size_signals',
                  'disqualification_signals', 'soil_brands_mentioned']:
        if field not in normalized or normalized[field] is None:
            normalized[field] = []

    # Ensure negative_indicators is a dict
    if not isinstance(normalized.get('negative_indicators'), dict):
        normalized['negative_indicators'] = {}

    return normalized


def enrich_lead_with_gemini(website_text, business_name, city, state, segment='nursery'):
    """
    Enrich a lead using Gemini to analyze website content.

    Routes to the appropriate segment-specific prompt builder based on the
    lead's segment. Defaults to the nursery prompt for unknown segments.

    Args:
        website_text: Extracted text from website
        business_name: Name of the business
        city: City location
        state: State location
        segment: Lead segment — 'nursery' (default), 'cannabis_grower', or 'hemp_producer'

    Returns:
        dict: Enriched data extracted from website, fields normalized to existing column names

    Raises:
        Exception: If API call fails or data is invalid
    """

    # Validate input
    if not website_text or len(website_text) < 100:
        raise ValueError("Insufficient website text for analysis")

    # Normalize segment values (DB uses 'hemp'/'cannabis', code uses full names)
    segment_map = {'hemp': 'hemp_producer', 'cannabis': 'cannabis_grower'}
    segment = segment_map.get(segment, segment)

    # --- Route to segment-appropriate prompt builder ---
    if segment == 'cannabis_grower':
        prompt = build_cannabis_prompt(website_text, business_name, city, state)
    elif segment == 'hemp_producer':
        prompt = build_hemp_prompt(website_text, business_name, city, state)
    else:
        # Default: nursery prompt (unchanged)
        prompt = build_nursery_prompt(website_text, business_name, city, state)

    # Call Gemini
    try:
        data = call_gemini(prompt)

        # --- Segment-specific validation and field normalization ---
        if segment == 'cannabis_grower':
            # Validate cannabis-specific required fields
            cannabis_required = ['business_type', 'cultivation_type', 'uses_amendments',
                                 'dispensary_only', 'confidence']
            for field in cannabis_required:
                if field not in data:
                    raise ValueError(f"Cannabis prompt missing required field: {field}")

            # Ensure cannabis arrays
            for arr_field in ['crops_grown', 'scale_indicators', 'disqualification_signals']:
                if arr_field not in data or data[arr_field] is None:
                    data[arr_field] = []

            # Normalize cannabis fields → existing column names
            data = _normalize_cannabis_response(data)

        elif segment == 'hemp_producer':
            # Validate hemp-specific required fields
            hemp_required = ['business_type', 'hemp_type', 'uses_amendments',
                             'organic_certified', 'confidence']
            for field in hemp_required:
                if field not in data:
                    raise ValueError(f"Hemp prompt missing required field: {field}")

            # Ensure hemp arrays
            for arr_field in ['crops_grown', 'scale_indicators', 'disqualification_signals']:
                if arr_field not in data or data[arr_field] is None:
                    data[arr_field] = []

            # Normalize hemp fields → existing column names
            data = _normalize_hemp_response(data)

        else:
            # Nursery: existing validation (unchanged)
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

        # Regex fallback: if Gemini missed the email, scan raw text directly
        if not data.get('email') and website_text:
            skip_prefixes = ('noreply', 'donotreply', 'no-reply', 'mailer-daemon', 'bounce')
            found_emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', website_text)
            found_emails = [e for e in found_emails if not any(e.lower().startswith(p) for p in skip_prefixes)]
            if found_emails:
                data['email'] = found_emails[0]
                data['email_source'] = 'regex_fallback'

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
