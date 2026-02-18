import sqlite3
from datetime import datetime
import os

DB_PATH = 'data/leads.db'

def get_db_connection():
    """Create and return a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize the database with required tables."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Create leads table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            address TEXT,
            city TEXT,
            state TEXT,
            zip TEXT,
            phone TEXT,
            website TEXT,
            source_file TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'new'
        )
    ''')

    # Create processing_log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processing_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads (id)
        )
    ''')

    # Create exports table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            format TEXT NOT NULL,
            tier_filter TEXT,
            record_count INTEGER NOT NULL,
            include_metadata BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create index for faster duplicate checking
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_business_city
        ON leads(business_name, city)
    ''')

    conn.commit()
    conn.close()
    print("Database initialized successfully")

    # Run migrations
    migrate_db()

def migrate_db():
    """Run database migrations to add new columns."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("PRAGMA table_info(leads)")
    columns = [row[1] for row in cursor.fetchall()]

    # Add enrichment columns if they don't exist
    new_columns = [
        ('rating', 'REAL'),
        ('review_count', 'INTEGER'),
        ('place_id', 'TEXT'),
        ('google_maps_url', 'TEXT'),
        ('hours', 'TEXT'),
        ('enrichment_status', 'TEXT DEFAULT "pending"'),
        ('enriched_at', 'TIMESTAMP'),
        ('website_text', 'TEXT'),
        ('scrape_status', 'TEXT DEFAULT "pending"'),
        ('scrape_error', 'TEXT'),
        ('scraped_at', 'TIMESTAMP'),
        # Gemini AI enrichment columns
        ('owner_name', 'TEXT'),
        ('owner_email', 'TEXT'),
        ('business_type', 'TEXT'),
        ('is_wholesale', 'BOOLEAN'),
        ('is_retail', 'BOOLEAN'),
        ('greenhouse_sqft', 'INTEGER'),
        ('acreage', 'REAL'),
        ('multiple_locations', 'BOOLEAN'),
        ('container_production', 'BOOLEAN'),
        ('soil_relevance', 'BOOLEAN'),
        ('organic_focus', 'BOOLEAN'),
        ('crops_grown', 'TEXT'),  # JSON array
        ('size_signals', 'TEXT'),  # JSON array
        ('negative_indicators', 'TEXT'),  # JSON object
        ('appointment_only', 'BOOLEAN'),
        ('gemini_confidence', 'TEXT'),
        ('gemini_raw_response', 'TEXT'),
        ('gemini_enriched_at', 'TIMESTAMP'),
        ('gemini_status', 'TEXT DEFAULT "pending"'),
        ('gemini_error', 'TEXT'),
        # Scoring columns
        ('score', 'INTEGER'),
        ('score_breakdown', 'TEXT'),  # JSON with signals
        ('tier', 'TEXT'),  # A/B/C/U
        ('scored_at', 'TIMESTAMP'),
        # Review columns
        ('tier_override', 'TEXT'),  # Manual tier override
        ('review_notes', 'TEXT'),  # Free text notes
        ('reviewed_at', 'TIMESTAMP'),
        ('reviewed_by', 'TEXT'),  # For future multi-user
        # Personalization columns
        ('custom_line', 'TEXT'),  # Generated first line for email
        ('email_angle', 'TEXT'),  # organic/wholesale/cannabis/etc
        ('personalization_status', 'TEXT DEFAULT "pending"'),  # pending/generated/failed
        ('personalization_generated_at', 'TIMESTAMP'),
        # Phase 1: ICP-specific enrichment columns
        ('uses_growing_media', 'BOOLEAN DEFAULT NULL'),  # Core ICP signal
        ('production_method', 'TEXT DEFAULT NULL'),  # field/container/greenhouse/hydroponic/mixed
        ('is_organic_certified', 'BOOLEAN DEFAULT NULL'),  # Organic certification detected
        ('scale_indicators', 'TEXT DEFAULT NULL'),  # JSON array: ["12 greenhouses", "40 acres"]
        ('purchases_soil', 'BOOLEAN DEFAULT NULL'),  # Explicit mention of buying potting mix
        ('soil_brands_mentioned', 'TEXT DEFAULT NULL'),  # JSON array: ["Pro-Mix", "Sungro"]
        ('disqualification_signals', 'TEXT DEFAULT NULL'),  # JSON array: ["landscaping", "lawn care"]
        ('geo_score', 'INTEGER DEFAULT 0'),  # Geographic proximity score
        ('icp_qualified', 'BOOLEAN DEFAULT NULL'),  # Passed ICP qualification gate
        ('icp_type', 'TEXT DEFAULT NULL'),  # primary/secondary/tertiary/disqualified
        # Phase 5: Re-enrichment tracking columns
        ('re_enrichment_status', 'TEXT DEFAULT "pending"'),  # pending/completed/failed/skipped
        ('re_enriched_at', 'TIMESTAMP DEFAULT NULL'),  # When re-enrichment completed
        ('rescored_at', 'TIMESTAMP DEFAULT NULL'),  # When rescored with new model
        # Phase 10: Email Hunter columns
        ('email_verification', 'TEXT DEFAULT NULL'),  # valid/invalid/risky/catch_all/unknown
        ('email_confidence', 'INTEGER DEFAULT NULL'),  # 0-100 confidence score
        ('email_found_at', 'TIMESTAMP DEFAULT NULL'),  # When email was discovered
        ('domain_is_catchall', 'BOOLEAN DEFAULT NULL'),  # Domain accepts all emails
        ('email_pattern', 'TEXT DEFAULT NULL'),  # Detected pattern: first.last, first, flast, etc.
        ('email_hunter_status', 'TEXT DEFAULT "pending"'),  # pending/completed/failed/skipped
        ('email_hunter_error', 'TEXT DEFAULT NULL'),  # Error message if failed
        ('contact_email', 'TEXT DEFAULT NULL'),  # Secondary contact (sales manager, etc.)
        ('generic_email', 'TEXT DEFAULT NULL'),  # Fallback: info@, contact@, sales@
        ('contact_form_url', 'TEXT DEFAULT NULL'),  # Last resort: web form URL
        # Phase 11: OMRI Soil Mixer Integration columns
        ('data_source', 'TEXT DEFAULT NULL'),  # omri/google_places/manual/import
        ('omri_code', 'TEXT DEFAULT NULL'),  # OMRI manufacturer code (e.g., "fox", "tom")
        ('omri_url', 'TEXT DEFAULT NULL'),  # Full OMRI profile URL
        ('omri_listing_date', 'TEXT DEFAULT NULL'),  # When first listed on OMRI
        ('omri_expiration', 'TEXT DEFAULT NULL'),  # OMRI certification expiration
        ('omri_product_count', 'INTEGER DEFAULT NULL'),  # Number of OMRI-listed products
        ('omri_categories', 'TEXT DEFAULT NULL'),  # JSON array: ["Potting Soil", "Transplant Media"]
        ('soil_mixer_tier', 'TEXT DEFAULT NULL'),  # tier_1 (craft) / tier_2 (commodity)
        ('soil_mixer_signals', 'TEXT DEFAULT NULL'),  # JSON: keywords, size indicators, etc.
        ('uses_worm_castings', 'BOOLEAN DEFAULT NULL'),  # Already uses vermicompost
        ('worm_castings_potential', 'TEXT DEFAULT NULL'),  # high/medium/low
        ('estimated_volume', 'TEXT DEFAULT NULL'),  # Small/Medium/Large/Enterprise
        ('primary_market', 'TEXT DEFAULT NULL'),  # retail/wholesale/professional/cannabis
        # Phase 12: Email Discovery Rebuild columns
        ('places_email', 'TEXT DEFAULT NULL'),      # Email directly from Google Places API
        ('email_source', 'TEXT DEFAULT NULL'),      # Layer that found the email: places/website_scrape/contact_page/pattern/generic/web_search/hunter_io/snov_io
        ('email_verified', 'BOOLEAN DEFAULT NULL'), # Whether email passed verification
        ('email_verification_result', 'TEXT DEFAULT NULL'),  # JSON: {status, sub_status, provider, confidence}
        ('email_hunt_attempted', 'BOOLEAN DEFAULT 0'),       # True once new system has run on this lead
        ('contact_page_text', 'TEXT DEFAULT NULL'),          # Raw text from /contact page scrape
        ('email_method', 'TEXT DEFAULT NULL'),               # Alias kept for backward compat (same as email_source)
    ]

    migrations_applied = False
    for column_name, column_type in new_columns:
        if column_name not in columns:
            try:
                cursor.execute(f'ALTER TABLE leads ADD COLUMN {column_name} {column_type}')
                print(f"Added column: {column_name}")
                migrations_applied = True
            except sqlite3.OperationalError as e:
                print(f"Migration warning for {column_name}: {e}")

    if migrations_applied:
        print("Database migrations completed")

    # Phase 9: Create pipeline_runs table for reliability tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_type TEXT NOT NULL,
            status TEXT DEFAULT 'running',
            total_leads INTEGER DEFAULT 0,
            completed_leads INTEGER DEFAULT 0,
            failed_leads INTEGER DEFAULT 0,
            current_lead_id INTEGER,
            error_log TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            config TEXT
        )
    """)
    print("Pipeline runs table created (Phase 9)")

    # Phase 10: Email Hunter tables
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            source TEXT NOT NULL,
            pattern_type TEXT,
            verification_status TEXT,
            verification_date TIMESTAMP,
            confidence INTEGER,
            selected BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS domain_patterns (
            domain TEXT PRIMARY KEY,
            detected_pattern TEXT,
            is_catchall BOOLEAN,
            sample_emails TEXT,
            checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_candidates_lead
        ON email_candidates(lead_id)
    """)
    
    print("Email Hunter tables created (Phase 10)")

    # Phase 0 (Registry Architecture): Add segment and registry_id to leads
    cursor.execute("PRAGMA table_info(leads)")
    lead_cols = [row[1] for row in cursor.fetchall()]

    if 'segment' not in lead_cols:
        try:
            cursor.execute("ALTER TABLE leads ADD COLUMN segment TEXT DEFAULT 'nursery'")
            print("Added column: segment")
        except sqlite3.OperationalError as e:
            print(f"Migration warning for segment: {e}")

    if 'registry_id' not in lead_cols:
        try:
            cursor.execute("ALTER TABLE leads ADD COLUMN registry_id INTEGER DEFAULT NULL")
            print("Added column: registry_id")
        except sqlite3.OperationalError as e:
            print(f"Migration warning for registry_id: {e}")

    # Backfill: ensure all existing leads have segment = 'nursery'
    cursor.execute("UPDATE leads SET segment = 'nursery' WHERE segment IS NULL")

    # Indexes for new columns
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_segment ON leads(segment)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_leads_registry_id ON leads(registry_id)")

    # Phase 0: Create registries table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS registries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            business_name TEXT NOT NULL,
            license_number TEXT,
            license_type TEXT,
            license_status TEXT,
            address TEXT,
            city TEXT,
            state TEXT NOT NULL,
            zip TEXT,
            county TEXT,
            phone TEXT,
            website TEXT,
            contact_name TEXT,
            contact_email TEXT,
            registry_source TEXT NOT NULL,
            segment TEXT NOT NULL,
            promoted_at TIMESTAMP,
            lead_id INTEGER,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            raw_data TEXT,
            UNIQUE(license_number, registry_source),
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_registries_state ON registries(state)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_registries_segment ON registries(segment)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_registries_promoted ON registries(promoted_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_registries_source ON registries(registry_source)")
    print("Registries table created (Phase 0)")

    conn.commit()
    conn.close()

def insert_lead(business_name, address, city, state, zip_code, source_file, phone=None, website=None):
    """
    Insert a new lead into the database.
    Returns (lead_id, created) where created is True if new, False if duplicate.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check for duplicate
    cursor.execute('''
        SELECT id FROM leads
        WHERE business_name = ? AND city = ?
    ''', (business_name, city))

    existing = cursor.fetchone()

    if existing:
        conn.close()
        return (existing['id'], False)

    # Insert new lead
    cursor.execute('''
        INSERT INTO leads (business_name, address, city, state, zip, phone, website, source_file)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (business_name, address, city, state, zip_code, phone, website, source_file))

    lead_id = cursor.lastrowid

    # Log the import
    log_action(lead_id, 'imported', f'Imported from {source_file}', cursor)

    conn.commit()
    conn.close()

    return (lead_id, True)

def log_action(lead_id, action, details, cursor=None):
    """Log an action for a lead."""
    if cursor is None:
        conn = get_db_connection()
        cursor = conn.cursor()
        should_commit = True
    else:
        should_commit = False

    cursor.execute('''
        INSERT INTO processing_log (lead_id, action, details)
        VALUES (?, ?, ?)
    ''', (lead_id, action, details))

    if should_commit:
        conn.commit()
        conn.close()

def get_all_leads():
    """Get all leads from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM leads
        ORDER BY imported_at DESC
    ''')
    leads = cursor.fetchall()
    conn.close()
    return leads

def get_lead_by_id(lead_id):
    """Get a specific lead by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM leads WHERE id = ?', (lead_id,))
    lead = cursor.fetchone()
    conn.close()
    return lead

def get_processing_log(lead_id):
    """Get processing log for a specific lead."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM processing_log
        WHERE lead_id = ?
        ORDER BY timestamp DESC
    ''', (lead_id,))
    logs = cursor.fetchall()
    conn.close()
    return logs

