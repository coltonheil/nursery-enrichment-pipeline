#!/usr/bin/env python3
"""
Phase 1: Main Orchestrator
Complete pipeline: Database → Instantly Campaigns

Usage:
    # Test with 5 leads
    python phase1_run.py --test

    # Sync Tier A leads
    python phase1_run.py --tier A

    # Sync Tier B leads
    python phase1_run.py --tier B

    # Sync all A+B leads
    python phase1_run.py --tier AB

    # Dry run (show what would be synced)
    python phase1_run.py --tier AB --dry-run
"""

import argparse
import sys
import os
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

# Import our modules
from phase1_lead_export import LeadExporter, InstantlyLead
from phase1_instantly_integration import InstantlySyncManager, SyncResult


class Phase1Pipeline:
    """Main Phase 1 orchestrator"""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.exporter = None
        self.sync_manager = None
    
    def run(
        self,
        tier_filter: str = 'AB',
        limit: Optional[int] = None,
        prefer_contact_email: bool = True
    ) -> Dict:
        """
        Run the complete Phase 1 pipeline.
        
        Args:
            tier_filter: 'A', 'B', or 'AB'
            limit: Maximum leads to process (None = all)
            prefer_contact_email: Prefer contact_email over owner_email
        
        Returns:
            Dictionary with results summary
        """
        print("=" * 70)
        print(f"Phase 1: Lead Export → Instantly Campaigns")
        print("=" * 70)
        print()
        
        if self.dry_run:
            print("⚠️  DRY RUN MODE - No leads will be synced")
            print()
        
        # Step 1: Export leads from database
        print("📊 Step 1: Analyzing Database")
        print("-" * 70)
        
        with LeadExporter() as exporter:
            # Get stats
            stats = exporter.get_export_stats(tier_filter)
            
            print(f"Tier Filter: {tier_filter}")
            print(f"  Total leads in tier: {stats['total_in_tier']}")
            print(f"  With owner email: {stats['with_owner_email']}")
            print(f"  With contact email: {stats['with_contact_email']}")
            print(f"  Total contactable: {stats['total_contactable']} ({stats['contactable_rate']}%)")
            print(f"  Breakdown: {stats['tier_breakdown']}")
            print()
            
            # Export leads
            print("📤 Step 2: Exporting Leads")
            print("-" * 70)
            
            leads = exporter.export_tier_ab_for_instantly(
                tier_filter=tier_filter,
                prefer_contact_email=prefer_contact_email,
                limit=limit
            )
            
            print(f"✅ Exported {len(leads)} leads")
            print()
        
        if len(leads) == 0:
            print("⚠️  No leads to sync")
            return {
                'total_leads': 0,
                'synced': 0,
                'failed': 0
            }
        
        # Step 3: Group by tier for campaign assignment
        print("🎯 Step 3: Grouping by Tier")
        print("-" * 70)
        
        tier_a_leads = [lead for lead in leads if lead.tier == 'A']
        tier_b_leads = [lead for lead in leads if lead.tier == 'B']
        
        print(f"Tier A: {len(tier_a_leads)} leads")
        print(f"Tier B: {len(tier_b_leads)} leads")
        print()
        
        if self.dry_run:
            print("📋 Dry Run: Would sync the following leads:")
            print()
            
            if tier_a_leads:
                print(f"Tier A → Campaign: {os.getenv('INSTANTLY_CAMPAIGN_TIER_A', 'N/A')[:8]}...")
                for i, lead in enumerate(tier_a_leads[:5], 1):
                    print(f"  {i}. {lead.email} - {lead.company_name} ({lead.city}, {lead.state})")
                if len(tier_a_leads) > 5:
                    print(f"  ... and {len(tier_a_leads) - 5} more")
                print()
            
            if tier_b_leads:
                print(f"Tier B → Campaign: {os.getenv('INSTANTLY_CAMPAIGN_TIER_B', 'N/A')[:8]}...")
                for i, lead in enumerate(tier_b_leads[:5], 1):
                    print(f"  {i}. {lead.email} - {lead.company_name} ({lead.city}, {lead.state})")
                if len(tier_b_leads) > 5:
                    print(f"  ... and {len(tier_b_leads) - 5} more")
                print()
            
            return {
                'total_leads': len(leads),
                'tier_a': len(tier_a_leads),
                'tier_b': len(tier_b_leads),
                'dry_run': True
            }
        
        # Step 4: Sync to Instantly campaigns
        print("🚀 Step 4: Syncing to Instantly")
        print("-" * 70)
        print()
        
        all_results = []
        
        with InstantlySyncManager() as sync_manager:
            # Create sync log table if needed
            sync_manager.create_sync_log_table()
            
            # Sync Tier A leads
            if tier_a_leads:
                print(f"📤 Syncing {len(tier_a_leads)} Tier A leads...")
                campaign_id = sync_manager.campaign_tier_a
                print(f"   Campaign: {campaign_id}")
                print()
                
                tier_a_data = [lead.to_instantly_format() for lead in tier_a_leads]
                
                results_a = sync_manager.sync_batch(
                    leads=tier_a_data,
                    campaign_id=campaign_id,
                    check_duplicates=True,
                    rate_limit_delay=0.5,
                    progress_callback=self._progress_callback
                )
                
                all_results.extend(results_a)
                print()
            
            # Sync Tier B leads
            if tier_b_leads:
                print(f"📤 Syncing {len(tier_b_leads)} Tier B leads...")
                campaign_id = sync_manager.campaign_tier_b
                print(f"   Campaign: {campaign_id}")
                print()
                
                tier_b_data = [lead.to_instantly_format() for lead in tier_b_leads]
                
                results_b = sync_manager.sync_batch(
                    leads=tier_b_data,
                    campaign_id=campaign_id,
                    check_duplicates=True,
                    rate_limit_delay=0.5,
                    progress_callback=self._progress_callback
                )
                
                all_results.extend(results_b)
                print()
            
            # Summary
            print("=" * 70)
            print("📊 Final Results")
            print("=" * 70)
            print()
            
            successful = [r for r in all_results if r.success]
            failed = [r for r in all_results if not r.success]
            
            print(f"Total Leads: {len(all_results)}")
            print(f"  ✅ Successful: {len(successful)}")
            print(f"  ❌ Failed: {len(failed)}")
            print()
            
            if failed:
                print("Failed Leads:")
                for result in failed:
                    print(f"  - {result.email}: {result.error}")
                print()
            
            # Get database stats
            stats = sync_manager.get_sync_stats()
            print("Database Sync History:")
            print(f"  Total synced (all time): {stats['total_synced']}")
            print(f"  Total failed (all time): {stats['total_failed']}")
            print(f"  By tier: {stats['tier_breakdown']}")
            print()
        
        return {
            'total_leads': len(all_results),
            'synced': len(successful),
            'failed': len(failed),
            'tier_a': len([r for r in all_results if 'tier_a' in r.campaign_id.lower()]),
            'tier_b': len([r for r in all_results if 'tier_b' in r.campaign_id.lower()]),
            'results': all_results
        }
    
    def _progress_callback(self, result: SyncResult, current: int, total: int):
        """Progress callback for batch sync"""
        status = "✅" if result.success else "❌"
        percent = int(current / total * 100)
        
        print(f"  [{percent:3d}%] {status} {result.email:40s} ({current}/{total})")
        
        if not result.success and result.error:
            # Only show first 60 chars of error
            error_short = result.error[:60] + ('...' if len(result.error) > 60 else '')
            print(f"        → {error_short}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Phase 1: Sync qualified leads to Instantly campaigns',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Test with 5 leads
  python phase1_run.py --test

  # Sync Tier A leads only
  python phase1_run.py --tier A

  # Sync Tier B leads only
  python phase1_run.py --tier B

  # Sync all A+B leads
  python phase1_run.py --tier AB

  # Dry run (preview what would be synced)
  python phase1_run.py --tier AB --dry-run
        '''
    )
    
    parser.add_argument(
        '--tier',
        choices=['A', 'B', 'AB'],
        default='AB',
        help='Tier filter: A, B, or AB (default: AB)'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Test mode: sync only 5 leads'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview mode: show what would be synced without actually syncing'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of leads to process'
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    # Validate environment
    required_vars = [
        'INSTANTLY_API_KEY',
        'INSTANTLY_CAMPAIGN_TIER_A',
        'INSTANTLY_CAMPAIGN_TIER_B'
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"❌ Missing required environment variables: {', '.join(missing)}")
        print("   Check your .env file")
        sys.exit(1)
    
    # Test mode: limit to 5 leads
    limit = args.limit
    if args.test:
        limit = 5
        print("🧪 TEST MODE: Limiting to 5 leads")
        print()
    
    # Run pipeline
    pipeline = Phase1Pipeline(dry_run=args.dry_run)
    
    try:
        results = pipeline.run(
            tier_filter=args.tier,
            limit=limit
        )
        
        # Exit code based on results
        if results['failed'] > 0:
            print(f"⚠️  Completed with {results['failed']} failures")
            sys.exit(1)
        else:
            print("✅ All leads synced successfully!")
            sys.exit(0)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
