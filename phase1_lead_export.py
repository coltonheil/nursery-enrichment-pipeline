#!/usr/bin/env python3
"""
Phase 1: Lead Export Module
Extracts Tier A/B leads with contact info and formats for Instantly.ai campaigns
"""

import sqlite3
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
import os


@dataclass
class InstantlyLead:
    """Structured lead data for Instantly.ai API"""
    email: str
    first_name: str
    last_name: str
    company_name: str
    
    # Custom variables for personalization
    city: str
    state: str
    business_type: Optional[str] = None
    tier: str = 'B'
    score: int = 0
    phone: Optional[str] = None
    website: Optional[str] = None
    
    # Internal tracking
    lead_id: int = 0
    email_source: str = 'owner'  # 'owner' or 'contact'
    
    def to_instantly_format(self) -> Dict:
        """Convert to Instantly API format"""
        return {
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'company_name': self.company_name,
            'custom_variables': {
                'city': self.city,
                'state': self.state,
                'business_type': self.business_type or 'Nursery',
                'tier': self.tier,
                'score': str(self.score),
                'phone': self.phone or '',
                'website': self.website or '',
                'lead_id': str(self.lead_id)
            }
        }


class LeadExporter:
    """Export qualified leads from database for Instantly campaigns"""
    
    def __init__(self, db_path: str = 'data/leads.db'):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def parse_contact_name(self, name: Optional[str]) -> Tuple[str, str]:
        """
        Parse contact name into first and last name.
        
        Returns:
            tuple: (first_name, last_name)
        """
        if not name or name.strip() == '':
            return ('', '')
        
        # Remove common titles
        name = name.strip()
        for title in ['Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.']:
            if name.startswith(title):
                name = name[len(title):].strip()
        
        parts = name.split()
        
        if len(parts) == 0:
            return ('', '')
        elif len(parts) == 1:
            return (parts[0], '')
        else:
            # First part is first name, everything else is last name
            return (parts[0], ' '.join(parts[1:]))
    
    def get_tier_ab_leads(
        self,
        tier_filter: str = 'AB',
        require_email: bool = True,
        limit: Optional[int] = None
    ) -> List[sqlite3.Row]:
        """
        Get Tier A/B leads from database.
        
        Args:
            tier_filter: 'A', 'B', or 'AB' (default: 'AB')
            require_email: Only return leads with email addresses (default: True)
            limit: Maximum number of leads to return (default: None = all)
        
        Returns:
            List of lead rows from database
        """
        if not self.conn:
            raise RuntimeError("Database not connected. Use 'with LeadExporter()' or call connect() first.")
        
        # Build tier filter
        tiers = list(tier_filter.upper())
        tier_placeholders = ','.join(['?'] * len(tiers))
        
        # Build query
        query = f'''
            SELECT 
                id,
                business_name,
                city,
                state,
                phone,
                website,
                owner_name,
                owner_email,
                contact_email,
                business_type,
                tier,
                score,
                tier_override
            FROM leads
            WHERE COALESCE(tier_override, tier) IN ({tier_placeholders})
        '''
        
        params = tiers
        
        if require_email:
            query += ' AND (owner_email IS NOT NULL AND owner_email != "") OR (contact_email IS NOT NULL AND contact_email != "")'
        
        query += ' ORDER BY COALESCE(tier_override, tier) ASC, score DESC'
        
        if limit:
            query += ' LIMIT ?'
            params.append(limit)
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        
        return cursor.fetchall()
    
    def convert_to_instantly_leads(
        self,
        leads: List[sqlite3.Row],
        prefer_contact_email: bool = True
    ) -> List[InstantlyLead]:
        """
        Convert database leads to Instantly lead format.
        
        Args:
            leads: List of lead rows from database
            prefer_contact_email: Prefer contact_email over owner_email when both exist
        
        Returns:
            List of InstantlyLead objects
        """
        instantly_leads = []
        
        for lead in leads:
            # Determine which email to use
            email = None
            email_source = None
            contact_name = None
            
            if prefer_contact_email and lead['contact_email']:
                email = lead['contact_email']
                email_source = 'contact'
                contact_name = lead['owner_name']  # Use owner_name as fallback
            elif lead['owner_email']:
                email = lead['owner_email']
                email_source = 'owner'
                contact_name = lead['owner_name']
            elif lead['contact_email']:
                email = lead['contact_email']
                email_source = 'contact'
                contact_name = lead['owner_name']
            
            if not email:
                continue  # Skip leads without email
            
            # Parse contact name
            first_name, last_name = self.parse_contact_name(contact_name)
            
            # Fallback if no name parsed
            if not first_name:
                first_name = 'Owner'
                last_name = ''
            
            # Create Instantly lead
            instantly_lead = InstantlyLead(
                email=email,
                first_name=first_name,
                last_name=last_name,
                company_name=lead['business_name'],
                city=lead['city'] or '',
                state=lead['state'] or '',
                business_type=lead['business_type'],
                tier=lead['tier_override'] or lead['tier'],
                score=lead['score'] or 0,
                phone=lead['phone'],
                website=lead['website'],
                lead_id=lead['id'],
                email_source=email_source
            )
            
            instantly_leads.append(instantly_lead)
        
        return instantly_leads
    
    def export_tier_ab_for_instantly(
        self,
        tier_filter: str = 'AB',
        prefer_contact_email: bool = True,
        limit: Optional[int] = None
    ) -> List[InstantlyLead]:
        """
        Complete export pipeline: DB → Instantly format.
        
        Args:
            tier_filter: 'A', 'B', or 'AB'
            prefer_contact_email: Prefer contact_email over owner_email
            limit: Max leads to export
        
        Returns:
            List of InstantlyLead objects ready for API
        """
        # Get leads from DB
        db_leads = self.get_tier_ab_leads(
            tier_filter=tier_filter,
            require_email=True,
            limit=limit
        )
        
        # Convert to Instantly format
        instantly_leads = self.convert_to_instantly_leads(
            db_leads,
            prefer_contact_email=prefer_contact_email
        )
        
        return instantly_leads
    
    def get_export_stats(self, tier_filter: str = 'AB') -> Dict:
        """
        Get statistics about exportable leads.
        
        Args:
            tier_filter: 'A', 'B', or 'AB'
        
        Returns:
            Dictionary with export stats
        """
        if not self.conn:
            raise RuntimeError("Database not connected")
        
        tiers = list(tier_filter.upper())
        tier_placeholders = ','.join(['?'] * len(tiers))
        
        cursor = self.conn.cursor()
        
        # Total leads in tier
        cursor.execute(f'''
            SELECT COUNT(*) as count
            FROM leads
            WHERE COALESCE(tier_override, tier) IN ({tier_placeholders})
        ''', tiers)
        total_in_tier = cursor.fetchone()['count']
        
        # Leads with owner_email
        cursor.execute(f'''
            SELECT COUNT(*) as count
            FROM leads
            WHERE COALESCE(tier_override, tier) IN ({tier_placeholders})
              AND owner_email IS NOT NULL AND owner_email != ''
        ''', tiers)
        with_owner_email = cursor.fetchone()['count']
        
        # Leads with contact_email
        cursor.execute(f'''
            SELECT COUNT(*) as count
            FROM leads
            WHERE COALESCE(tier_override, tier) IN ({tier_placeholders})
              AND contact_email IS NOT NULL AND contact_email != ''
        ''', tiers)
        with_contact_email = cursor.fetchone()['count']
        
        # Leads with either email
        cursor.execute(f'''
            SELECT COUNT(*) as count
            FROM leads
            WHERE COALESCE(tier_override, tier) IN ({tier_placeholders})
              AND ((owner_email IS NOT NULL AND owner_email != '')
                   OR (contact_email IS NOT NULL AND contact_email != ''))
        ''', tiers)
        total_contactable = cursor.fetchone()['count']
        
        # Breakdown by tier
        cursor.execute(f'''
            SELECT 
                COALESCE(tier_override, tier) as tier,
                COUNT(*) as count
            FROM leads
            WHERE COALESCE(tier_override, tier) IN ({tier_placeholders})
              AND ((owner_email IS NOT NULL AND owner_email != '')
                   OR (contact_email IS NOT NULL AND contact_email != ''))
            GROUP BY COALESCE(tier_override, tier)
        ''', tiers)
        
        tier_breakdown = {}
        for row in cursor.fetchall():
            tier_breakdown[row['tier']] = row['count']
        
        return {
            'tier_filter': tier_filter,
            'total_in_tier': total_in_tier,
            'with_owner_email': with_owner_email,
            'with_contact_email': with_contact_email,
            'total_contactable': total_contactable,
            'contactable_rate': round(total_contactable / total_in_tier * 100, 1) if total_in_tier > 0 else 0,
            'tier_breakdown': tier_breakdown
        }