def update_lead_status(lead_id, status):
    """Update the status of a lead."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE leads
        SET status = ?
        WHERE id = ?
    ''', (status, lead_id))
    conn.commit()
    conn.close()

def update_enriched_data(lead_id, enriched_data):
    """
    Update a lead with enriched data from Google Places API.
    enriched_data should be a dictionary with keys: phone, website, rating, review_count,
    place_id, google_maps_url, hours, enrichment_status
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Build UPDATE query dynamically based on provided data
    update_fields = []
    values = []

    if 'phone' in enriched_data and enriched_data['phone']:
        update_fields.append('phone = ?')
        values.append(enriched_data['phone'])

    if 'website' in enriched_data and enriched_data['website']:
        update_fields.append('website = ?')
        values.append(enriched_data['website'])

    if 'rating' in enriched_data and enriched_data['rating']:
        update_fields.append('rating = ?')
        values.append(enriched_data['rating'])

    if 'review_count' in enriched_data and enriched_data['review_count']:
        update_fields.append('review_count = ?')
        values.append(enriched_data['review_count'])

    if 'place_id' in enriched_data and enriched_data['place_id']:
        update_fields.append('place_id = ?')
        values.append(enriched_data['place_id'])

    if 'google_maps_url' in enriched_data and enriched_data['google_maps_url']:
        update_fields.append('google_maps_url = ?')
        values.append(enriched_data['google_maps_url'])

    if 'hours' in enriched_data and enriched_data['hours']:
        update_fields.append('hours = ?')
        values.append(enriched_data['hours'])

    # Always update enrichment status and timestamp
    update_fields.append('enrichment_status = ?')
    values.append(enriched_data.get('enrichment_status', 'enriched'))

    update_fields.append('enriched_at = CURRENT_TIMESTAMP')

    # Add lead_id for WHERE clause
    values.append(lead_id)

    query = f"UPDATE leads SET {', '.join(update_fields)} WHERE id = ?"
    cursor.execute(query, values)

    conn.commit()
    conn.close()

