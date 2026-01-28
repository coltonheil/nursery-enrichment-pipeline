from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context
import os
import threading
import time
import json
from werkzeug.utils import secure_filename
from database.models import init_db, get_db_connection, get_all_leads, get_lead_by_id, update_enriched_data, log_action, get_leads_with_website, update_scrape_data, get_leads_for_gemini_enrichment, update_gemini_data, update_gemini_error, get_leads_for_scoring, update_lead_score, get_tier_distribution, get_leads_filtered, get_distinct_states, get_distinct_business_types, update_lead_review, bulk_update_tier, bulk_mark_reviewed, get_leads_for_personalization, update_personalization, update_personalization_error, get_personalized_leads, get_leads_for_export, log_export, get_export_history, get_export_preview_count
from importers.excel_importer import import_excel_file, validate_excel_file
from enrichment.google_places import enrich_business
from enrichment.web_scraper import scrape_and_extract
from enrichment.gemini_client import enrich_lead_with_gemini, generate_personalization
from enrichment.scorer import calculate_score, calculate_geo_score
from enrichment.email_hunter import hunt_email
from exporters.instantly_exporter import export_to_csv, export_to_excel, get_export_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'data/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['ALLOWED_EXTENSIONS'] = {'xlsx', 'xls'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Custom Jinja filters (Phase 6)
@app.template_filter('from_json')
def from_json_filter(value):
    """Parse JSON string to Python object."""
    if value is None or value == '':
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return None
    return value

# Global state for scraping job
scraping_state = {
    'running': False,
    'stop_requested': False,
    'total': 0,
    'completed': 0,
    'failed': 0,
    'current_lead': None,
    'errors': []
}

# Global state for AI enrichment job
ai_enrichment_state = {
    'running': False,
    'stop_requested': False,
    'total': 0,
    'completed': 0,
    'failed': 0,
    'current_lead': None,
    'errors': []
}

# Global state for personalization job
personalization_state = {
    'running': False,
    'stop_requested': False,
    'total': 0,
    'completed': 0,
    'failed': 0,
    'current_lead': None,
    'errors': []
}

# Global state for Google Places enrichment job
google_places_state = {
    'running': False,
    'stop_requested': False,
    'total': 0,
    'completed': 0,
    'failed': 0,
    'current_lead': None,
    'errors': []
}

# Global state for full pipeline job
pipeline_state = {
    'running': False,
    'stop_requested': False,
    'current_step': None,  # 'google_places', 'scraping', 'ai_enrichment', 'scoring'
    'step_progress': 0,  # 0-100 for current step
    'overall_progress': 0,  # 0-100 overall
    'batch_size': 0,
    'total_steps': 4,
    'completed_steps': 0,
    'status_message': '',
    'errors': []
}

# Phase 9: Pipeline run tracking functions

