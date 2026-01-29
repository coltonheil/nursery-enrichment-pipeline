#!/usr/bin/env python3
"""
Instantly.ai Integration Module
Complete integration for Phases 1-3:
- Phase 1: Core send functionality + API endpoints
- Phase 2: Staging area / outreach queue
- Phase 3: Webhooks + event tracking

This module provides Flask blueprints and database models for the full integration.
"""

import os
import json
import hmac
import hashlib
import requests
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from functools import wraps
from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, current_app
import threading
import time


# =============================================================================
# CONFIGURATION
# =============================================================================

class InstantlyConfig:
    """Configuration for Instantly integration"""
    
    # API Configuration
    API_KEY = os.getenv('INSTANTLY_API_KEY', '')
    BASE_URL = "https://api.instantly.ai/api/v2"
    
    # Campaign IDs
    CAMPAIGN_TIER_A = os.getenv('INSTANTLY_CAMPAIGN_TIER_A', '')
    CAMPAIGN_TIER_B = os.getenv('INSTANTLY_CAMPAIGN_TIER_B', '')
    CAMPAIGN_TIER_C = os.getenv('INSTANTLY_CAMPAIGN_TIER_C', '')  # Optional
    
    # Webhook Configuration
    WEBHOOK_SECRET = os.getenv('INSTANTLY_WEBHOOK_SECRET', '')
    WEBHOOK_URL = os.getenv('INSTANTLY_WEBHOOK_URL', '')  # Your public URL
    
    # Rate Limiting
    RATE_LIMIT_DELAY = 0.5  # Seconds between API calls
    BATCH_SIZE = 50  # Leads per batch
    
    @classmethod
    def get_campaign_for_tier(cls, tier: str) -> Optional[str]:
        """Get campaign ID for a tier"""
        mapping = {
            'A': cls.CAMPAIGN_TIER_A,
            'B': cls.CAMPAIGN_TIER_B,
            'C': cls.CAMPAIGN_TIER_C,
        }
        return mapping.get(tier.upper())
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if Instantly is properly configured"""
        return bool(cls.API_KEY and cls.CAMPAIGN_TIER_A and cls.CAMPAIGN_TIER_B)


# =============================================================================
# DATABASE MODELS
# =============================================================================

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('data/leads.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_instantly_tables():
    """Initialize all Instantly-related database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Phase 1: Sync Log Table (tracks sends to Instantly)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS instantly_sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            campaign_id TEXT NOT NULL,
            email TEXT NOT NULL,
            tier TEXT NOT NULL,
            sync_status TEXT DEFAULT 'pending',
            sync_error TEXT,
            synced_at TIMESTAMP,
            response_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            UNIQUE(lead_id, campaign_id)
        )
    ''')
    
    # Phase 2: Outreach Queue (staging area)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS outreach_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            first_name TEXT,
            last_name TEXT,
            company_name TEXT,
            tier TEXT NOT NULL,
            campaign_id TEXT,
            custom_variables TEXT,
            status TEXT DEFAULT 'pending',
            review_notes TEXT,
            reviewed_by TEXT,
            reviewed_at TIMESTAMP,
            approved_at TIMESTAMP,
            rejected_at TIMESTAMP,
            sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            UNIQUE(lead_id)
        )
    ''')
    
    # Phase 3: Event Tracking (webhooks)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS instantly_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            email TEXT NOT NULL,
            campaign_id TEXT,
            lead_id INTEGER,
            event_data TEXT,
            processed BOOLEAN DEFAULT FALSE,
            received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        )
    ''')
    
    # Phase 3: Campaign Stats (aggregated metrics)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS campaign_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,
            stat_date DATE NOT NULL,
            total_sent INTEGER DEFAULT 0,
            total_opened INTEGER DEFAULT 0,
            total_clicked INTEGER DEFAULT 0,
            total_replied INTEGER DEFAULT 0,
            total_bounced INTEGER DEFAULT 0,
            total_unsubscribed INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(campaign_id, stat_date)
        )
    ''')
    
    # Indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sync_log_lead ON instantly_sync_log(lead_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sync_log_status ON instantly_sync_log(sync_status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_queue_status ON outreach_queue(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_queue_tier ON outreach_queue(tier)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_email ON instantly_events(email)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_type ON instantly_events(event_type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_processed ON instantly_events(processed)')
    
    # Add column to leads table if not exists (for tracking Instantly status)
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN instantly_status TEXT DEFAULT NULL')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN instantly_sent_at TIMESTAMP DEFAULT NULL')
    except sqlite3.OperationalError:
        pass
    
    try:
        cursor.execute('ALTER TABLE leads ADD COLUMN instantly_campaign_id TEXT DEFAULT NULL')
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()
    
    print("✅ Instantly database tables initialized")