def get_leads_by_enrichment_status(status):
    """Get all leads with a specific enrichment status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM leads
        WHERE enrichment_status = ?
        ORDER BY imported_at DESC
    ''', (status,))
    leads = cursor.fetchall()
    conn.close()
    return leads

def update_scrape_data(lead_id, website_text, scrape_status, scrape_error=None):
    """
    Update a lead with scraped website data.

    Args:
        lead_id: The lead ID
        website_text: The scraped text content (or None if failed)
        scrape_status: 'scraped', 'failed', or 'skipped'
        scrape_error: Error message if scrape failed
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE leads
        SET website_text = ?,
            scrape_status = ?,
            scrape_error = ?,
            scraped_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (website_text, scrape_status, scrape_error, lead_id))

    conn.commit()
    conn.close()

def get_leads_by_scrape_status(status):
    """Get all leads with a specific scrape status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM leads
        WHERE scrape_status = ?
        ORDER BY imported_at DESC
    ''', (status,))
    leads = cursor.fetchall()
    conn.close()
    return leads

def get_leads_with_website():
    """Get all leads that have a website URL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM leads
        WHERE website IS NOT NULL AND website != ''
        ORDER BY imported_at DESC
    ''')
    leads = cursor.fetchall()
    conn.close()
    return leads

def update_gemini_data(lead_id, gemini_data, raw_response=None):
    """
    Update a lead with Gemini AI enrichment data.

    Args:
        lead_id: The lead ID
        gemini_data: Dictionary with extracted fields from Gemini
        raw_response: Full JSON response from Gemini for debugging
    """
    import json

    conn = get_db_connection()
    cursor = conn.cursor()

    # Convert arrays and objects to JSON strings
    crops_grown_json = json.dumps(gemini_data.get('crops_grown', []))
    size_signals_json = json.dumps(gemini_data.get('size_signals', []))
    negative_indicators_json = json.dumps(gemini_data.get('negative_indicators', {}))
    raw_response_json = json.dumps(raw_response) if raw_response else json.dumps(gemini_data)

    # Phase 2: New ICP field JSON arrays
    scale_indicators_json = json.dumps(gemini_data.get('scale_indicators', []))
    soil_brands_mentioned_json = json.dumps(gemini_data.get('soil_brands_mentioned', []))
    disqualification_signals_json = json.dumps(gemini_data.get('disqualification_signals', []))

    cursor.execute('''
        UPDATE leads
        SET owner_name = ?,
            owner_email = ?,
            business_type = ?,
            is_wholesale = ?,
            is_retail = ?,
            greenhouse_sqft = ?,
            acreage = ?,
            multiple_locations = ?,
            container_production = ?,
            soil_relevance = ?,
            organic_focus = ?,
            crops_grown = ?,
            size_signals = ?,
            negative_indicators = ?,
            appointment_only = ?,
            gemini_confidence = ?,
            gemini_raw_response = ?,
            gemini_enriched_at = CURRENT_TIMESTAMP,
            gemini_status = 'enriched',
            gemini_error = NULL,
            uses_growing_media = ?,
            production_method = ?,
            is_organic_certified = ?,
            scale_indicators = ?,
            purchases_soil = ?,
            soil_brands_mentioned = ?,
            disqualification_signals = ?
        WHERE id = ?
    ''', (
        gemini_data.get('owner_name'),
        gemini_data.get('email'),
        gemini_data.get('business_type'),
        gemini_data.get('is_wholesale'),
        gemini_data.get('is_retail'),
        gemini_data.get('greenhouse_sqft'),
        gemini_data.get('acreage'),
        gemini_data.get('multiple_locations'),
        gemini_data.get('container_production'),
        gemini_data.get('soil_relevance'),
        gemini_data.get('organic_focus'),
        crops_grown_json,
        size_signals_json,
        negative_indicators_json,
        gemini_data.get('appointment_only'),
        gemini_data.get('confidence'),
        raw_response_json,
        # Phase 2: New ICP fields
        gemini_data.get('uses_growing_media'),
        gemini_data.get('production_method'),
        gemini_data.get('is_organic_certified'),
        scale_indicators_json,
        gemini_data.get('purchases_soil'),
        soil_brands_mentioned_json,
        disqualification_signals_json,
        lead_id
    ))

    conn.commit()
    conn.close()

def update_gemini_error(lead_id, error_message):
    """Mark a lead as failed during Gemini enrichment."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE leads
        SET gemini_status = 'failed',
            gemini_error = ?,
            gemini_enriched_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (error_message, lead_id))

    conn.commit()
    conn.close()

def get_leads_for_gemini_enrichment(limit=None):
    """
    Get leads that are ready for Gemini enrichment.
    Returns leads where scrape_status = 'scraped' AND gemini_status = 'pending'.

    Args:
        limit: Maximum number of leads to return (None = all leads)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        SELECT * FROM leads
        WHERE scrape_status = 'scraped'
          AND (gemini_status = 'pending' OR gemini_status IS NULL)
        ORDER BY imported_at DESC
    '''

    if limit is not None:
        query += f' LIMIT {int(limit)}'

    cursor.execute(query)
    leads = cursor.fetchall()
    conn.close()
    return leads