def get_or_create_pipeline_run(run_type: str, config: dict = None):
    """Get existing incomplete run or create new one (Phase 9)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check for incomplete run
    cursor.execute("""
        SELECT * FROM pipeline_runs
        WHERE run_type = ? AND status = 'running'
        ORDER BY started_at DESC
        LIMIT 1
    """, (run_type,))

    existing = cursor.fetchone()

    if existing:
        conn.close()
        return dict(existing), True  # (run, is_resume)

    # Create new run
    cursor.execute("""
        INSERT INTO pipeline_runs (run_type, config)
        VALUES (?, ?)
    """, (run_type, json.dumps(config or {})))

    run_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM pipeline_runs WHERE id = ?", (run_id,))
    new_run = dict(cursor.fetchone())
    conn.close()

    return new_run, False


def update_pipeline_progress(run_id: int, completed: int, failed: int, current_lead_id: int = None, error: str = None):
    """Update pipeline run progress (Phase 9)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE pipeline_runs SET
            completed_leads = ?,
            failed_leads = ?,
            current_lead_id = ?,
            error_log = COALESCE(error_log, '') || ?
        WHERE id = ?
    """, (completed, failed, current_lead_id,
          f"\n{error}" if error else "", run_id))

    conn.commit()
    conn.close()


def complete_pipeline_run(run_id: int, status: str = 'completed'):
    """Mark pipeline run as complete (Phase 9)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE pipeline_runs SET
            status = ?,
            completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (status, run_id))

    conn.commit()
    conn.close()


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    """Home page."""
    return render_template('upload.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard with pipeline stats (Phase 8)."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Pipeline progress
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN enrichment_status = 'enriched' THEN 1 ELSE 0 END) as google_enriched,
            SUM(CASE WHEN scrape_status = 'scraped' THEN 1 ELSE 0 END) as scraped,
            SUM(CASE WHEN gemini_status = 'enriched' THEN 1 ELSE 0 END) as ai_enriched,
            SUM(CASE WHEN score IS NOT NULL THEN 1 ELSE 0 END) as scored,
            SUM(CASE WHEN reviewed_at IS NOT NULL THEN 1 ELSE 0 END) as reviewed
        FROM leads
    """)
    pipeline = dict(cursor.fetchone())

    # Tier distribution
    cursor.execute("""
        SELECT
            COALESCE(tier_override, tier, 'U') as tier,
            COUNT(*) as count
        FROM leads
        WHERE score IS NOT NULL
        GROUP BY COALESCE(tier_override, tier, 'U')
    """)
    tier_dist = {row['tier']: row['count'] for row in cursor.fetchall()}

    # Geographic distribution
    cursor.execute("""
        SELECT
            state,
            COUNT(*) as count,
            AVG(score) as avg_score
        FROM leads
        WHERE state IS NOT NULL
        GROUP BY state
        ORDER BY count DESC
    """)
    geo_dist = [dict(row) for row in cursor.fetchall()]

    # ICP type distribution
    cursor.execute("""
        SELECT
            COALESCE(icp_type, 'unknown') as icp_type,
            COUNT(*) as count
        FROM leads
        GROUP BY icp_type
    """)
    icp_dist = {row['icp_type']: row['count'] for row in cursor.fetchall()}

    # Top signals (most common positive signals)
    cursor.execute("""
        SELECT score_breakdown
        FROM leads
        WHERE score_breakdown IS NOT NULL
    """)
    signal_counts = {}
    for row in cursor.fetchall():
        try:
            breakdown = json.loads(row['score_breakdown'])
            if 'signals' in breakdown:
                for signal in breakdown['signals']:
                    if signal.get('points', 0) > 0:  # Only positive signals
                        desc = signal.get('description', 'Unknown')
                        signal_counts[desc] = signal_counts.get(desc, 0) + 1
        except:
            pass
    top_signals = sorted(signal_counts.items(), key=lambda x: -x[1])[:10]

    conn.close()

    return render_template('dashboard.html',
        pipeline=pipeline,
        tier_dist=tier_dist,
        geo_dist=geo_dist,
        icp_dist=icp_dist,
        top_signals=top_signals
    )

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """Handle file upload and import."""
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)

        file = request.files['file']

        # Check if filename is empty
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)

        # Check if file extension is allowed
        if not allowed_file(file.filename):
            flash('Invalid file type. Please upload an Excel file (.xlsx or .xls)', 'error')
            return redirect(request.url)

        try:
            # Save the uploaded file
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Validate the Excel file
            is_valid, error_message = validate_excel_file(filepath)
            if not is_valid:
                flash(f'Validation error: {error_message}', 'error')
                os.remove(filepath)
                return redirect(request.url)

            # Import the file
            results = import_excel_file(filepath, filename)

            # Display results
            if results['errors'] > 0:
                flash(f"Import completed with errors. Imported: {results['imported']}, Duplicates: {results['duplicates']}, Errors: {results['errors']}", 'warning')
                for error in results['error_details'][:5]:  # Show first 5 errors
                    flash(error, 'error')
            else:
                flash(f"Import successful! Imported: {results['imported']} leads, Duplicates skipped: {results['duplicates']}", 'success')

            return redirect(url_for('leads'))

        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'error')
            return redirect(request.url)

    return render_template('upload.html')

@app.route('/leads')
def leads():
    """Display all imported leads with filtering and pagination."""
    # Get filter parameters from query string
    tier_filter = request.args.get('tier', None)
    state_filter = request.args.get('state', None)
    business_type_filter = request.args.get('business_type', None)
    min_score = request.args.get('min_score', type=int)
    max_score = request.args.get('max_score', type=int)
    search = request.args.get('search', None)
    sort_by = request.args.get('sort_by', 'score')
    sort_order = request.args.get('sort_order', 'DESC')
    page = request.args.get('page', 1, type=int)
    per_page = 50

    # Calculate offset
    offset = (page - 1) * per_page

    # Get filtered leads
    filtered_leads, total_count = get_leads_filtered(
        tier=tier_filter,
        state=state_filter,
        business_type=business_type_filter,
        min_score=min_score,
        max_score=max_score,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=per_page,
        offset=offset
    )

    # Calculate pagination info
    total_pages = (total_count + per_page - 1) // per_page

    # Get filter options
    states = get_distinct_states()
    business_types = get_distinct_business_types()

    return render_template('leads.html',
                         leads=filtered_leads,
                         total_count=total_count,
                         page=page,
                         per_page=per_page,
                         total_pages=total_pages,
                         states=states,
                         business_types=business_types,
                         tier_filter=tier_filter,
                         state_filter=state_filter,
                         business_type_filter=business_type_filter,
                         min_score=min_score,
                         max_score=max_score,
                         search=search,
                         sort_by=sort_by,
                         sort_order=sort_order)

@app.route('/enrich/<int:lead_id>', methods=['POST'])
def enrich_lead(lead_id):
    """Enrich a single lead with Google Places data."""
    try:
        # Get the lead
        lead = get_lead_by_id(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404

        # Call Google Places API
        enriched_data = enrich_business(
            lead['business_name'],
            lead['city'],
            lead['state']
        )

        # Check for errors
        if 'error' in enriched_data:
            # Log the failure
            log_action(lead_id, 'enrichment_failed', enriched_data['error'])

            # Update status to failed
            update_enriched_data(lead_id, {'enrichment_status': 'failed'})

            return jsonify({
                'error': enriched_data['error'],
                'lead_id': lead_id
            }), 400

        # Update the lead with enriched data
        enriched_data['enrichment_status'] = 'enriched'
        update_enriched_data(lead_id, enriched_data)

        # Log success
        log_action(lead_id, 'enriched', f"Enriched with Google Places data")

        # Return the enriched data
        return jsonify({
            'success': True,
            'lead_id': lead_id,
            'data': enriched_data
        })

    except Exception as e:
        log_action(lead_id, 'enrichment_error', str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/enrich-batch', methods=['POST'])
def enrich_batch():
    """Enrich multiple leads in batch."""
    try:
        data = request.get_json()
        lead_ids = data.get('lead_ids', [])

        if not lead_ids:
            return jsonify({'error': 'No lead IDs provided'}), 400

        results = {
            'success': [],
            'failed': [],
            'errors': []
        }

        for lead_id in lead_ids:
            lead = get_lead_by_id(lead_id)
            if not lead:
                results['failed'].append(lead_id)
                results['errors'].append(f"Lead {lead_id} not found")
                continue

            # Enrich the lead
            enriched_data = enrich_business(
                lead['business_name'],
                lead['city'],
                lead['state']
            )

            if 'error' in enriched_data:
                log_action(lead_id, 'enrichment_failed', enriched_data['error'])
                update_enriched_data(lead_id, {'enrichment_status': 'failed'})
                results['failed'].append(lead_id)
                results['errors'].append(f"Lead {lead_id}: {enriched_data['error']}")
            else:
                enriched_data['enrichment_status'] = 'enriched'
                update_enriched_data(lead_id, enriched_data)
                log_action(lead_id, 'enriched', "Enriched with Google Places data")
                results['success'].append(lead_id)

        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_full_pipeline(batch_size):
    """
    Background job to run the complete enrichment pipeline on a batch of leads.
    Steps: Google Places → Scrape Websites → AI Enrichment → Scoring
    Phase 9: Now tracks run in pipeline_runs table
    """
    global pipeline_state

    try:
        # Phase 9: Create pipeline run tracking
        run, is_resume = get_or_create_pipeline_run('full_pipeline', {'batch_size': batch_size})
        run_id = run['id']

        pipeline_state['batch_size'] = batch_size
        pipeline_state['completed_steps'] = 0
        pipeline_state['errors'] = []

        # ============================================================
        # STEP 1: Google Places Enrichment
        # ============================================================
        pipeline_state['current_step'] = 'google_places'
        pipeline_state['status_message'] = f'Step 1/4: Google Places enrichment ({batch_size} leads)'
        pipeline_state['step_progress'] = 0

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM leads
            WHERE (enrichment_status = 'pending' OR enrichment_status IS NULL)
            ORDER BY imported_at DESC
            LIMIT ?
        ''', (batch_size,))
        batch_leads = cursor.fetchall()
        conn.close()

        lead_ids = [lead['id'] for lead in batch_leads]
        total_leads = len(lead_ids)

        if total_leads == 0:
            pipeline_state['status_message'] = 'No leads need enrichment'
            return

        # Process Google Places enrichment
        for idx, lead in enumerate(batch_leads):
            if pipeline_state['stop_requested']:
                return

            try:
                enriched_data = enrich_business(lead['business_name'], lead['city'], lead['state'])
                if 'error' not in enriched_data:
                    enriched_data['enrichment_status'] = 'enriched'
                    update_enriched_data(lead['id'], enriched_data)
                    log_action(lead['id'], 'enriched', "Enriched with Google Places data")
                else:
                    log_action(lead['id'], 'enrichment_failed', enriched_data['error'])
                    update_enriched_data(lead['id'], {'enrichment_status': 'failed'})
            except Exception as e:
                log_action(lead['id'], 'enrichment_error', str(e)[:200])
                update_enriched_data(lead['id'], {'enrichment_status': 'failed'})

            pipeline_state['step_progress'] = int((idx + 1) / total_leads * 100)
            pipeline_state['overall_progress'] = int(((pipeline_state['completed_steps'] + (idx + 1) / total_leads) / 4) * 100)

        pipeline_state['completed_steps'] = 1

        # ============================================================
        # STEP 2: Scrape Websites
        # ============================================================
        pipeline_state['current_step'] = 'scraping'
        pipeline_state['status_message'] = f'Step 2/4: Scraping websites'
        pipeline_state['step_progress'] = 0

        # Get the same leads that now have websites
        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(lead_ids))
        cursor.execute(f'''
            SELECT * FROM leads
            WHERE id IN ({placeholders})
              AND website IS NOT NULL
              AND (scrape_status = 'pending' OR scrape_status IS NULL)
        ''', lead_ids)
        leads_to_scrape = cursor.fetchall()
        conn.close()

        for idx, lead in enumerate(leads_to_scrape):
            if pipeline_state['stop_requested']:
                return

            try:
                from enrichment.web_scraper import scrape_and_extract
                extracted_text, status_info = scrape_and_extract(lead['website'])

                if extracted_text and len(extracted_text) > 100:
                    update_scrape_data(lead['id'], extracted_text, 'scraped', None)
                    log_action(lead['id'], 'scraped', f"Scraped {status_info['pages_scraped']} pages")
                else:
                    update_scrape_data(lead['id'], None, 'failed', 'No content extracted')
                    log_action(lead['id'], 'scrape_failed', 'No content extracted')
            except Exception as e:
                update_scrape_data(lead['id'], None, 'failed', str(e)[:200])
                log_action(lead['id'], 'scrape_failed', str(e)[:200])

            pipeline_state['step_progress'] = int((idx + 1) / len(leads_to_scrape) * 100) if leads_to_scrape else 100
            pipeline_state['overall_progress'] = int(((pipeline_state['completed_steps'] + (idx + 1) / max(len(leads_to_scrape), 1)) / 4) * 100)

        pipeline_state['completed_steps'] = 2

        # ============================================================
        # STEP 3: AI Enrichment
        # ============================================================
        pipeline_state['current_step'] = 'ai_enrichment'
        pipeline_state['status_message'] = f'Step 3/4: AI enrichment with Gemini'
        pipeline_state['step_progress'] = 0

        # Get leads that are scraped and ready for AI
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT * FROM leads
            WHERE id IN ({placeholders})
              AND scrape_status = 'scraped'
              AND (gemini_status = 'pending' OR gemini_status IS NULL)
        ''', lead_ids)
        leads_to_ai_enrich = cursor.fetchall()
        conn.close()

        for idx, lead in enumerate(leads_to_ai_enrich):
            if pipeline_state['stop_requested']:
                return

            try:
                enriched_data = enrich_lead_with_gemini(
                    website_text=lead['website_text'],
                    business_name=lead['business_name'],
                    city=lead['city'],
                    state=lead['state']
                )

                if 'error' not in enriched_data:
                    update_gemini_data(lead['id'], enriched_data)
                    log_action(lead['id'], 'gemini_enriched', f"AI enriched: {enriched_data.get('business_type', 'unknown')}")
                else:
                    update_gemini_error(lead['id'], enriched_data['error'])
                    log_action(lead['id'], 'gemini_failed', enriched_data['error'])
            except Exception as e:
                update_gemini_error(lead['id'], str(e)[:200])
                log_action(lead['id'], 'gemini_error', str(e)[:200])

            pipeline_state['step_progress'] = int((idx + 1) / len(leads_to_ai_enrich) * 100) if leads_to_ai_enrich else 100
            pipeline_state['overall_progress'] = int(((pipeline_state['completed_steps'] + (idx + 1) / max(len(leads_to_ai_enrich), 1)) / 4) * 100)

        pipeline_state['completed_steps'] = 3

        # ============================================================
        # STEP 4: Email Hunting & Scoring
        # ============================================================
        pipeline_state['current_step'] = 'email_and_scoring'
        pipeline_state['status_message'] = f'Step 4/4: Email hunting & scoring leads'
        pipeline_state['step_progress'] = 0

        # Score all the leads in the batch
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f'''
            SELECT * FROM leads
            WHERE id IN ({placeholders})
        ''', lead_ids)
        leads_to_score = cursor.fetchall()
        conn.close()

        for idx, lead in enumerate(leads_to_score):
            if pipeline_state['stop_requested']:
                return

            try:
                # Hunt for email if we have owner name and website
                if lead.get('owner_name') and lead.get('website'):
                    try:
                        email_result = hunt_email(
                            owner_name=lead['owner_name'],
                            business_name=lead['business_name'],
                            website=lead['website'],
                            enable_web_search=True,  # 3-layer fallback enabled
                            verify_mx=True
                        )
                        
                        # Update lead with email results
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute('''
                            UPDATE leads
                            SET owner_email = ?,
                                email_confidence = ?,
                                email_method = ?,
                                generic_email = ?,
                                contact_form_url = ?
                            WHERE id = ?
                        ''', (
                            email_result.email,
                            email_result.confidence,
                            email_result.method,
                            email_result.generic_email,
                            email_result.contact_form_url,
                            lead['id']
                        ))
                        conn.commit()
                        conn.close()
                        
                        if email_result.email:
                            log_action(lead['id'], 'email_found', f"Email: {email_result.email} ({email_result.confidence}% via {email_result.method})")
                        else:
                            log_action(lead['id'], 'email_not_found', f"No email found: {email_result.error or 'Unknown reason'}")
                    except Exception as e:
                        log_action(lead['id'], 'email_error', str(e)[:200])
                
                # Score the lead
                score_data = calculate_score(lead)
                update_lead_score(lead['id'], score_data)
                log_action(lead['id'], 'scored', f"Scored {score_data['total']} points, Tier {score_data['tier']}")
            except Exception as e:
                log_action(lead['id'], 'score_error', str(e)[:200])

            pipeline_state['step_progress'] = int((idx + 1) / len(leads_to_score) * 100)
            pipeline_state['overall_progress'] = int(((pipeline_state['completed_steps'] + (idx + 1) / len(leads_to_score)) / 4) * 100)

        pipeline_state['completed_steps'] = 4
        pipeline_state['overall_progress'] = 100
        pipeline_state['status_message'] = f'Pipeline complete! Processed {total_leads} leads'

        # Phase 9: Mark pipeline run as complete
        update_pipeline_progress(run_id, total_leads, 0, None, None)
        complete_pipeline_run(run_id, 'completed')

    except Exception as e:
        pipeline_state['errors'].append(str(e))
        pipeline_state['status_message'] = f'Error: {str(e)[:100]}'
        # Phase 9: Mark as failed
        try:
            complete_pipeline_run(run_id, 'failed')
        except:
            pass
    finally:
        pipeline_state['running'] = False
        pipeline_state['current_step'] = None

def run_google_places_job(batch_size=None):
    """Background job to enrich leads with Google Places data."""
    global google_places_state

    try:
        # Get all leads that need Google Places enrichment
        conn = get_db_connection()
        cursor = conn.cursor()

        query = '''
            SELECT * FROM leads
            WHERE (enrichment_status = 'pending' OR enrichment_status IS NULL)
            ORDER BY imported_at DESC
        '''

        if batch_size is not None:
            query += f' LIMIT {int(batch_size)}'

        cursor.execute(query)
        leads_to_enrich = cursor.fetchall()
        conn.close()

        google_places_state['total'] = len(leads_to_enrich)
        google_places_state['completed'] = 0
        google_places_state['failed'] = 0
        google_places_state['errors'] = []

        for lead in leads_to_enrich:
            # Check if stop was requested
            if google_places_state['stop_requested']:
                break

            google_places_state['current_lead'] = lead['business_name']

            try:
                # Call Google Places API
                enriched_data = enrich_business(
                    lead['business_name'],
                    lead['city'],
                    lead['state']
                )

                if 'error' in enriched_data:
                    # Log the failure
                    log_action(lead['id'], 'enrichment_failed', enriched_data['error'])
                    update_enriched_data(lead['id'], {'enrichment_status': 'failed'})
                    google_places_state['failed'] += 1
                    google_places_state['errors'].append(f"{lead['business_name']}: {enriched_data['error']}")
                else:
                    # Update the lead with enriched data
                    enriched_data['enrichment_status'] = 'enriched'
                    update_enriched_data(lead['id'], enriched_data)
                    log_action(lead['id'], 'enriched', "Enriched with Google Places data")
                    google_places_state['completed'] += 1

            except Exception as e:
                # Error during enrichment
                error_msg = str(e)[:200]
                log_action(lead['id'], 'enrichment_error', error_msg)
                update_enriched_data(lead['id'], {'enrichment_status': 'failed'})
                google_places_state['failed'] += 1
                google_places_state['errors'].append(f"{lead['business_name']}: {error_msg}")

    finally:
        google_places_state['running'] = False
        google_places_state['current_lead'] = None

@app.route('/google-places/start', methods=['POST'])
def start_google_places():
    """Start the background Google Places enrichment job."""
    global google_places_state

    if google_places_state['running']:
        return jsonify({'error': 'Google Places enrichment already running'}), 400

    # Get optional batch_size from request
    batch_size = None
    if request.is_json:
        data = request.get_json()
        batch_size = data.get('batch_size', None)
        if batch_size is not None:
            try:
                batch_size = int(batch_size)
                if batch_size < 1:
                    return jsonify({'error': 'Batch size must be at least 1'}), 400
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid batch size'}), 400

    # Reset state
    google_places_state['running'] = True
    google_places_state['stop_requested'] = False

    # Start background thread with batch_size
    thread = threading.Thread(target=run_google_places_job, args=(batch_size,))
    thread.daemon = True
    thread.start()

    message = 'Google Places enrichment started'
    if batch_size:
        message += f' (batch size: {batch_size} leads)'

    return jsonify({'message': message})

@app.route('/google-places/status')
def google_places_status():
    """SSE endpoint for Google Places enrichment progress."""
    def generate():
        while google_places_state['running'] or google_places_state['completed'] > 0:
            data = {
                'running': google_places_state['running'],
                'total': google_places_state['total'],
                'completed': google_places_state['completed'],
                'failed': google_places_state['failed'],
                'current_lead': google_places_state['current_lead'],
                'errors': google_places_state['errors'][-5:]  # Last 5 errors
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(0.5)  # Update every 500ms

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/google-places/stop', methods=['POST'])
def stop_google_places():
    """Stop the Google Places enrichment job gracefully."""
    global google_places_state

    if not google_places_state['running']:
        return jsonify({'error': 'No Google Places enrichment job running'}), 400

    google_places_state['stop_requested'] = True
    return jsonify({'message': 'Stop requested - will finish current lead'})

@app.route('/pipeline/start', methods=['POST'])
def start_full_pipeline():
    """Start the full enrichment pipeline."""
    global pipeline_state

    if pipeline_state['running']:
        return jsonify({'error': 'Pipeline already running'}), 400

    # Get batch_size from request (required)
    if not request.is_json:
        return jsonify({'error': 'JSON body required'}), 400

    data = request.get_json()
    batch_size = data.get('batch_size')

    if not batch_size:
        return jsonify({'error': 'batch_size is required'}), 400

    try:
        batch_size = int(batch_size)
        if batch_size < 1:
            return jsonify({'error': 'Batch size must be at least 1'}), 400
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid batch size'}), 400

    # Reset state
    pipeline_state['running'] = True
    pipeline_state['stop_requested'] = False
    pipeline_state['overall_progress'] = 0
    pipeline_state['step_progress'] = 0
    pipeline_state['completed_steps'] = 0
    pipeline_state['current_step'] = None
    pipeline_state['errors'] = []

    # Start background thread
    thread = threading.Thread(target=run_full_pipeline, args=(batch_size,))
    thread.daemon = True
    thread.start()

    return jsonify({'message': f'Full pipeline started for {batch_size} leads'})

@app.route('/pipeline/status')
def pipeline_status():
    """SSE endpoint for full pipeline progress."""
    def generate():
        while pipeline_state['running'] or pipeline_state['overall_progress'] > 0:
            data = {
                'running': pipeline_state['running'],
                'current_step': pipeline_state['current_step'],
                'step_progress': pipeline_state['step_progress'],
                'overall_progress': pipeline_state['overall_progress'],
                'batch_size': pipeline_state['batch_size'],
                'completed_steps': pipeline_state['completed_steps'],
                'total_steps': pipeline_state['total_steps'],
                'status_message': pipeline_state['status_message'],
                'errors': pipeline_state['errors'][-5:]  # Last 5 errors
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(0.5)  # Update every 500ms

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/pipeline/stop', methods=['POST'])
def stop_pipeline():
    """Stop the pipeline job gracefully."""
    global pipeline_state

    if not pipeline_state['running']:
        return jsonify({'error': 'No pipeline job running'}), 400

    pipeline_state['stop_requested'] = True
    return jsonify({'message': 'Stop requested - will finish current lead'})

def run_scraping_job():
    """Background job to scrape websites."""
    global scraping_state

    try:
        # Get all leads with websites that need scraping
        all_leads = get_leads_with_website()
        leads_to_scrape = [lead for lead in all_leads if lead['scrape_status'] == 'pending']

        scraping_state['total'] = len(leads_to_scrape)
        scraping_state['completed'] = 0
        scraping_state['failed'] = 0
        scraping_state['errors'] = []

        for lead in leads_to_scrape:
            # Check if stop was requested
            if scraping_state['stop_requested']:
                break

            scraping_state['current_lead'] = lead['business_name']

            try:
                # Scrape and extract
                extracted_text, status_info = scrape_and_extract(lead['website'])

                if extracted_text and len(extracted_text) > 100:
                    # Success
                    update_scrape_data(lead['id'], extracted_text, 'scraped', None)
                    log_action(lead['id'], 'scraped', f"Scraped {status_info['pages_scraped']} pages, {status_info['total_chars']} chars")
                    scraping_state['completed'] += 1
                else:
                    # Failed - no content
                    error_msg = 'No content extracted (possible JS-only site)'
                    update_scrape_data(lead['id'], None, 'failed', error_msg)
                    log_action(lead['id'], 'scrape_failed', error_msg)
                    scraping_state['failed'] += 1
                    scraping_state['errors'].append(f"{lead['business_name']}: {error_msg}")

            except Exception as e:
                # Error during scraping
                error_msg = str(e)[:200]
                update_scrape_data(lead['id'], None, 'failed', error_msg)
                log_action(lead['id'], 'scrape_failed', error_msg)
                scraping_state['failed'] += 1
                scraping_state['errors'].append(f"{lead['business_name']}: {error_msg}")

    finally:
        scraping_state['running'] = False
        scraping_state['current_lead'] = None

@app.route('/scrape/start', methods=['POST'])
def start_scraping():
    """Start the background scraping job."""
    global scraping_state

    if scraping_state['running']:
        return jsonify({'error': 'Scraping already running'}), 400

    # Reset state
    scraping_state['running'] = True
    scraping_state['stop_requested'] = False

    # Start background thread
    thread = threading.Thread(target=run_scraping_job)
    thread.daemon = True
    thread.start()

    return jsonify({'message': 'Scraping started'})

@app.route('/scrape/status')
def scraping_status():
    """SSE endpoint for scraping progress."""
    def generate():
        while scraping_state['running'] or scraping_state['completed'] > 0:
            data = {
                'running': scraping_state['running'],
                'total': scraping_state['total'],
                'completed': scraping_state['completed'],
                'failed': scraping_state['failed'],
                'current_lead': scraping_state['current_lead'],
                'errors': scraping_state['errors'][-5:]  # Last 5 errors
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(0.5)  # Update every 500ms

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/scrape/stop', methods=['POST'])
def stop_scraping():
    """Stop the scraping job gracefully."""
    global scraping_state

    if not scraping_state['running']:
        return jsonify({'error': 'No scraping job running'}), 400

    scraping_state['stop_requested'] = True
    return jsonify({'message': 'Stop requested - will finish current lead'})

def run_ai_enrichment_job(batch_size=None):
    """
    Background job to enrich leads with Gemini AI.

    Args:
        batch_size: Optional limit on number of leads to enrich (None = all leads)
    """
    global ai_enrichment_state

    try:
        # Get all leads ready for AI enrichment (with optional batch limit)
        leads_to_enrich = get_leads_for_gemini_enrichment(limit=batch_size)

        ai_enrichment_state['total'] = len(leads_to_enrich)
        ai_enrichment_state['completed'] = 0
        ai_enrichment_state['failed'] = 0
        ai_enrichment_state['errors'] = []

        for lead in leads_to_enrich:
            # Check if stop was requested
            if ai_enrichment_state['stop_requested']:
                break

            ai_enrichment_state['current_lead'] = lead['business_name']

            try:
                # Enrich with Gemini
                enriched_data = enrich_lead_with_gemini(
                    website_text=lead['website_text'],
                    business_name=lead['business_name'],
                    city=lead['city'],
                    state=lead['state']
                )

                # Save to database
                update_gemini_data(lead['id'], enriched_data, enriched_data)
                log_action(lead['id'], 'gemini_enriched', f"AI enrichment completed - {enriched_data.get('business_type')} ({enriched_data.get('confidence')} confidence)")
                ai_enrichment_state['completed'] += 1

                # Rate limit: 1 request per second (safe for free tier)
                time.sleep(1)

            except Exception as e:
                # Error during enrichment
                error_msg = str(e)[:200]
                update_gemini_error(lead['id'], error_msg)
                log_action(lead['id'], 'gemini_failed', error_msg)
                ai_enrichment_state['failed'] += 1
                ai_enrichment_state['errors'].append(f"{lead['business_name']}: {error_msg}")

    finally:
        ai_enrichment_state['running'] = False
        ai_enrichment_state['current_lead'] = None

@app.route('/enrich-ai/start', methods=['POST'])
def start_ai_enrichment():
    """
    Start the background AI enrichment job.

    Optional JSON body:
        batch_size: Number of leads to enrich (e.g., {"batch_size": 10})
    """
    global ai_enrichment_state

    if ai_enrichment_state['running']:
        return jsonify({'error': 'AI enrichment already running'}), 400

    # Get optional batch_size from request
    batch_size = None
    if request.is_json:
        data = request.get_json()
        batch_size = data.get('batch_size', None)
        if batch_size is not None:
            try:
                batch_size = int(batch_size)
                if batch_size < 1:
                    return jsonify({'error': 'Batch size must be at least 1'}), 400
            except (ValueError, TypeError):
                return jsonify({'error': 'Invalid batch size'}), 400

    # Reset state
    ai_enrichment_state['running'] = True
    ai_enrichment_state['stop_requested'] = False

    # Start background thread with batch_size
    thread = threading.Thread(target=run_ai_enrichment_job, args=(batch_size,))
    thread.daemon = True
    thread.start()

    message = f'AI enrichment started'
    if batch_size:
        message += f' (batch size: {batch_size} leads)'

    return jsonify({'message': message})

@app.route('/enrich-ai/status')
def ai_enrichment_status():
    """SSE endpoint for AI enrichment progress."""
    def generate():
        while ai_enrichment_state['running'] or ai_enrichment_state['completed'] > 0:
            data = {
                'running': ai_enrichment_state['running'],
                'total': ai_enrichment_state['total'],
                'completed': ai_enrichment_state['completed'],
                'failed': ai_enrichment_state['failed'],
                'current_lead': ai_enrichment_state['current_lead'],
                'errors': ai_enrichment_state['errors'][-5:]  # Last 5 errors
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(0.5)  # Update every 500ms

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/enrich-ai/stop', methods=['POST'])
def stop_ai_enrichment():
    """Stop the AI enrichment job gracefully."""
    global ai_enrichment_state

    if not ai_enrichment_state['running']:
        return jsonify({'error': 'No AI enrichment job running'}), 400

    ai_enrichment_state['stop_requested'] = True
    return jsonify({'message': 'Stop requested - will finish current lead'})

@app.route('/score/all', methods=['POST'])
def score_all_leads():
    """
    Score leads in the database.

    Optional JSON body:
        batch_size: Number of leads to score (e.g., {"batch_size": 10})
    """
    try:
        # Get optional batch_size from request
        batch_size = None
        if request.is_json:
            data = request.get_json()
            batch_size = data.get('batch_size', None)
            if batch_size is not None:
                try:
                    batch_size = int(batch_size)
                    if batch_size < 1:
                        return jsonify({'error': 'Batch size must be at least 1'}), 400
                except (ValueError, TypeError):
                    return jsonify({'error': 'Invalid batch size'}), 400

        # Get leads to score (with optional limit)
        all_leads = get_leads_for_scoring(limit=batch_size)

        results = {
            'total': len(all_leads),
            'scored': 0,
            'tier_distribution': {'A': 0, 'B': 0, 'C': 0, 'U': 0}
        }

        for lead in all_leads:
            # Calculate score
            score_data = calculate_score(lead)

            # Save to database
            update_lead_score(lead['id'], score_data)
            log_action(lead['id'], 'scored', f"Scored {score_data['total']} points, Tier {score_data['tier']}")

            results['scored'] += 1
            results['tier_distribution'][score_data['tier']] += 1

        message = f"Scored {results['scored']} leads"
        if batch_size:
            message += f" (batch size: {batch_size})"

        return jsonify({
            'success': True,
            'message': message,
            'tier_distribution': results['tier_distribution']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/score/<int:lead_id>', methods=['POST'])
def score_single_lead(lead_id):
    """Rescore a single lead."""
    try:
        # Get the lead
        lead = get_lead_by_id(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404

        # Calculate score
        score_data = calculate_score(lead)

        # Save to database
        update_lead_score(lead_id, score_data)
        log_action(lead_id, 'rescored', f"Rescored {score_data['total']} points, Tier {score_data['tier']}")

        return jsonify({
            'success': True,
            'lead_id': lead_id,
            'score': score_data['total'],
            'tier': score_data['tier'],
            'signals': score_data['signals']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/rescore/all', methods=['POST'])
def rescore_all_leads():
    """
    Re-score all enriched leads with new ICP-based scoring model (Phases 3-4).
    Uses geographic intelligence and ICP qualification gate.

    This is faster than re-enrichment since it doesn't call Gemini API.

    Optional JSON body:
        batch_size: Limit number of leads to rescore (default: all)
    """
    try:
        # Get optional batch_size
        batch_size = None
        if request.is_json:
            data = request.get_json()
            batch_size = data.get('batch_size', None)
            if batch_size is not None:
                batch_size = int(batch_size)

        # Get all enriched leads
        conn = get_db_connection()
        cursor = conn.cursor()

        query = """
            SELECT * FROM leads
            WHERE gemini_status = 'enriched'
            ORDER BY imported_at DESC
        """

        if batch_size:
            query += f" LIMIT {batch_size}"

        cursor.execute(query)
        leads = cursor.fetchall()

        results = {
            'total': len(leads),
            'rescored': 0,
            'tier_distribution': {'A': 0, 'B': 0, 'C': 0, 'U': 0},
            'icp_distribution': {
                'primary': 0,
                'secondary': 0,
                'tertiary': 0,
                'disqualified': 0
            }
        }

        for lead in leads:
            # Convert to dict for scorer
            lead_dict = dict(lead)

            # Calculate score with new ICP-based model (includes geo scoring)
            score_result = calculate_score(lead_dict)

            # Update database with new score, tier, ICP status, and geo score
            cursor.execute('''
                UPDATE leads
                SET score = ?,
                    tier = ?,
                    icp_qualified = ?,
                    icp_type = ?,
                    geo_score = ?,
                    score_breakdown = ?,
                    rescored_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                score_result['total'],
                score_result['tier'],
                score_result.get('icp_qualified'),
                score_result.get('icp_type'),
                score_result.get('geo_score', 0),
                json.dumps({
                    'total': score_result['total'],
                    'signals': score_result['signals'],
                    'tier': score_result['tier'],
                    'has_data': score_result['has_data']
                }),
                lead['id']
            ))

            results['rescored'] += 1
            results['tier_distribution'][score_result['tier']] += 1
            results['icp_distribution'][score_result.get('icp_type', 'disqualified')] += 1

        conn.commit()
        conn.close()

        message = f"Rescored {results['rescored']} leads with new ICP-based model"
        if batch_size:
            message += f" (batch size: {batch_size})"

        return jsonify({
            'success': True,
            'message': message,
            'tier_distribution': results['tier_distribution'],
            'icp_distribution': results['icp_distribution'],
            'total': results['total']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tier-distribution')
def api_tier_distribution():
    """Get tier distribution for dashboard."""
    try:
        distribution = get_tier_distribution()
        return jsonify(distribution)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def api_stats():
    """Get overall lead statistics."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get counts
        cursor.execute("SELECT COUNT(*) FROM leads")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM leads WHERE tier = 'A'")
        tier_a = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM leads WHERE tier = 'B'")
        tier_b = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM leads WHERE tier = 'C'")
        tier_c = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM leads WHERE tier = 'U' OR tier IS NULL")
        tier_u = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM leads WHERE owner_email IS NOT NULL AND owner_email != ''")
        with_email = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'total_leads': total,
            'tier_a': tier_a,
            'tier_b': tier_b,
            'tier_c': tier_c,
            'tier_u': tier_u,
            'with_email': with_email
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/lead/<int:lead_id>')
def api_get_lead(lead_id):
    """Get full lead details including score breakdown."""
    try:
        lead = get_lead_by_id(lead_id)
        if not lead:
            return jsonify({'error': 'Lead not found'}), 404

        # Convert sqlite3.Row to dict
        lead_dict = dict(lead)

        # Parse JSON fields
        import json
        if lead_dict.get('score_breakdown'):
            try:
                lead_dict['score_breakdown'] = json.loads(lead_dict['score_breakdown'])
            except:
                pass

        if lead_dict.get('negative_indicators'):
            try:
                lead_dict['negative_indicators'] = json.loads(lead_dict['negative_indicators'])
            except:
                pass

        if lead_dict.get('crops_grown'):
            try:
                lead_dict['crops_grown'] = json.loads(lead_dict['crops_grown'])
            except:
                pass

        if lead_dict.get('size_signals'):
            try:
                lead_dict['size_signals'] = json.loads(lead_dict['size_signals'])
            except:
                pass

        return jsonify(lead_dict)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/leads/<int:lead_id>/tier-override', methods=['POST'])
