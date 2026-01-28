"""
Re-enrich Tier U leads that failed or are pending.
These leads scored 0 because enrichment failed, not because they're bad.
Goal: Find hidden A/B/C quality leads currently stuck in U tier.
"""

import time
from database.models import get_db_connection, log_action
from enrichment.gemini_client import enrich_lead_with_gemini
from enrichment.scorer import calculate_score

def reenrich_tier_u(progress_interval=50):
    """Re-enrich failed/pending Tier U leads and re-score them."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get Tier U leads that need re-enrichment
    cursor.execute("""
        SELECT id, business_name, city, state, website_text, score
        FROM leads
        WHERE tier = 'U'
          AND website_text IS NOT NULL
          AND LENGTH(website_text) > 1000
          AND (gemini_status = 'failed' OR gemini_status = 'pending' OR gemini_status IS NULL)
        ORDER BY 
          CASE 
            WHEN business_type LIKE '%nursery%' THEN 1
            WHEN business_type LIKE '%greenhouse%' THEN 2
            ELSE 3
          END,
          LENGTH(website_text) DESC
        LIMIT 1000
    """)
    
    leads = cursor.fetchall()
    
    print("=" * 80)
    print("TIER U RE-ENRICHMENT & RE-SCORING")
    print("=" * 80)
    print(f"Total leads to re-enrich: {len(leads)}")
    print()
    print("Goal: Find hidden A/B/C quality leads currently stuck in U tier")
    print()
    
    stats = {
        'total': len(leads),
        'enriched': 0,
        'failed': 0,
        'upgraded_to_a': 0,
        'upgraded_to_b': 0,
        'upgraded_to_c': 0,
        'stayed_u': 0,
        'errors': 0
    }
    
    for idx, lead in enumerate(leads, 1):
        lead_id, business_name, city, state, website_text, old_score = lead
        
        print(f"[{idx}/{len(leads)}] {business_name} (Old: U/{old_score})", flush=True)
        
        try:
            # Re-enrich with Gemini
            enriched = enrich_lead_with_gemini(
                website_text=website_text,
                business_name=business_name,
                city=city,
                state=state
            )
            
            # Extract fields
            business_type = enriched.get('business_type')
            is_wholesale = enriched.get('is_wholesale')
            is_retail = enriched.get('is_retail')
            container_production = enriched.get('container_production')
            soil_relevance = enriched.get('soil_relevance')
            organic_focus = enriched.get('organic_focus')
            crops_grown = enriched.get('crops_grown', [])
            negative_indicators = enriched.get('negative_indicators', {})
            uses_growing_media = enriched.get('uses_growing_media')
            production_method = enriched.get('production_method')
            is_organic_certified = enriched.get('is_organic_certified')
            
            # Update database with enrichment
            cursor.execute("""
                UPDATE leads
                SET business_type = ?,
                    is_wholesale = ?,
                    is_retail = ?,
                    container_production = ?,
                    soil_relevance = ?,
                    organic_focus = ?,
                    uses_growing_media = ?,
                    production_method = ?,
                    is_organic_certified = ?,
                    gemini_status = 'enriched'
                WHERE id = ?
            """, (
                business_type,
                is_wholesale,
                is_retail,
                container_production,
                soil_relevance,
                organic_focus,
                uses_growing_media,
                production_method,
                is_organic_certified,
                lead_id
            ))
            
            conn.commit()
            stats['enriched'] += 1
            
            # Re-calculate score
            # Fetch the updated lead
            cursor.execute("""
                SELECT * FROM leads WHERE id = ?
            """, (lead_id,))
            
            updated_lead = dict(zip([d[0] for d in cursor.description], cursor.fetchone()))
            
            # Calculate new score
            score_result = calculate_score(updated_lead)
            new_score = score_result['total']
            new_tier = score_result['tier']
            
            # Update with new score
            cursor.execute("""
                UPDATE leads
                SET score = ?,
                    tier = ?,
                    score_breakdown = ?,
                    negative_indicators = ?
                WHERE id = ?
            """, (
                new_score,
                new_tier,
                str(score_result.get('signals', [])),
                str(score_result.get('negative_indicators', {})),
                lead_id
            ))
            
            conn.commit()
            
            # Track upgrades
            if new_tier == 'A':
                stats['upgraded_to_a'] += 1
                tier_icon = '🌟'
            elif new_tier == 'B':
                stats['upgraded_to_b'] += 1
                tier_icon = '⭐'
            elif new_tier == 'C':
                stats['upgraded_to_c'] += 1
                tier_icon = '✨'
            else:
                stats['stayed_u'] += 1
                tier_icon = '⚪'
            
            print(f"   {tier_icon} Re-scored: {new_tier}/{new_score} (was U/{old_score})", flush=True)
            
            if new_tier != 'U':
                print(f"   🎯 UPGRADED! {business_type or 'Unknown type'}", flush=True)
            
            log_action(lead_id, 'tier_u_reenrichment', 
                      f"Re-enriched: {new_tier}/{new_score} (was U/{old_score})", cursor)
        
        except Exception as e:
            stats['failed'] += 1
            stats['errors'] += 1
            error_msg = str(e)[:200]
            print(f"   ❌ Failed: {error_msg}", flush=True)
            
            cursor.execute("""
                UPDATE leads SET gemini_status = 'failed' WHERE id = ?
            """, (lead_id,))
            conn.commit()
            
            log_action(lead_id, 'tier_u_reenrichment_failed', error_msg, cursor)
        
        # Progress report
        if idx % progress_interval == 0 or idx == len(leads):
            print()
            print("=" * 80)
            print(f"PROGRESS REPORT: {idx}/{len(leads)} leads processed ({idx/len(leads)*100:.1f}%)")
            print("=" * 80)
            print(f"Successfully enriched: {stats['enriched']} ({stats['enriched']/idx*100:.1f}%)")
            print(f"Failed: {stats['failed']} ({stats['failed']/idx*100:.1f}%)")
            print()
            print("Tier upgrades:")
            print(f"  🌟 A tier: {stats['upgraded_to_a']} ({stats['upgraded_to_a']/idx*100:.1f}%)")
            print(f"  ⭐ B tier: {stats['upgraded_to_b']} ({stats['upgraded_to_b']/idx*100:.1f}%)")
            print(f"  ✨ C tier: {stats['upgraded_to_c']} ({stats['upgraded_to_c']/idx*100:.1f}%)")
            print(f"  ⚪ Stayed U: {stats['stayed_u']} ({stats['stayed_u']/idx*100:.1f}%)")
            total_upgraded = stats['upgraded_to_a'] + stats['upgraded_to_b'] + stats['upgraded_to_c']
            print()
            print(f"Total upgraded: {total_upgraded} ({total_upgraded/idx*100:.1f}%)")
            print("=" * 80)
            print()
        
        # Rate limiting
        time.sleep(1.2)
    
    conn.close()
    
    # Final summary
    print()
    print("=" * 80)
    print("RE-ENRICHMENT COMPLETE")
    print("=" * 80)
    print(f"Total processed: {stats['total']}")
    print(f"Successfully enriched: {stats['enriched']} ({stats['enriched']/stats['total']*100:.1f}%)")
    print(f"Failed: {stats['failed']} ({stats['failed']/stats['total']*100:.1f}%)")
    print()
    print("🎯 TIER UPGRADES:")
    print(f"  🌟 A tier: {stats['upgraded_to_a']} leads")
    print(f"  ⭐ B tier: {stats['upgraded_to_b']} leads")
    print(f"  ✨ C tier: {stats['upgraded_to_c']} leads")
    total_upgraded = stats['upgraded_to_a'] + stats['upgraded_to_b'] + stats['upgraded_to_c']
    print(f"  Total upgraded: {total_upgraded} ({total_upgraded/stats['total']*100:.1f}%)")
    print()
    
    if total_upgraded > 0:
        print(f"✅ SUCCESS! Found {total_upgraded} qualified leads hidden in Tier U!")
        print()
        print("Next step: Run contact extraction + email search on new A/B leads:")
        print("  python full_pipeline_with_progress.py")
    
    return stats

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    
    reenrich_tier_u(progress_interval=50)