# Example usage and testing
if __name__ == '__main__':
    print("=" * 70)
    print("Phase 1: Lead Export - Test Run")
    print("=" * 70)
    print()
    
    with LeadExporter() as exporter:
        # Get stats
        print("📊 Export Statistics:")
        print()
        
        stats_ab = exporter.get_export_stats('AB')
        print(f"Tier A+B Combined:")
        print(f"  Total leads: {stats_ab['total_in_tier']}")
        print(f"  With owner email: {stats_ab['with_owner_email']}")
        print(f"  With contact email: {stats_ab['with_contact_email']}")
        print(f"  Total contactable: {stats_ab['total_contactable']} ({stats_ab['contactable_rate']}%)")
        print(f"  Breakdown: {stats_ab['tier_breakdown']}")
        print()
        
        stats_a = exporter.get_export_stats('A')
        print(f"Tier A Only:")
        print(f"  Total leads: {stats_a['total_in_tier']}")
        print(f"  Contactable: {stats_a['total_contactable']} ({stats_a['contactable_rate']}%)")
        print()
        
        stats_b = exporter.get_export_stats('B')
        print(f"Tier B Only:")
        print(f"  Total leads: {stats_b['total_in_tier']}")
        print(f"  Contactable: {stats_b['total_contactable']} ({stats_b['contactable_rate']}%)")
        print()
        
        # Export sample leads
        print("-" * 70)
        print("📤 Sample Export (First 5 Tier A leads):")
        print()
        
        leads = exporter.export_tier_ab_for_instantly(
            tier_filter='A',
            prefer_contact_email=True,
            limit=5
        )
        
        for i, lead in enumerate(leads, 1):
            print(f"{i}. {lead.first_name} {lead.last_name} ({lead.email})")
            print(f"   Company: {lead.company_name}")
            print(f"   Location: {lead.city}, {lead.state}")
            print(f"   Tier: {lead.tier} | Score: {lead.score}")
            print(f"   Email source: {lead.email_source}")
            print()
        
        # Show Instantly API format
        if leads:
            print("-" * 70)
            print("📋 Instantly API Format (First Lead):")
            print()
            print(json.dumps(leads[0].to_instantly_format(), indent=2))
            print()
    
    print("=" * 70)
    print("✅ Export test complete!")
    print("=" * 70)