def get_leads_by_gemini_status(status):
    """Get all leads with a specific Gemini enrichment status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM leads
        WHERE gemini_status = ?
        ORDER BY imported_at DESC
    ''', (status,))
    leads = cursor.fetchall()
    conn.close()
    return leads

def update_lead_score(lead_id, score_data):
    """
    Update a lead with score and tier.

    Args:
        lead_id: The lead ID
        score_data: Dict with keys: total, signals, tier, has_data, icp_qualified, icp_type, geo_score
    """
    import json

    conn = get_db_connection()
    cursor = conn.cursor()

    # Convert score breakdown to JSON
    breakdown = {
        'total': score_data['total'],
        'signals': score_data['signals'],
        'tier': score_data['tier'],
        'has_data': score_data['has_data']
    }
    breakdown_json = json.dumps(breakdown)

    cursor.execute('''
        UPDATE leads
        SET score = ?,
            score_breakdown = ?,
            tier = ?,
            icp_qualified = ?,
            icp_type = ?,
            geo_score = ?,
            scored_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        score_data['total'],
        breakdown_json,
        score_data['tier'],
        score_data.get('icp_qualified'),
        score_data.get('icp_type'),
        score_data.get('geo_score', 0),
        lead_id
    ))

    conn.commit()
    conn.close()

def get_leads_by_tier(tier):
    """Get all leads with a specific tier."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM leads
        WHERE tier = ?
        ORDER BY score DESC, business_name ASC
    ''', (tier,))
    leads = cursor.fetchall()
    conn.close()
    return leads

def get_tier_distribution():
    """
    Get the distribution of leads across tiers.

    Returns:
        dict with counts for each tier: {'A': 47, 'B': 234, 'C': 312, 'U': 85, 'total': 678}
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT tier, COUNT(*) as count
        FROM leads
        WHERE tier IS NOT NULL
        GROUP BY tier
    ''')

    results = cursor.fetchall()
    conn.close()

    distribution = {'A': 0, 'B': 0, 'C': 0, 'U': 0, 'total': 0}

    for row in results:
        tier = row['tier']
        count = row['count']
        distribution[tier] = count
        distribution['total'] += count

    return distribution