def set_tier_override(lead_id):
    """Set manual tier override for a lead (Phase 7 - Keyboard Shortcuts)."""
    try:
        data = request.get_json()
        tier = data.get('tier')

        if tier not in ['A', 'B', 'C', 'U']:
            return jsonify({"error": "Invalid tier"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE leads SET
                tier_override = ?,
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (tier, lead_id))
        conn.commit()
        conn.close()

        log_action(lead_id, 'tier_override', f"Tier set to {tier}")

        return jsonify({"status": "ok", "tier": tier})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/leads/<int:lead_id>/reviewed', methods=['POST'])
def mark_reviewed(lead_id):
    """Mark a lead as reviewed (Phase 7 - Keyboard Shortcuts)."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE leads SET
                reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (lead_id,))
        conn.commit()
        conn.close()

        log_action(lead_id, 'reviewed', 'Marked as reviewed')

        return jsonify({"status": "ok"})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/lead/<int:lead_id>/review', methods=['POST'])
def api_update_review(lead_id):
    """Update lead review data (tier override, notes)."""
    try:
        data = request.get_json()

        tier_override = data.get('tier_override')
        review_notes = data.get('review_notes')
        reviewed_by = data.get('reviewed_by', 'user')

        # Update review
        update_lead_review(lead_id, tier_override, review_notes, reviewed_by)
        log_action(lead_id, 'reviewed', f"Tier override: {tier_override}, Notes: {review_notes[:50] if review_notes else 'None'}")

        return jsonify({
            'success': True,
            'message': 'Review updated successfully'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bulk/update-tier', methods=['POST'])
def api_bulk_update_tier():
    """Bulk update tier for multiple leads."""
    try:
        data = request.get_json()
        lead_ids = data.get('lead_ids', [])
        tier_override = data.get('tier')

        if not lead_ids or not tier_override:
            return jsonify({'error': 'Missing lead_ids or tier'}), 400

        if tier_override not in ['A', 'B', 'C', 'U']:
            return jsonify({'error': 'Invalid tier'}), 400

        # Update leads
        updated_count = bulk_update_tier(lead_ids, tier_override)

        # Log actions
        for lead_id in lead_ids:
            log_action(lead_id, 'bulk_tier_update', f"Tier override set to {tier_override}")

        return jsonify({
            'success': True,
            'message': f'Updated {updated_count} leads to Tier {tier_override}',
            'updated_count': updated_count
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/bulk/mark-reviewed', methods=['POST'])
def api_bulk_mark_reviewed():
    """Bulk mark leads as reviewed."""
    try:
        data = request.get_json()
        lead_ids = data.get('lead_ids', [])
        reviewed_by = data.get('reviewed_by', 'user')

        if not lead_ids:
            return jsonify({'error': 'Missing lead_ids'}), 400

        # Update leads
        updated_count = bulk_mark_reviewed(lead_ids, reviewed_by)

        # Log actions
        for lead_id in lead_ids:
            log_action(lead_id, 'bulk_reviewed', f"Marked as reviewed by {reviewed_by}")

        return jsonify({
            'success': True,
            'message': f'Marked {updated_count} leads as reviewed',
            'updated_count': updated_count
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

def run_personalization_job():
    """Background job to generate personalized email lines."""
    global personalization_state

    try:
        # Get leads ready for personalization (Tier A + B, enriched)
        leads_to_personalize = get_leads_for_personalization()

        personalization_state['total'] = len(leads_to_personalize)
        personalization_state['completed'] = 0
        personalization_state['failed'] = 0
        personalization_state['errors'] = []

        for lead in leads_to_personalize:
            # Check if stop was requested
            if personalization_state['stop_requested']:
                break

            personalization_state['current_lead'] = lead['business_name']

            try:
                # Parse JSON fields
                import json
                crops_grown = []
                size_signals = []

                if lead['crops_grown']:
                    try:
                        crops_grown = json.loads(lead['crops_grown'])
                    except:
                        pass

                if lead['size_signals']:
                    try:
                        size_signals = json.loads(lead['size_signals'])
                    except:
                        pass

                # Generate personalization
                result = generate_personalization(
                    business_name=lead['business_name'],
                    business_type=lead['business_type'],
                    organic_focus=lead['organic_focus'],
                    crops_grown=crops_grown,
                    size_signals=size_signals,
                    is_wholesale=lead['is_wholesale'],
                    container_production=lead['container_production']
                )

                # Save to database
                update_personalization(lead['id'], result['custom_line'], result['email_angle'])
                log_action(lead['id'], 'personalized', f"Generated custom line: {result['custom_line'][:50]}...")
                personalization_state['completed'] += 1

                # Rate limit: 1 request per second
                time.sleep(1)

            except Exception as e:
                # Error during personalization
                error_msg = str(e)[:200]
                update_personalization_error(lead['id'], error_msg)
                log_action(lead['id'], 'personalization_failed', error_msg)
                personalization_state['failed'] += 1
                personalization_state['errors'].append(f"{lead['business_name']}: {error_msg}")

    finally:
        personalization_state['running'] = False
        personalization_state['current_lead'] = None

@app.route('/personalize/start', methods=['POST'])
def start_personalization():
    """Start the background personalization job."""
    global personalization_state

    if personalization_state['running']:
        return jsonify({'error': 'Personalization already running'}), 400

    # Reset state
    personalization_state['running'] = True
    personalization_state['stop_requested'] = False

    # Start background thread
    thread = threading.Thread(target=run_personalization_job)
    thread.daemon = True
    thread.start()

    return jsonify({'message': 'Personalization started'})

@app.route('/personalize/status')
def personalization_status():
    """SSE endpoint for personalization progress."""
    def generate():
        while personalization_state['running'] or personalization_state['completed'] > 0:
            data = {
                'running': personalization_state['running'],
                'total': personalization_state['total'],
                'completed': personalization_state['completed'],
                'failed': personalization_state['failed'],
                'current_lead': personalization_state['current_lead'],
                'errors': personalization_state['errors'][-5:]  # Last 5 errors
            }
            yield f"data: {json.dumps(data)}\n\n"
            time.sleep(0.5)  # Update every 500ms

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/personalize/stop', methods=['POST'])
def stop_personalization():
    """Stop the personalization job gracefully."""
    global personalization_state

    if not personalization_state['running']:
        return jsonify({'error': 'No personalization job running'}), 400

    personalization_state['stop_requested'] = True
    return jsonify({'message': 'Stop requested - will finish current lead'})

@app.route('/api/personalized-leads')
def api_get_personalized_leads():
    """Get all leads with generated personalization."""
    try:
        leads = get_personalized_leads()
        # Convert to list of dicts
        result = []
        for lead in leads:
            result.append({
                'id': lead['id'],
                'business_name': lead['business_name'],
                'tier': lead['tier_override'] or lead['tier'],
                'score': lead['score'],
                'custom_line': lead['custom_line'],
                'email_angle': lead['email_angle'],
                'owner_email': lead['owner_email']
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export')
def export_page():
    """Show export configuration page."""
    # Get tier distribution for reference
    tier_dist = get_tier_distribution()

    # Get export history
    recent_exports = get_export_history(limit=10)

    return render_template('export.html',
                         tier_distribution=tier_dist,
                         export_history=recent_exports)

@app.route('/api/export/preview')
def api_export_preview():
    """Get preview count of leads that would be exported."""
    try:
        # Get filter parameters
        tier_filter = request.args.get('tiers', None)  # e.g., 'AB'
        require_email = request.args.get('require_email', 'true').lower() == 'true'
        require_personalization = request.args.get('require_personalization', 'false').lower() == 'true'

        count = get_export_preview_count(
            tier_filter=tier_filter,
            require_email=require_email,
            require_personalization=require_personalization
        )

        return jsonify({'count': count})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/export/csv', methods=['POST'])
def export_csv():
    """Generate and download CSV export."""
    try:
        # Get filter parameters from form
        tier_filter = request.form.get('tiers', None)  # e.g., 'AB'
        require_email = request.form.get('require_email', 'on') == 'on'
        require_personalization = request.form.get('require_personalization', 'off') == 'on'
        include_metadata = request.form.get('include_metadata', 'on') == 'on'

        # Get leads for export
        leads = get_leads_for_export(
            tier_filter=tier_filter,
            require_email=require_email,
            require_personalization=require_personalization
        )

        if not leads:
            flash('No leads match the export criteria', 'warning')
            return redirect(url_for('export_page'))

        # Convert to list of dicts
        leads_list = [dict(lead) for lead in leads]

        # Generate CSV
        csv_content = export_to_csv(leads_list, include_metadata=include_metadata)

        # Generate filename
        filename = get_export_filename(format='csv', tier_filter=tier_filter)

        # Log export
        log_export(
            filename=filename,
            format='csv',
            tier_filter=tier_filter,
            record_count=len(leads_list),
            include_metadata=include_metadata
        )

        # Create response
        from flask import make_response
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'

        return response

    except Exception as e:
        flash(f'Export failed: {str(e)}', 'error')
        return redirect(url_for('export_page'))

@app.route('/export/excel', methods=['POST'])
def export_excel():
    """Generate and download Excel export."""
    try:
        # Get filter parameters from form
        tier_filter = request.form.get('tiers', None)
        require_email = request.form.get('require_email', 'on') == 'on'
        require_personalization = request.form.get('require_personalization', 'off') == 'on'
        include_metadata = request.form.get('include_metadata', 'on') == 'on'

        # Get leads for export
        leads = get_leads_for_export(
            tier_filter=tier_filter,
            require_email=require_email,
            require_personalization=require_personalization
        )

        if not leads:
            flash('No leads match the export criteria', 'warning')
            return redirect(url_for('export_page'))

        # Convert to list of dicts
        leads_list = [dict(lead) for lead in leads]

        # Generate Excel
        excel_content = export_to_excel(leads_list, include_metadata=include_metadata)

        # Generate filename
        filename = get_export_filename(format='xlsx', tier_filter=tier_filter)

        # Log export
        log_export(
            filename=filename,
            format='xlsx',
            tier_filter=tier_filter,
            record_count=len(leads_list),
            include_metadata=include_metadata
        )

        # Create response
        from flask import make_response, send_file
        return send_file(
            excel_content,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except ImportError:
        flash('Excel export requires openpyxl. Install with: pip install openpyxl', 'error')
        return redirect(url_for('export_page'))
    except Exception as e:
        flash(f'Export failed: {str(e)}', 'error')
        return redirect(url_for('export_page'))

@app.route('/health')
def health():
    """Health check endpoint."""
    return {'status': 'ok', 'message': 'Nursery Enrichment Pipeline is running'}

if __name__ == '__main__':
    # Initialize database
    init_db()
    print("\n" + "="*50)
    print("Starting Nursery Enrichment Pipeline")
    print("="*50)
    print(f"Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"Allowed file types: {', '.join(app.config['ALLOWED_EXTENSIONS'])}")
    print(f"Max file size: {app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB")
    print("\nAccess the application at: http://localhost:5000")
    print("="*50 + "\n")

    # Run the Flask app
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5002, debug=debug_mode)
