#!/usr/bin/env python3
"""
Phase 1: Instantly.ai Integration Module
Adds qualified leads to Instantly campaigns via API
"""

import os
import requests
import json
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import sqlite3


@dataclass
class SyncResult:
    """Result of syncing a lead to Instantly"""
    lead_id: int
    email: str
    campaign_id: str
    success: bool
    error: Optional[str] = None
    response: Optional[Dict] = None


class InstantlyClient:
    """Client for Instantly.ai API V2"""
    
    BASE_URL = "https://api.instantly.ai/api/v2"
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('INSTANTLY_API_KEY')
        if not self.api_key:
            raise ValueError("INSTANTLY_API_KEY not found in environment")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def add_lead_to_campaign(
        self,
        campaign_id: str,
        email: str,
        first_name: str = '',
        last_name: str = '',
        company_name: str = '',
        custom_variables: Optional[Dict[str, str]] = None
    ) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Add a single lead to an Instantly campaign.
        
        Args:
            campaign_id: Instantly campaign ID
            email: Lead email address
            first_name: Contact first name
            last_name: Contact last name
            company_name: Business name
            custom_variables: Additional fields for personalization
        
        Returns:
            Tuple of (success: bool, response: dict, error: str)
        """
        url = f"{self.BASE_URL}/leads"
        
        payload = {
            "campaign_id": campaign_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "company_name": company_name
        }
        
        # Add custom variables if provided
        if custom_variables:
            payload["custom_variables"] = custom_variables
        
        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                return (True, response.json(), None)
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                return (False, None, error_msg)
        
        except requests.exceptions.Timeout:
            return (False, None, "Request timeout (30s)")
        except requests.exceptions.ConnectionError:
            return (False, None, "Connection error - check internet connection")
        except Exception as e:
            return (False, None, f"Unexpected error: {str(e)}")
    
    def get_campaign_leads(
        self,
        campaign_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[bool, Optional[List[Dict]], Optional[str]]:
        """
        Get leads from a campaign.
        
        Args:
            campaign_id: Instantly campaign ID
            skip: Number of leads to skip (pagination)
            limit: Max leads to return (max 100)
        
        Returns:
            Tuple of (success: bool, leads: list, error: str)
        """
        url = f"{self.BASE_URL}/leads"
        
        params = {
            "campaign_id": campaign_id,
            "skip": skip,
            "limit": min(limit, 100)  # API max is 100
        }
        
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                leads = data.get('data', [])
                return (True, leads, None)
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                return (False, None, error_msg)
        
        except Exception as e:
            return (False, None, f"Error fetching leads: {str(e)}")
    
    def check_lead_exists(
        self,
        campaign_id: str,
        email: str
    ) -> Tuple[bool, bool, Optional[str]]:
        """
        Check if a lead already exists in a campaign.
        
        Args:
            campaign_id: Instantly campaign ID
            email: Email to check
        
        Returns:
            Tuple of (success: bool, exists: bool, error: str)
        """
        success, leads, error = self.get_campaign_leads(campaign_id, limit=1000)
        
        if not success:
            return (False, False, error)
        
        # Check if email exists in campaign
        exists = any(lead.get('email', '').lower() == email.lower() for lead in leads)
        
        return (True, exists, None)


class InstantlySyncManager:
    """Manages syncing leads from database to Instantly campaigns"""
    
    def __init__(
        self,
        db_path: str = 'data/leads.db',
        api_key: Optional[str] = None
    ):
        self.db_path = db_path
        self.client = InstantlyClient(api_key)
        self.conn = None
        
        # Load campaign IDs from environment
        self.campaign_tier_a = os.getenv('INSTANTLY_CAMPAIGN_TIER_A')
        self.campaign_tier_b = os.getenv('INSTANTLY_CAMPAIGN_TIER_B')
        
        if not self.campaign_tier_a or not self.campaign_tier_b:
            raise ValueError("Campaign IDs not found. Check INSTANTLY_CAMPAIGN_TIER_A and INSTANTLY_CAMPAIGN_TIER_B in .env")
    
    def connect_db(self):
        """Connect to database"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def close_db(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        self.connect_db()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_db()
    
    def create_sync_log_table(self):
        """Create table to track Instantly sync status"""
        if not self.conn:
            raise RuntimeError("Database not connected")
        
        cursor = self.conn.cursor()
        
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
                FOREIGN KEY (lead_id) REFERENCES leads(id),
                UNIQUE(lead_id, campaign_id)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sync_log_lead
            ON instantly_sync_log(lead_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sync_log_status
            ON instantly_sync_log(sync_status)
        ''')
        
        self.conn.commit()
        print("✅ Sync log table created/verified")
    
    def sync_lead_to_campaign(
        self,
        lead_data: Dict,
        campaign_id: str,
        check_duplicates: bool = True
    ) -> SyncResult:
        """
        Sync a single lead to Instantly campaign.
        
        Args:
            lead_data: Dictionary with lead data (from InstantlyLead.to_instantly_format())
            campaign_id: Instantly campaign ID
            check_duplicates: Check if lead already exists (default: True)
        
        Returns:
            SyncResult object
        """
        email = lead_data['email']
        lead_id = int(lead_data['custom_variables']['lead_id'])
        tier = lead_data['custom_variables']['tier']
        
        # Check for duplicates if requested
        if check_duplicates:
            success, exists, error = self.client.check_lead_exists(campaign_id, email)
            
            if not success:
                return SyncResult(
                    lead_id=lead_id,
                    email=email,
                    campaign_id=campaign_id,
                    success=False,
                    error=f"Duplicate check failed: {error}"
                )
            
            if exists:
                return SyncResult(
                    lead_id=lead_id,
                    email=email,
                    campaign_id=campaign_id,
                    success=False,
                    error="Lead already exists in campaign"
                )
        
        # Add lead to campaign
        success, response, error = self.client.add_lead_to_campaign(
            campaign_id=campaign_id,
            email=email,
            first_name=lead_data.get('first_name', ''),
            last_name=lead_data.get('last_name', ''),
            company_name=lead_data.get('company_name', ''),
            custom_variables=lead_data.get('custom_variables', {})
        )
        
        # Log to database
        if self.conn:
            self._log_sync_result(
                lead_id=lead_id,
                campaign_id=campaign_id,
                email=email,
                tier=tier,
                success=success,
                error=error,
                response=response
            )
        
        return SyncResult(
            lead_id=lead_id,
            email=email,
            campaign_id=campaign_id,
            success=success,
            error=error,
            response=response
        )
    
    def _log_sync_result(
        self,
        lead_id: int,
        campaign_id: str,
        email: str,
        tier: str,
        success: bool,
        error: Optional[str],
        response: Optional[Dict]
    ):
        """Log sync result to database"""
        if not self.conn:
            return
        
        cursor = self.conn.cursor()
        
        status = 'synced' if success else 'failed'
        response_json = json.dumps(response) if response else None
        
        # Upsert (insert or update)
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
        
        self.conn.commit()
    
    def sync_batch(
        self,
        leads: List[Dict],
        campaign_id: str,
        check_duplicates: bool = True,
        rate_limit_delay: float = 0.5,
        progress_callback: Optional[callable] = None
    ) -> List[SyncResult]:
        """
        Sync a batch of leads to Instantly campaign.
        
        Args:
            leads: List of lead dictionaries (from InstantlyLead.to_instantly_format())
            campaign_id: Instantly campaign ID
            check_duplicates: Check for duplicates before syncing
            rate_limit_delay: Delay between API calls (seconds)
            progress_callback: Function to call after each lead (receives result)
        
        Returns:
            List of SyncResult objects
        """
        results = []
        total = len(leads)
        
        for i, lead_data in enumerate(leads, 1):
            result = self.sync_lead_to_campaign(
                lead_data=lead_data,
                campaign_id=campaign_id,
                check_duplicates=check_duplicates
            )
            
            results.append(result)
            
            # Progress callback
            if progress_callback:
                progress_callback(result, i, total)
            
            # Rate limiting
            if i < total and rate_limit_delay > 0:
                time.sleep(rate_limit_delay)
        
        return results
    
    def get_sync_stats(self) -> Dict:
        """Get sync statistics from database"""
        if not self.conn:
            raise RuntimeError("Database not connected")
        
        cursor = self.conn.cursor()
        
        # Total synced
        cursor.execute('''
            SELECT COUNT(*) as count FROM instantly_sync_log
            WHERE sync_status = 'synced'
        ''')
        total_synced = cursor.fetchone()['count']
        
        # Total failed
        cursor.execute('''
            SELECT COUNT(*) as count FROM instantly_sync_log
            WHERE sync_status = 'failed'
        ''')
        total_failed = cursor.fetchone()['count']
        
        # By tier
        cursor.execute('''
            SELECT tier, sync_status, COUNT(*) as count
            FROM instantly_sync_log
            GROUP BY tier, sync_status
        ''')
        
        tier_breakdown = {}
        for row in cursor.fetchall():
            tier = row['tier']
            status = row['sync_status']
            count = row['count']
            
            if tier not in tier_breakdown:
                tier_breakdown[tier] = {'synced': 0, 'failed': 0}
            
            tier_breakdown[tier][status] = count
        
        return {
            'total_synced': total_synced,
            'total_failed': total_failed,
            'tier_breakdown': tier_breakdown
        }


# Example usage and testing
if __name__ == '__main__':
    from dotenv import load_dotenv
    from phase1_lead_export import LeadExporter
    
    load_dotenv()
    
    print("=" * 70)
    print("Phase 1: Instantly Integration - Test Run")
    print("=" * 70)
    print()
    
    # Initialize sync manager
    with InstantlySyncManager() as sync_manager:
        # Create sync log table
        sync_manager.create_sync_log_table()
        print()
        
        # Export sample leads
        print("📤 Exporting test leads...")
        with LeadExporter() as exporter:
            # Get 3 Tier A leads for testing
            test_leads = exporter.export_tier_ab_for_instantly(
                tier_filter='A',
                limit=3
            )
        
        if not test_leads:
            print("❌ No leads found for testing")
            exit(1)
        
        print(f"✅ Found {len(test_leads)} test leads")
        print()
        
        # Convert to Instantly format
        leads_data = [lead.to_instantly_format() for lead in test_leads]
        
        # Get campaign ID for Tier A
        campaign_id = sync_manager.campaign_tier_a
        
        print(f"📋 Target Campaign: {campaign_id}")
        print()
        
        # Sync leads
        print("⏳ Syncing leads to Instantly...")
        print()
        
        def progress_callback(result, current, total):
            status = "✅" if result.success else "❌"
            print(f"  {status} [{current}/{total}] {result.email}")
            if not result.success:
                print(f"     Error: {result.error}")
        
        results = sync_manager.sync_batch(
            leads=leads_data,
            campaign_id=campaign_id,
            check_duplicates=True,
            rate_limit_delay=1.0,
            progress_callback=progress_callback
        )
        
        # Summary
        print()
        print("-" * 70)
        print("📊 Sync Results:")
        print()
        
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        print(f"  ✅ Successful: {len(successful)}/{len(results)}")
        print(f"  ❌ Failed: {len(failed)}/{len(results)}")
        
        if failed:
            print()
            print("  Failed leads:")
            for result in failed:
                print(f"    - {result.email}: {result.error}")
        
        # Get stats
        print()
        stats = sync_manager.get_sync_stats()
        print(f"📈 Database Stats:")
        print(f"  Total synced: {stats['total_synced']}")
        print(f"  Total failed: {stats['total_failed']}")
        print(f"  By tier: {stats['tier_breakdown']}")
        print()
    
    print("=" * 70)
    print("✅ Integration test complete!")
    print("=" * 70)