def get_leads_for_scoring(limit=None):
    """
    Get leads that should be scored.
    Returns all leads (scored and unscored).

    Args:
        limit: Maximum number of leads to return (None = all leads)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = '''
        SELECT * FROM leads
        ORDER BY imported_at DESC
    '''

    if limit is not None:
        query += f' LIMIT {int(limit)}'

    cursor.execute(query)
    leads = cursor.fetchall()
    conn.close()
    return leads

def update_lead_review(lead_id, tier_override=None, review_notes=None, reviewed_by=None):
    """
    Update lead review data (tier override, notes, reviewed status).

    Args:
        lead_id: The lead ID
        tier_override: Manual tier override (A/B/C/U) or None
        review_notes: Free text notes
        reviewed_by: Username/email of reviewer
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE leads
        SET tier_override = ?,
            review_notes = ?,
            reviewed_at = CURRENT_TIMESTAMP,
            reviewed_by = ?
        WHERE id = ?
    ''', (tier_override, review_notes, reviewed_by, lead_id))

    conn.commit()
    conn.close()

def get_leads_filtered(tier=None, state=None, business_type=None, min_score=None, max_score=None, search=None, sort_by='score', sort_order='DESC', limit=50, offset=0, segment=None):
    """
    Get leads with filters, sorting, and pagination.

    Args:
        tier: Filter by tier (A/B/C/U) or None for all
        state: Filter by state or None for all
        business_type: Filter by business_type or None for all
        min_score: Minimum score or None
        max_score: Maximum score or None
        search: Search term for business name or None
        sort_by: Column to sort by (default: score)
        sort_order: ASC or DESC (default: DESC)
        limit: Results per page (default: 50)
        offset: Results to skip (default: 0)

    Returns:
        tuple: (leads, total_count)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Build WHERE clause
    where_conditions = []
    params = []

    if tier:
        # Check tier_override first, fall back to calculated tier
        where_conditions.append('(COALESCE(tier_override, tier) = ?)')
        params.append(tier)

    if state:
        where_conditions.append('state = ?')
        params.append(state)

    if business_type:
        where_conditions.append('business_type = ?')
        params.append(business_type)

    if min_score is not None:
        where_conditions.append('score >= ?')
        params.append(min_score)

    if max_score is not None:
        where_conditions.append('score <= ?')
        params.append(max_score)

    if search:
        where_conditions.append('business_name LIKE ?')
        params.append(f'%{search}%')

    if segment:
        where_conditions.append('segment = ?')
        params.append(segment)

    where_clause = ' AND '.join(where_conditions) if where_conditions else '1=1'

    # Get total count
    count_query = f'SELECT COUNT(*) as count FROM leads WHERE {where_clause}'
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()['count']

    # Get filtered leads with sorting and pagination
    # Validate sort_by to prevent SQL injection
    allowed_sort_columns = ['score', 'business_name', 'city', 'tier', 'imported_at']
    if sort_by not in allowed_sort_columns:
        sort_by = 'score'

    # Validate sort_order
    sort_order = 'DESC' if sort_order.upper() == 'DESC' else 'ASC'

    query = f'''
        SELECT * FROM leads
        WHERE {where_clause}
        ORDER BY {sort_by} {sort_order}
        LIMIT ? OFFSET ?
    '''
    params.extend([limit, offset])

    cursor.execute(query, params)
    leads = cursor.fetchall()

    conn.close()

    return (leads, total_count)

def get_distinct_states():
    """Get list of all unique states in database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT state
        FROM leads
        WHERE state IS NOT NULL AND state != ''
        ORDER BY state
    ''')
    states = [row['state'] for row in cursor.fetchall()]
    conn.close()
    return states