# =============================================================================
# INSTANTLY API CLIENT
# =============================================================================

class InstantlyAPIClient:
    """Client for Instantly.ai API V2"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or InstantlyConfig.API_KEY
        self.base_url = InstantlyConfig.BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Tuple[bool, Any, Optional[str]]:
        """Make API request with error handling"""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                timeout=30,
                **kwargs
            )
            
            if response.status_code in [200, 201]:
                return (True, response.json(), None)
            else:
                error = f"HTTP {response.status_code}: {response.text[:200]}"
                return (False, None, error)
        
        except requests.exceptions.Timeout:
            return (False, None, "Request timeout")
        except requests.exceptions.ConnectionError:
            return (False, None, "Connection error")
        except Exception as e:
            return (False, None, f"Error: {str(e)}")
    
    # Campaign Methods
    def list_campaigns(self) -> Tuple[bool, List[Dict], Optional[str]]:
        """List all campaigns"""
        success, data, error = self._request('GET', 'campaigns')
        if success:
            return (True, data.get('data', []), None)
        return (False, [], error)
    
    def get_campaign(self, campaign_id: str) -> Tuple[bool, Dict, Optional[str]]:
        """Get campaign details"""
        return self._request('GET', f'campaigns/{campaign_id}')
    
    def get_campaign_analytics(self, campaign_id: str) -> Tuple[bool, Dict, Optional[str]]:
        """Get campaign analytics"""
        return self._request('GET', f'campaigns/{campaign_id}/analytics')
    
    # Lead Methods
    def add_lead(
        self,
        campaign_id: str,
        email: str,
        first_name: str = '',
        last_name: str = '',
        company_name: str = '',
        custom_variables: Dict = None
    ) -> Tuple[bool, Dict, Optional[str]]:
        """Add a lead to a campaign"""
        payload = {
            "campaign_id": campaign_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "company_name": company_name
        }
        
        if custom_variables:
            payload["custom_variables"] = custom_variables
        
        return self._request('POST', 'leads', json=payload)
    
    def get_lead(self, email: str) -> Tuple[bool, Dict, Optional[str]]:
        """Get lead by email"""
        return self._request('GET', f'leads/{email}')
    
    def list_campaign_leads(self, campaign_id: str, skip: int = 0, limit: int = 100) -> Tuple[bool, List[Dict], Optional[str]]:
        """List leads in a campaign"""
        success, data, error = self._request(
            'GET', 'leads',
            params={'campaign_id': campaign_id, 'skip': skip, 'limit': min(limit, 100)}
        )
        if success:
            return (True, data.get('data', []), None)
        return (False, [], error)
    
    # Webhook Methods
    def list_webhooks(self) -> Tuple[bool, List[Dict], Optional[str]]:
        """List configured webhooks"""
        success, data, error = self._request('GET', 'webhooks')
        if success:
            return (True, data.get('data', []), None)
        return (False, [], error)
    
    def create_webhook(self, url: str, events: List[str]) -> Tuple[bool, Dict, Optional[str]]:
        """Create a webhook"""
        payload = {
            "url": url,
            "events": events
        }
        return self._request('POST', 'webhooks', json=payload)
    
    def delete_webhook(self, webhook_id: str) -> Tuple[bool, Dict, Optional[str]]:
        """Delete a webhook"""
        return self._request('DELETE', f'webhooks/{webhook_id}')


# =============================================================================
# PHASE 1: CORE INTEGRATION
# =============================================================================

@dataclass
class LeadSendResult:
    """Result of sending a lead to Instantly"""
    lead_id: int
    email: str
    campaign_id: str
    success: bool
    error: Optional[str] = None


class InstantlySender:
    """Core sender for Phase 1"""
    
    def __init__(self):
        self.client = InstantlyAPIClient()
    
    def get_lead_data(self, lead_id: int) -> Optional[Dict]:
        """Get lead data from database"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                id, business_name, city, state, phone, website,
                owner_name, owner_email, contact_email, business_type,
                tier, tier_override, score
            FROM leads
            WHERE id = ?
        ''', (lead_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def format_lead_for_instantly(self, lead: Dict) -> Dict:
        """Format lead data for Instantly API"""
        # Determine email
        email = lead.get('contact_email') or lead.get('owner_email')
        if not email:
            return None
        
        # Parse name
        owner_name = lead.get('owner_name') or ''
        name_parts = owner_name.strip().split()
        first_name = name_parts[0] if name_parts else 'Owner'
        last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
        
        # Determine tier
        tier = lead.get('tier_override') or lead.get('tier') or 'B'
        
        return {
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'company_name': lead.get('business_name', ''),
            'custom_variables': {
                'city': lead.get('city') or '',
                'state': lead.get('state') or '',
                'business_type': lead.get('business_type') or 'Nursery',
                'tier': tier,
                'score': str(lead.get('score') or 0),
                'phone': lead.get('phone') or '',
                'website': lead.get('website') or '',
                'lead_id': str(lead.get('id'))
            },
            'tier': tier,
            'lead_id': lead.get('id')
        }
    
    def send_lead(self, lead_id: int, campaign_id: str = None) -> LeadSendResult:
        """Send a single lead to Instantly"""
        # Get lead data
        lead = self.get_lead_data(lead_id)
        if not lead:
            return LeadSendResult(
                lead_id=lead_id,
                email='',
                campaign_id='',
                success=False,
                error="Lead not found"
            )
        
        # Format for Instantly
        formatted = self.format_lead_for_instantly(lead)
        if not formatted:
            return LeadSendResult(
                lead_id=lead_id,
                email='',
                campaign_id='',
                success=False,
                error="No email address"
            )
        
        # Determine campaign
        if not campaign_id:
            campaign_id = InstantlyConfig.get_campaign_for_tier(formatted['tier'])
        
        if not campaign_id:
            return LeadSendResult(
                lead_id=lead_id,
                email=formatted['email'],
                campaign_id='',
                success=False,
                error=f"No campaign configured for tier {formatted['tier']}"
            )
        
        # Send to Instantly
        success, response, error = self.client.add_lead(
            campaign_id=campaign_id,
            email=formatted['email'],
            first_name=formatted['first_name'],
            last_name=formatted['last_name'],
            company_name=formatted['company_name'],
            custom_variables=formatted['custom_variables']
        )
        
        # Log to database
        self._log_send(
            lead_id=lead_id,
            email=formatted['email'],
            campaign_id=campaign_id,
            tier=formatted['tier'],
            success=success,
            error=error,
            response=response
        )
        
        # Update lead status
        if success:
            self._update_lead_status(lead_id, campaign_id)
        
        return LeadSendResult(
            lead_id=lead_id,
            email=formatted['email'],
            campaign_id=campaign_id,
            success=success,
            error=error
        )
    
    def send_batch(
        self,
        lead_ids: List[int],
        campaign_id: str = None,
        progress_callback: callable = None
    ) -> List[LeadSendResult]:
        """Send multiple leads to Instantly"""
        results = []
        total = len(lead_ids)
        
        for i, lead_id in enumerate(lead_ids, 1):
            result = self.send_lead(lead_id, campaign_id)
            results.append(result)
            
            if progress_callback:
                progress_callback(result, i, total)
            
            # Rate limiting
            if i < total:
                time.sleep(InstantlyConfig.RATE_LIMIT_DELAY)
        
        return results
    
    def _log_send(
        self,
        lead_id: int,
        email: str,
        campaign_id: str,
        tier: str,
        success: bool,
        error: Optional[str],
        response: Optional[Dict]
    ):
        """Log send attempt to database"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        status = 'synced' if success else 'failed'
        response_json = json.dumps(response) if response else None
        
        cursor.execute('''
            INSERT INTO instantly_sync_log (
                lead_id, campaign_id, email, tier, sync_status,
                sync_error, synced_at, response_data
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lead_id, campaign_id) DO UPDATE SET
                sync_status = excluded.sync_status,
                sync_error = excluded.sync_error,
                synced_at = excluded.synced_at,
                response_data = excluded.response_data
        ''', (
            lead_id, campaign_id, email, tier, status,
            error, datetime.now().isoformat(), response_json
        ))
        
        conn.commit()
        conn.close()
    
    def _update_lead_status(self, lead_id: int, campaign_id: str):
        """Update lead status after successful send"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE leads
            SET instantly_status = 'sent',
                instantly_sent_at = ?,
                instantly_campaign_id = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), campaign_id, lead_id))
        
        conn.commit()
        conn.close()


# =============================================================================
# PHASE 2: OUTREACH QUEUE (STAGING AREA)
# =============================================================================

class OutreachQueue:
    """Staging area for lead review before sending"""
    
    @staticmethod
    def add_to_queue(lead_ids: List[int], auto_assign_campaign: bool = True) -> Tuple[int, int]:
        """
        Add leads to the outreach queue for review.
        Returns (added_count, skipped_count)
        """
        conn = get_db_connection()
        cursor = conn.cursor()
        
        added = 0
        skipped = 0
        sender = InstantlySender()
        
        for lead_id in lead_ids:
            # Get lead data
            lead = sender.get_lead_data(lead_id)
            if not lead:
                skipped += 1
                continue
            
            # Format for queue
            formatted = sender.format_lead_for_instantly(lead)
            if not formatted:
                skipped += 1
                continue
            
            # Determine campaign
            campaign_id = None
            if auto_assign_campaign:
                campaign_id = InstantlyConfig.get_campaign_for_tier(formatted['tier'])
            
            try:
                cursor.execute('''
                    INSERT INTO outreach_queue (
                        lead_id, email, first_name, last_name, company_name,
                        tier, campaign_id, custom_variables, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                ''', (
                    lead_id,
                    formatted['email'],
                    formatted['first_name'],
                    formatted['last_name'],
                    formatted['company_name'],
                    formatted['tier'],
                    campaign_id,
                    json.dumps(formatted['custom_variables'])
                ))
                added += 1
            except sqlite3.IntegrityError:
                # Already in queue
                skipped += 1
        
        conn.commit()
        conn.close()
        
        return (added, skipped)
    
    @staticmethod
    def get_queue(
        status: str = None,
        tier: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict], int]:
        """Get queue items with filters"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build WHERE clause
        conditions = []
        params = []
        
        if status:
            conditions.append('status = ?')
            params.append(status)
        
        if tier:
            conditions.append('tier = ?')
            params.append(tier)
        
        where_clause = ' AND '.join(conditions) if conditions else '1=1'
        
        # Get count
        cursor.execute(f'SELECT COUNT(*) as count FROM outreach_queue WHERE {where_clause}', params)
        total = cursor.fetchone()['count']
        
        # Get items
        cursor.execute(f'''
            SELECT q.*, l.website, l.phone as lead_phone, l.score
            FROM outreach_queue q
            LEFT JOIN leads l ON q.lead_id = l.id
            WHERE {where_clause}
            ORDER BY q.tier ASC, q.created_at DESC
            LIMIT ? OFFSET ?
        ''', params + [limit, offset])
        
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return (items, total)
    
    @staticmethod
    def approve_items(item_ids: List[int], reviewed_by: str = None) -> int:
        """Approve queue items for sending"""
        if not item_ids:
            return 0
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(item_ids))
        cursor.execute(f'''
            UPDATE outreach_queue
            SET status = 'approved',
                approved_at = ?,
                reviewed_by = ?,
                reviewed_at = ?
            WHERE id IN ({placeholders}) AND status = 'pending'
        ''', [datetime.now().isoformat(), reviewed_by, datetime.now().isoformat()] + item_ids)
        
        updated = cursor.rowcount
        conn.commit()
        conn.close()
        
        return updated
    
    @staticmethod
    def reject_items(item_ids: List[int], reviewed_by: str = None, notes: str = None) -> int:
        """Reject queue items"""
        if not item_ids:
            return 0
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join(['?'] * len(item_ids))
        cursor.execute(f'''
            UPDATE outreach_queue
            SET status = 'rejected',
                rejected_at = ?,
                reviewed_by = ?,
                reviewed_at = ?,
                review_notes = ?
            WHERE id IN ({placeholders}) AND status = 'pending'
        ''', [datetime.now().isoformat(), reviewed_by, datetime.now().isoformat(), notes] + item_ids)
        
        updated = cursor.rowcount
        conn.commit()
        conn.close()
        
        return updated
    
    @staticmethod
    def update_item(
        item_id: int,
        email: str = None,
        first_name: str = None,
        last_name: str = None,
        campaign_id: str = None,
        notes: str = None
    ) -> bool:
        """Update a queue item"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if email:
            updates.append('email = ?')
            params.append(email)
        if first_name:
            updates.append('first_name = ?')
            params.append(first_name)
        if last_name:
            updates.append('last_name = ?')
            params.append(last_name)
        if campaign_id:
            updates.append('campaign_id = ?')
            params.append(campaign_id)
        if notes is not None:
            updates.append('review_notes = ?')
            params.append(notes)
        
        if not updates:
            return False
        
        params.append(item_id)
        cursor.execute(f'''
            UPDATE outreach_queue
            SET {', '.join(updates)}
            WHERE id = ?
        ''', params)
        
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return updated
    
    @staticmethod
    def send_approved() -> Tuple[int, int, List[str]]:
        """Send all approved items to Instantly. Returns (sent, failed, errors)"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get approved items
        cursor.execute('''
            SELECT * FROM outreach_queue
            WHERE status = 'approved'
            ORDER BY tier ASC, created_at ASC
        ''')
        
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not items:
            return (0, 0, [])
        
        sender = InstantlySender()
        sent = 0
        failed = 0
        errors = []
        
        for item in items:
            result = sender.send_lead(item['lead_id'], item['campaign_id'])
            
            # Update queue status
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if result.success:
                cursor.execute('''
                    UPDATE outreach_queue
                    SET status = 'sent', sent_at = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(), item['id']))
                sent += 1
            else:
                cursor.execute('''
                    UPDATE outreach_queue
                    SET status = 'failed', review_notes = ?
                    WHERE id = ?
                ''', (f"Send error: {result.error}", item['id']))
                failed += 1
                errors.append(f"{item['email']}: {result.error}")
            
            conn.commit()
            conn.close()
            
            # Rate limiting
            time.sleep(InstantlyConfig.RATE_LIMIT_DELAY)
        
        return (sent, failed, errors)
    
    @staticmethod
    def get_queue_stats() -> Dict:
        """Get queue statistics"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                status,
                tier,
                COUNT(*) as count
            FROM outreach_queue
            GROUP BY status, tier
        ''')
        
        results = cursor.fetchall()
        conn.close()
        
        stats = {
            'by_status': {},
            'by_tier': {},
            'total': 0
        }
        
        for row in results:
            status = row['status']
            tier = row['tier']
            count = row['count']
            
            if status not in stats['by_status']:
                stats['by_status'][status] = 0
            stats['by_status'][status] += count
            
            if tier not in stats['by_tier']:
                stats['by_tier'][tier] = 0
            stats['by_tier'][tier] += count
            
            stats['total'] += count
        
        return stats


# =============================================================================
# PHASE 3: WEBHOOKS & EVENT TRACKING
# =============================================================================

class InstantlyEventHandler:
    """Handle incoming Instantly webhook events"""
    
    # Event types
    EVENT_TYPES = [
        'email.sent',
        'email.opened',
        'email.clicked',
        'email.replied',
        'email.bounced',
        'email.unsubscribed',
        'lead.interested',
        'lead.not_interested',
        'lead.meeting_booked',
        'lead.meeting_completed',
        'lead.out_of_office'
    ]
    
    @classmethod
    def verify_webhook(cls, payload: bytes, signature: str) -> bool:
        """Verify webhook signature (if configured)"""
        if not InstantlyConfig.WEBHOOK_SECRET:
            return True  # Skip verification if no secret configured
        
        expected = hmac.new(
            InstantlyConfig.WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    
    @classmethod
    def process_event(cls, event_data: Dict) -> bool:
        """Process an incoming webhook event"""
        event_type = event_data.get('event_type') or event_data.get('type')
        email = event_data.get('email') or event_data.get('lead', {}).get('email')
        campaign_id = event_data.get('campaign_id')
        
        if not event_type or not email:
            return False
        
        # Find lead_id by email
        lead_id = cls._find_lead_by_email(email)
        
        # Store event
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO instantly_events (
                event_type, email, campaign_id, lead_id, event_data
            )
            VALUES (?, ?, ?, ?, ?)
        ''', (
            event_type,
            email,
            campaign_id,
            lead_id,
            json.dumps(event_data)
        ))
        
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Process event (update stats, trigger actions)
        cls._handle_event(event_id, event_type, email, lead_id, event_data)
        
        return True
    
    @classmethod
    def _find_lead_by_email(cls, email: str) -> Optional[int]:
        """Find lead ID by email"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id FROM leads
            WHERE owner_email = ? OR contact_email = ?
            LIMIT 1
        ''', (email, email))
        
        row = cursor.fetchone()
        conn.close()
        
        return row['id'] if row else None
    
    @classmethod
    def _handle_event(
        cls,
        event_id: int,
        event_type: str,
        email: str,
        lead_id: Optional[int],
        event_data: Dict
    ):
        """Handle specific event types"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update lead status based on event
        if lead_id:
            status_mapping = {
                'email.replied': 'replied',
                'email.bounced': 'bounced',
                'email.unsubscribed': 'unsubscribed',
                'lead.interested': 'interested',
                'lead.meeting_booked': 'meeting_booked',
            }
            
            if event_type in status_mapping:
                cursor.execute('''
                    UPDATE leads
                    SET instantly_status = ?
                    WHERE id = ?
                ''', (status_mapping[event_type], lead_id))
        
        # Update campaign stats
        campaign_id = event_data.get('campaign_id')
        if campaign_id:
            today = datetime.now().date().isoformat()
            
            # Ensure stats row exists
            cursor.execute('''
                INSERT OR IGNORE INTO campaign_stats (campaign_id, stat_date)
                VALUES (?, ?)
            ''', (campaign_id, today))
            
            # Update appropriate counter
            stat_mapping = {
                'email.sent': 'total_sent',
                'email.opened': 'total_opened',
                'email.clicked': 'total_clicked',
                'email.replied': 'total_replied',
                'email.bounced': 'total_bounced',
                'email.unsubscribed': 'total_unsubscribed',
            }
            
            if event_type in stat_mapping:
                column = stat_mapping[event_type]
                cursor.execute(f'''
                    UPDATE campaign_stats
                    SET {column} = {column} + 1, updated_at = ?
                    WHERE campaign_id = ? AND stat_date = ?
                ''', (datetime.now().isoformat(), campaign_id, today))
        
        # Mark event as processed
        cursor.execute('''
            UPDATE instantly_events
            SET processed = TRUE, processed_at = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), event_id))
        
        conn.commit()
        conn.close()
    
    @classmethod
    def get_hot_leads(cls, limit: int = 50) -> List[Dict]:
        """Get leads that have replied or shown interest"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT l.*, e.event_type, e.received_at as event_time
            FROM leads l
            JOIN instantly_events e ON e.lead_id = l.id
            WHERE e.event_type IN ('email.replied', 'lead.interested', 'lead.meeting_booked')
            ORDER BY e.received_at DESC
            LIMIT ?
        ''', (limit,))
        
        leads = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return leads
    
    @classmethod
    def get_campaign_stats(cls, campaign_id: str = None, days: int = 30) -> List[Dict]:
        """Get campaign statistics"""
        conn = get_db_connection()
        cursor = conn.cursor()
        
        start_date = (datetime.now() - timedelta(days=days)).date().isoformat()
        
        if campaign_id:
            cursor.execute('''
                SELECT * FROM campaign_stats
                WHERE campaign_id = ? AND stat_date >= ?
                ORDER BY stat_date DESC
            ''', (campaign_id, start_date))
        else:
            cursor.execute('''
                SELECT 
                    campaign_id,
                    SUM(total_sent) as total_sent,
                    SUM(total_opened) as total_opened,
                    SUM(total_clicked) as total_clicked,
                    SUM(total_replied) as total_replied,
                    SUM(total_bounced) as total_bounced,
                    SUM(total_unsubscribed) as total_unsubscribed
                FROM campaign_stats
                WHERE stat_date >= ?
                GROUP BY campaign_id
            ''', (start_date,))
        
        stats = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return stats
    
    @classmethod
    def setup_webhooks(cls, base_url: str) -> Tuple[bool, str]:
        """Setup webhooks in Instantly"""
        client = InstantlyAPIClient()
        
        webhook_url = f"{base_url}/api/v2/instantly/webhook"
        events = cls.EVENT_TYPES
        
        success, response, error = client.create_webhook(webhook_url, events)
        
        if success:
            return (True, f"Webhook created: {response.get('id')}")
        else:
            return (False, f"Failed to create webhook: {error}")


# =============================================================================
# FLASK BLUEPRINT
# =============================================================================

instantly_bp = Blueprint('instantly', __name__, url_prefix='/api/v2/instantly')


# Middleware for API authentication (optional)
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # For now, no auth required - add if needed
        return f(*args, **kwargs)
    return decorated


# ----- Phase 1 Endpoints -----

@instantly_bp.route('/status', methods=['GET'])
def get_status():
    """Get Instantly integration status"""
    return jsonify({
        'configured': InstantlyConfig.is_configured(),
        'api_key_set': bool(InstantlyConfig.API_KEY),
        'campaign_tier_a': InstantlyConfig.CAMPAIGN_TIER_A[:8] + '...' if InstantlyConfig.CAMPAIGN_TIER_A else None,
        'campaign_tier_b': InstantlyConfig.CAMPAIGN_TIER_B[:8] + '...' if InstantlyConfig.CAMPAIGN_TIER_B else None,
        'campaign_tier_c': InstantlyConfig.CAMPAIGN_TIER_C[:8] + '...' if InstantlyConfig.CAMPAIGN_TIER_C else None,
    })


@instantly_bp.route('/send', methods=['POST'])
@require_api_key
def send_leads():
    """Send leads to Instantly"""
    data = request.get_json()
    
    lead_ids = data.get('lead_ids', [])
    campaign_id = data.get('campaign_id')  # Optional override
    
    if not lead_ids:
        return jsonify({'error': 'No lead_ids provided'}), 400
    
    if not InstantlyConfig.is_configured():
        return jsonify({'error': 'Instantly not configured'}), 500
    
    sender = InstantlySender()
    results = sender.send_batch(lead_ids, campaign_id)
    
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]
    
    return jsonify({
        'success': True,
        'sent': len(successful),
        'failed': len(failed),
        'results': [asdict(r) for r in results]
    })


@instantly_bp.route('/send/<int:lead_id>', methods=['POST'])
@require_api_key
def send_single_lead(lead_id: int):
    """Send a single lead to Instantly"""
    data = request.get_json() or {}
    campaign_id = data.get('campaign_id')
    
    if not InstantlyConfig.is_configured():
        return jsonify({'error': 'Instantly not configured'}), 500
    
    sender = InstantlySender()
    result = sender.send_lead(lead_id, campaign_id)
    
    return jsonify({
        'success': result.success,
        'lead_id': result.lead_id,
        'email': result.email,
        'campaign_id': result.campaign_id,
        'error': result.error
    })


@instantly_bp.route('/campaigns', methods=['GET'])
def list_campaigns():
    """List Instantly campaigns"""
    if not InstantlyConfig.is_configured():
        return jsonify({'error': 'Instantly not configured'}), 500
    
    client = InstantlyAPIClient()
    success, campaigns, error = client.list_campaigns()
    
    if success:
        return jsonify({'campaigns': campaigns})
    else:
        return jsonify({'error': error}), 500


@instantly_bp.route('/sync-stats', methods=['GET'])
def get_sync_stats():
    """Get sync statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            sync_status,
            tier,
            COUNT(*) as count
        FROM instantly_sync_log
        GROUP BY sync_status, tier
    ''')
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'stats': results})


# ----- Phase 2 Endpoints -----

@instantly_bp.route('/queue', methods=['GET'])
def get_queue():
    """Get outreach queue"""
    status = request.args.get('status')
    tier = request.args.get('tier')
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    items, total = OutreachQueue.get_queue(status, tier, limit, offset)
    
    return jsonify({
        'items': items,
        'total': total,
        'limit': limit,
        'offset': offset
    })


@instantly_bp.route('/queue', methods=['POST'])
@require_api_key
def add_to_queue():
    """Add leads to outreach queue"""
    data = request.get_json()
    lead_ids = data.get('lead_ids', [])
    
    if not lead_ids:
        return jsonify({'error': 'No lead_ids provided'}), 400
    
    added, skipped = OutreachQueue.add_to_queue(lead_ids)
    
    return jsonify({
        'success': True,
        'added': added,
        'skipped': skipped
    })


@instantly_bp.route('/queue/approve', methods=['POST'])
@require_api_key
def approve_queue_items():
    """Approve queue items"""
    data = request.get_json()
    item_ids = data.get('item_ids', [])
    reviewed_by = data.get('reviewed_by', 'system')
    
    if not item_ids:
        return jsonify({'error': 'No item_ids provided'}), 400
    
    updated = OutreachQueue.approve_items(item_ids, reviewed_by)
    
    return jsonify({
        'success': True,
        'approved': updated
    })


@instantly_bp.route('/queue/reject', methods=['POST'])
@require_api_key
def reject_queue_items():
    """Reject queue items"""
    data = request.get_json()
    item_ids = data.get('item_ids', [])
    reviewed_by = data.get('reviewed_by', 'system')
    notes = data.get('notes')
    
    if not item_ids:
        return jsonify({'error': 'No item_ids provided'}), 400
    
    updated = OutreachQueue.reject_items(item_ids, reviewed_by, notes)
    
    return jsonify({
        'success': True,
        'rejected': updated
    })


@instantly_bp.route('/queue/<int:item_id>', methods=['PUT'])
@require_api_key
def update_queue_item(item_id: int):
    """Update a queue item"""
    data = request.get_json()
    
    updated = OutreachQueue.update_item(
        item_id,
        email=data.get('email'),
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        campaign_id=data.get('campaign_id'),
        notes=data.get('notes')
    )
    
    return jsonify({'success': updated})


@instantly_bp.route('/queue/send-approved', methods=['POST'])
@require_api_key
def send_approved_queue():
    """Send all approved items to Instantly"""
    sent, failed, errors = OutreachQueue.send_approved()
    
    return jsonify({
        'success': True,
        'sent': sent,
        'failed': failed,
        'errors': errors
    })


@instantly_bp.route('/queue/stats', methods=['GET'])
def get_queue_stats():
    """Get queue statistics"""
    stats = OutreachQueue.get_queue_stats()
    return jsonify(stats)


# ----- Phase 3 Endpoints -----

@instantly_bp.route('/webhook', methods=['POST'])
def receive_webhook():
    """Receive Instantly webhook events"""
    # Verify signature if configured
    signature = request.headers.get('X-Instantly-Signature', '')
    
    if not InstantlyEventHandler.verify_webhook(request.data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    event_data = request.get_json()
    
    if not event_data:
        return jsonify({'error': 'No event data'}), 400
    
    processed = InstantlyEventHandler.process_event(event_data)
    
    return jsonify({'processed': processed})


@instantly_bp.route('/events', methods=['GET'])
def get_events():
    """Get recent events"""
    limit = request.args.get('limit', 100, type=int)
    event_type = request.args.get('type')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if event_type:
        cursor.execute('''
            SELECT * FROM instantly_events
            WHERE event_type = ?
            ORDER BY received_at DESC
            LIMIT ?
        ''', (event_type, limit))
    else:
        cursor.execute('''
            SELECT * FROM instantly_events
            ORDER BY received_at DESC
            LIMIT ?
        ''', (limit,))
    
    events = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'events': events})


@instantly_bp.route('/hot-leads', methods=['GET'])
def get_hot_leads():
    """Get leads that have replied or shown interest"""
    limit = request.args.get('limit', 50, type=int)
    leads = InstantlyEventHandler.get_hot_leads(limit)
    
    return jsonify({'leads': leads})


@instantly_bp.route('/campaign-stats', methods=['GET'])
def get_campaign_stats():
    """Get campaign statistics"""
    campaign_id = request.args.get('campaign_id')
    days = request.args.get('days', 30, type=int)
    
    stats = InstantlyEventHandler.get_campaign_stats(campaign_id, days)
    
    return jsonify({'stats': stats})


@instantly_bp.route('/setup-webhooks', methods=['POST'])
@require_api_key
def setup_webhooks():
    """Setup Instantly webhooks"""
    data = request.get_json()
    base_url = data.get('base_url')
    
    if not base_url:
        return jsonify({'error': 'base_url required'}), 400
    
    success, message = InstantlyEventHandler.setup_webhooks(base_url)
    
    return jsonify({
        'success': success,
        'message': message
    })


# =============================================================================
# INITIALIZATION
# =============================================================================

def init_instantly_integration(app):
    """Initialize Instantly integration with Flask app"""
    # Register blueprint
    app.register_blueprint(instantly_bp)
    
    # Initialize database tables
    with app.app_context():
        init_instantly_tables()
    
    print("✅ Instantly integration initialized")
    print(f"   API Key: {'✓' if InstantlyConfig.API_KEY else '✗'}")
    print(f"   Campaign Tier A: {'✓' if InstantlyConfig.CAMPAIGN_TIER_A else '✗'}")
    print(f"   Campaign Tier B: {'✓' if InstantlyConfig.CAMPAIGN_TIER_B else '✗'}")


# For testing
if __name__ == '__main__':
    print("Instantly Integration Module")
    print("=" * 50)
    print(f"Configured: {InstantlyConfig.is_configured()}")
    print(f"API Key: {'Set' if InstantlyConfig.API_KEY else 'Not set'}")
    print(f"Campaign Tier A: {InstantlyConfig.CAMPAIGN_TIER_A[:20]}..." if InstantlyConfig.CAMPAIGN_TIER_A else "Not set")
    print(f"Campaign Tier B: {InstantlyConfig.CAMPAIGN_TIER_B[:20]}..." if InstantlyConfig.CAMPAIGN_TIER_B else "Not set")
