"""
Instantly Integration Routes for Flask App
Add these routes to app.py or import as a module

This file contains:
- V2 page routes for outreach queue and campaign stats
- API endpoint for queue preview (for "Add to Queue" modal)
"""

from flask import render_template, request, jsonify
from database.models import get_db_connection


def register_instantly_routes(app):
    """Register all Instantly-related routes with the Flask app"""
    
    # Import and register the API blueprint
    from instantly_integration import instantly_bp, init_instantly_tables
    app.register_blueprint(instantly_bp)
    
    # Initialize database tables
    init_instantly_tables()
    
    # =========================================================================
    # V2 Page Routes
    # =========================================================================
    
    @app.route('/v2/outreach-queue')
    def outreach_queue_v2():
        """Outreach queue / staging area (Phase 2)"""
        return render_template('outreach_queue_v2.html')
    
    @app.route('/v2/campaign-stats')
    def campaign_stats_v2():
        """Campaign statistics dashboard (Phase 3)"""
        return render_template('campaign_stats_v2.html')
    
    @app.route('/v2/hot-leads')
    def hot_leads_v2():
        """Hot leads page - leads that replied or showed interest"""
        return render_template('hot_leads_v2.html')
    
    # =========================================================================
    # API Helper Routes
    # =========================================================================
    
    @app.route('/api/v2/instantly/queue-preview')
    def queue_preview():
        """
        Preview leads that would be added to queue.
        Used by "Add to Queue" modal to show count before adding.
        """
        tiers = request.args.get('tiers', 'AB').upper().split(',')
        require_email = request.args.get('require_email', 'true').lower() == 'true'
        skip_sent = request.args.get('skip_sent', 'true').lower() == 'true'
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build query
        tier_placeholders = ','.join(['?'] * len(tiers))
        conditions = [f'COALESCE(tier_override, tier) IN ({tier_placeholders})']
        params = list(tiers)
        
        if require_email:
            conditions.append('((owner_email IS NOT NULL AND owner_email != "") OR (contact_email IS NOT NULL AND contact_email != ""))')
        
        if skip_sent:
            conditions.append('(instantly_status IS NULL OR instantly_status = "")')
            # Also skip leads already in queue
            conditions.append('id NOT IN (SELECT lead_id FROM outreach_queue)')
        
        where_clause = ' AND '.join(conditions)
        
        # Get count
        cursor.execute(f'SELECT COUNT(*) as count FROM leads WHERE {where_clause}', params)
        count = cursor.fetchone()['count']
        
        # Get breakdown by tier
        cursor.execute(f'''
            SELECT COALESCE(tier_override, tier) as tier, COUNT(*) as count
            FROM leads
            WHERE {where_clause}
            GROUP BY COALESCE(tier_override, tier)
        ''', params)
        
        by_tier = {row['tier']: row['count'] for row in cursor.fetchall()}
        
        # Get lead IDs
        cursor.execute(f'SELECT id FROM leads WHERE {where_clause} LIMIT 10000', params)
        lead_ids = [row['id'] for row in cursor.fetchall()]
        
        conn.close()
        
        return jsonify({
            'count': count,
            'by_tier': by_tier,
            'lead_ids': lead_ids
        })
    
    @app.route('/api/v2/instantly/lead/<int:lead_id>/send', methods=['POST'])
    def send_single_lead_api(lead_id):
        """Quick send a single lead to Instantly (for lead card button)"""
        from instantly_integration import InstantlySender, InstantlyConfig
        
        if not InstantlyConfig.is_configured():
            return jsonify({'error': 'Instantly not configured'}), 500
        
        data = request.get_json() or {}
        campaign_id = data.get('campaign_id')
        
        sender = InstantlySender()
        result = sender.send_lead(lead_id, campaign_id)
        
        return jsonify({
            'success': result.success,
            'lead_id': result.lead_id,
            'email': result.email,
            'campaign_id': result.campaign_id,
            'error': result.error
        })
    
    @app.route('/api/v2/instantly/lead/<int:lead_id>/add-to-queue', methods=['POST'])
    def add_single_lead_to_queue(lead_id):
        """Add a single lead to the outreach queue (for lead card button)"""
        from instantly_integration import OutreachQueue
        
        added, skipped = OutreachQueue.add_to_queue([lead_id])
        
        return jsonify({
            'success': added > 0,
            'added': added,
            'skipped': skipped
        })
    
    print("✅ Instantly routes registered")


# Helper to add Instantly buttons to lead cards in dashboard_v2.html
LEAD_CARD_INSTANTLY_BUTTONS = '''
<div class="btn-group mt-2">
    <button class="btn btn-sm btn-outline-primary" 
            onclick="sendToInstantly({{ lead.id }})"
            title="Send directly to Instantly">
        <i class="bi bi-send"></i> Send
    </button>
    <button class="btn btn-sm btn-outline-secondary"
            onclick="addToQueue({{ lead.id }})"
            title="Add to outreach queue for review">
        <i class="bi bi-inbox"></i> Queue
    </button>
</div>
'''

# JavaScript for lead card buttons
LEAD_CARD_INSTANTLY_JS = '''
<script>
async function sendToInstantly(leadId) {
    if (!confirm('Send this lead directly to Instantly? This cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/v2/instantly/lead/${leadId}/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Sent to ${data.email}`);
            location.reload();
        } else {
            alert(`❌ Error: ${data.error}`);
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function addToQueue(leadId) {
    try {
        const response = await fetch(`/api/v2/instantly/lead/${leadId}/add-to-queue`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert('✅ Added to outreach queue');
        } else {
            alert('Already in queue or no email address');
        }
    } catch (error) {
        alert('Error: ' + error.message);
    }
}
</script>
'''