def get_distinct_business_types():
    """Get list of all unique business types in database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT business_type
        FROM leads
        WHERE business_type IS NOT NULL AND business_type != ''
        ORDER BY business_type
    ''')
    types = [row['business_type'] for row in cursor.fetchall()]
    conn.close()
    return types

def bulk_update_tier(lead_ids, tier_override):
    """
    Bulk update tier override for multiple leads.

    Args:
        lead_ids: List of lead IDs
        tier_override: Tier to set (A/B/C/U)

    Returns:
        int: Number of leads updated
    """
    if not lead_ids:
        return 0

    conn = get_db_connection()
    cursor = conn.cursor()

    # Create placeholders for IN clause
    placeholders = ','.join(['?'] * len(lead_ids))

    cursor.execute(f'''
        UPDATE leads
        SET tier_override = ?,
            reviewed_at = CURRENT_TIMESTAMP
        WHERE id IN ({placeholders})
    ''', [tier_override] + lead_ids)

    updated_count = cursor.rowcount
    conn.commit()
    conn.close()

    return updated_count

def bulk_mark_reviewed(lead_ids, reviewed_by=None):
    """
    Bulk mark leads as reviewed.

    Args:
        lead_ids: List of lead IDs
        reviewed_by: Username/email of reviewer

    Returns:
        int: Number of leads updated
    """
    if not lead_ids:
        return 0

    conn = get_db_connection()
    cursor = conn.cursor()

    placeholders = ','.join(['?'] * len(lead_ids))

    cursor.execute(f'''
        UPDATE leads
        SET reviewed_at = CURRENT_TIMESTAMP,
            reviewed_by = ?
        WHERE id IN ({placeholders})
    ''', [reviewed_by] + lead_ids)

    updated_count = cursor.rowcount
    conn.commit()
    conn.close()

    return updated_count

def update_personalization(lead_id, custom_line, email_angle):
    """
    Update lead with generated personalization.

    Args:
        lead_id: The lead ID
        custom_line: Generated first line for email
        email_angle: The angle/approach (organic/wholesale/cannabis/etc)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE leads
        SET custom_line = ?,
            email_angle = ?,
            personalization_status = 'generated',
            personalization_generated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (custom_line, email_angle, lead_id))

    conn.commit()
    conn.close()

