"""
Cleanup Big Box Retailers and Duplicates

Removes big box retail stores (Dollar Tree, Home Depot, Lowes, Walmart, etc.)
and deduplicates the database.
"""

import sqlite3
from database.models import get_db_connection

# Big box retailer patterns to remove
BIG_BOX_PATTERNS = [
    # Major chains
    'DOLLAR TREE',
    'DOLLAR GENERAL',
    'FAMILY DOLLAR',
    'HOME DEPOT',
    'LOWES',
    'LOWE\'S',
    'WALMART',
    'MENARDS',
    'FLEET FARM',
    'FARM & FLEET',
    'TRACTOR SUPPLY',
    'TSC STORES',
    'RURAL KING',
    
    # Hardware stores (mostly retail, not nurseries)
    'ACE HARDWARE',
    'TRUE VALUE',
    'DO IT BEST',
    
    # Big box grocery with garden centers
    'MEIJER',
    'KROGER',
    'ALDI',
    'COSTCO',
    'SAM\'S CLUB',
    
    # Garden center chains
    'GARDEN RIDGE',
    'GETHSEMANE GARDEN CENTER',
]

# Exact business names to remove (non-nursery businesses)
EXACT_REMOVALS = [
    'DOLLAR TREE STORES INC',
    'THE HOME DEPOT USA INC',
    'HOME DEPOT USA INC DBA',
    'LOWES HOME CENTERS LLC',
    'LOWES HOME CENTERS LLC DBA',
    'WALMART INC DBA',
    'MENARDS INC',
]

def cleanup_big_box():
    """Remove big box retailers and duplicates from database."""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("=" * 80)
    print("BIG BOX RETAILER CLEANUP")
    print("=" * 80)
    print()
    
    # 1. Count big box retailers
    print("1️⃣  Identifying big box retailers...")
    print()
    
    # Build pattern conditions
    conditions = []
    for pattern in BIG_BOX_PATTERNS:
        conditions.append(f"business_name LIKE '%{pattern}%'")
    for name in EXACT_REMOVALS:
        conditions.append(f"business_name = ?")
    
    where_clause = " OR ".join(conditions)
    params = EXACT_REMOVALS
    
    cursor.execute(f"""
        SELECT business_name, COUNT(*) as count
        FROM leads
        WHERE ({where_clause})
        GROUP BY business_name
        ORDER BY count DESC
    """, params)
    
    big_box_summary = cursor.fetchall()
    total_big_box = sum(count for _, count in big_box_summary)
    
    print(f"Found {len(big_box_summary)} big box retailer names ({total_big_box} total entries):")
    print()
    for name, count in big_box_summary[:20]:
        print(f"  - {name}: {count} entries")
    
    if len(big_box_summary) > 20:
        print(f"  ... and {len(big_box_summary) - 20} more")
    print()
    
    # 2. Identify exact duplicates (same business_name + address)
    print("2️⃣  Identifying exact duplicates...")
    print()
    
    cursor.execute("""
        SELECT business_name, address, COUNT(*) as count
        FROM leads
        WHERE address IS NOT NULL
        GROUP BY business_name, address
        HAVING count > 1
        ORDER BY count DESC
    """)
    
    duplicates = cursor.fetchall()
    total_duplicate_entries = sum(count - 1 for _, _, count in duplicates)  # Keep 1, remove rest
    
    print(f"Found {len(duplicates)} duplicate business+address combinations:")
    print(f"  Total duplicate entries to remove: {total_duplicate_entries}")
    print()
    for name, address, count in duplicates[:10]:
        addr_short = (address[:50] + '...') if len(address) > 50 else address
        print(f"  - {name} ({addr_short}): {count} entries")
    
    if len(duplicates) > 10:
        print(f"  ... and {len(duplicates) - 10} more")
    print()
    
    # 3. Show cleanup plan
    print("=" * 80)
    print("CLEANUP PLAN")
    print("=" * 80)
    print()
    print(f"Big box retailers to remove: {total_big_box} entries")
    print(f"Duplicate entries to remove: {total_duplicate_entries} entries")
    print(f"Total entries to remove: {total_big_box + total_duplicate_entries}")
    print()
    
    # 4. Execute cleanup
    response = input("Proceed with cleanup? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("Cleanup cancelled.")
        conn.close()
        return
    
    print()
    print("🧹 Executing cleanup...")
    print()
    
    # Remove big box retailers
    cursor.execute(f"""
        DELETE FROM leads
        WHERE ({where_clause})
    """, params)
    big_box_removed = cursor.rowcount
    print(f"✅ Removed {big_box_removed} big box retailer entries")
    
    # Remove duplicates (keep the one with the lowest ID)
    cursor.execute("""
        DELETE FROM leads
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM leads
            WHERE address IS NOT NULL
            GROUP BY business_name, address
        )
        AND address IS NOT NULL
        AND (business_name, address) IN (
            SELECT business_name, address
            FROM leads
            WHERE address IS NOT NULL
            GROUP BY business_name, address
            HAVING COUNT(*) > 1
        )
    """)
    duplicates_removed = cursor.rowcount
    print(f"✅ Removed {duplicates_removed} duplicate entries")
    
    conn.commit()
    
    # 5. Final stats
    print()
    print("=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)
    print()
    
    cursor.execute("SELECT tier, COUNT(*) FROM leads GROUP BY tier ORDER BY tier")
    tier_distribution = cursor.fetchall()
    
    total_remaining = sum(count for _, count in tier_distribution)
    
    print("Updated tier distribution:")
    print()
    for tier, count in tier_distribution:
        pct = count / total_remaining * 100 if total_remaining > 0 else 0
        print(f"  Tier {tier}: {count:,} leads ({pct:.1f}%)")
    print()
    print(f"Total leads remaining: {total_remaining:,}")
    print(f"Total removed: {big_box_removed + duplicates_removed:,}")
    print()
    
    conn.close()

if __name__ == '__main__':
    cleanup_big_box()