def update_personalization_error(lead_id, error_message):
    """Mark a lead as failed during personalization."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        UPDATE leads
        SET personalization_status = 'failed',
            custom_line = ?,
            personalization_generated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (f"ERROR: {error_message[:100]}", lead_id))

    conn.commit()
    conn.close()

def get_leads_for_personalization():
    """
    Get leads ready for personalization (Tier A or B, enriched, not yet personalized).

    Returns:
        list: Leads that need personalization
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM leads
        WHERE (COALESCE(tier_override, tier) IN ('A', 'B'))
          AND gemini_status = 'enriched'
          AND (personalization_status = 'pending' OR personalization_status IS NULL)
        ORDER BY COALESCE(tier_override, tier) ASC, score DESC
    ''')

    leads = cursor.fetchall()
    conn.close()
    return leads

def get_personalized_leads():
    """Get all leads with generated personalization."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM leads
        WHERE personalization_status = 'generated'
        ORDER BY COALESCE(tier_override, tier) ASC, score DESC
    ''')

    leads = cursor.fetchall()
    conn.close()
    return leads

def get_leads_for_export(tier_filter=None, require_email=True, require_personalization=False, segment=None):
    """
    Get leads ready for export with optional filters.

    Args:
        tier_filter: Filter by tier(s) - e.g., 'A', 'AB', 'ABC' or None for all
        require_email: Only include leads with email addresses (default: True)
        require_personalization: Only include leads with custom_line (default: False)
        segment: Filter by segment (e.g., 'nursery', 'cannabis_grower') or None for all

    Returns:
        list: Leads ready for export
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    where_conditions = []
    params = []

    # Tier filter
    if tier_filter:
        tiers = list(tier_filter)  # Convert 'AB' to ['A', 'B']
        placeholders = ','.join(['?'] * len(tiers))
        where_conditions.append(f'(COALESCE(tier_override, tier) IN ({placeholders}))')
        params.extend(tiers)

    # Email requirement — must have an email AND be verified OR high-confidence
    # (Places/website-scrape emails ≥85 confidence skip API verification)
    if require_email:
        where_conditions.append(
            '(owner_email IS NOT NULL AND owner_email != "" '
            'AND (email_verified = 1 OR COALESCE(email_confidence, 0) >= 85))'
        )

    # Personalization requirement
    if require_personalization:
        where_conditions.append('(custom_line IS NOT NULL AND custom_line != "")')

    # Segment filter
    if segment:
        where_conditions.append('segment = ?')
        params.append(segment)

    where_clause = ' AND '.join(where_conditions) if where_conditions else '1=1'

    query = f'''
        SELECT * FROM leads
        WHERE {where_clause}
        ORDER BY COALESCE(tier_override, tier) ASC, score DESC
    '''

    cursor.execute(query, params)
    leads = cursor.fetchall()
    conn.close()

    return leads

def log_export(filename, format, tier_filter, record_count, include_metadata=True):
    """
    Log an export to the exports table.

    Args:
        filename: Name of exported file
        format: 'csv' or 'xlsx'
        tier_filter: Tier filter used (e.g., 'AB') or None
        record_count: Number of records exported
        include_metadata: Whether metadata columns were included

    Returns:
        int: Export ID
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        INSERT INTO exports (filename, format, tier_filter, record_count, include_metadata)
        VALUES (?, ?, ?, ?, ?)
    ''', (filename, format, tier_filter, record_count, include_metadata))

    export_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return export_id

def get_export_history(limit=10):
    """
    Get recent export history.

    Args:
        limit: Maximum number of records to return (default: 10)

    Returns:
        list: Recent exports
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM exports
        ORDER BY created_at DESC
        LIMIT ?
    ''', (limit,))

    exports = cursor.fetchall()
    conn.close()

    return exports

def get_export_preview_count(tier_filter=None, require_email=True, require_personalization=False, segment=None):
    """
    Get count of leads that would be exported with given filters.

    Args:
        tier_filter: Filter by tier(s) - e.g., 'A', 'AB', 'ABC' or None for all
        require_email: Only count leads with email addresses (default: True)
        require_personalization: Only count leads with custom_line (default: False)
        segment: Filter by segment (e.g., 'nursery', 'cannabis_grower') or None for all

    Returns:
        int: Number of leads that match filters
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    where_conditions = []
    params = []

    if tier_filter:
        tiers = list(tier_filter)
        placeholders = ','.join(['?'] * len(tiers))
        where_conditions.append(f'(COALESCE(tier_override, tier) IN ({placeholders}))')
        params.extend(tiers)

    if require_email:
        where_conditions.append(
            '(owner_email IS NOT NULL AND owner_email != "" '
            'AND (email_verified = 1 OR COALESCE(email_confidence, 0) >= 85))'
        )

    if require_personalization:
        where_conditions.append('(custom_line IS NOT NULL AND custom_line != "")')

    if segment:
        where_conditions.append('segment = ?')
        params.append(segment)

    where_clause = ' AND '.join(where_conditions) if where_conditions else '1=1'

    query = f'SELECT COUNT(*) as count FROM leads WHERE {where_clause}'
    cursor.execute(query, params)
    count = cursor.fetchone()['count']
    conn.close()

    return count
