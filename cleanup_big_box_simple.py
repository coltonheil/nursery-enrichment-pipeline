"""
Simple Big Box Cleanup - Remove known retailers and duplicates
"""

import sqlite3
from database.models import get_db_connection

def cleanup():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("=" * 80)
    print("BIG BOX RETAILER & DUPLICATE CLEANUP")
    print("=" * 80)
    print()
    
    # Count before
    cursor.execute("SELECT COUNT(*) FROM leads")
    total_before = cursor.fetchone()[0]
    print(f"Total leads before cleanup: {total_before:,}")
    print()
    
    # 1. Remove Dollar Tree
    print("Removing Dollar Tree...")
    cursor.execute("DELETE FROM leads WHERE business_name LIKE '%DOLLAR TREE%'")
    print(f"  ✅ Removed {cursor.rowcount} entries")
    
    # 2. Remove Home Depot
    print("Removing Home Depot...")
    cursor.execute("DELETE FROM leads WHERE business_name LIKE '%HOME DEPOT%'")
    print(f"  ✅ Removed {cursor.rowcount} entries")
    
    # 3. Remove Lowes
    print("Removing Lowes...")
    cursor.execute("DELETE FROM leads WHERE business_name LIKE '%LOWES%' OR business_name LIKE '%LOWE''S%'")
    print(f"  ✅ Removed {cursor.rowcount} entries")
    
    # 4. Remove Walmart
    print("Removing Walmart...")
    cursor.execute("DELETE FROM leads WHERE business_name LIKE '%WALMART%'")
    print(f"  ✅ Removed {cursor.rowcount} entries")
    
    # 5. Remove Menards
    print("Removing Menards...")
    cursor.execute("DELETE FROM leads WHERE business_name LIKE '%MENARDS%'")
    print(f"  ✅ Removed {cursor.rowcount} entries")
    
    # 6. Remove Costco
    print("Removing Costco...")
    cursor.execute("DELETE FROM leads WHERE business_name LIKE '%COSTCO%'")
    print(f"  ✅ Removed {cursor.rowcount} entries")
    
    # 7. Remove Family Fare/Dollar General/Family Dollar
    print("Removing other big box grocery/discount...")
    cursor.execute("""
        DELETE FROM leads 
        WHERE business_name LIKE '%FAMILY FARE%' 
           OR business_name LIKE '%DOLLAR GENERAL%'
           OR business_name LIKE '%FAMILY DOLLAR%'
    """)
    print(f"  ✅ Removed {cursor.rowcount} entries")
    
    # 8. Remove Ace Hardware chains (keep individual stores)
    print("Removing Ace Hardware duplicates (keeping unique stores)...")
    cursor.execute("""
        DELETE FROM leads 
        WHERE business_name = 'ACE HARDWARE' 
           OR business_name = 'Ace Hardware'
    """)
    print(f"  ✅ Removed {cursor.rowcount} generic entries")
    
    # 9. Remove exact duplicates (same name + address)
    print()
    print("Removing duplicate entries (same business + address)...")
    cursor.execute("""
        DELETE FROM leads
        WHERE rowid NOT IN (
            SELECT MIN(rowid)
            FROM leads
            WHERE address IS NOT NULL AND address != ''
            GROUP BY business_name, address
        )
        AND address IS NOT NULL AND address != ''
        AND (business_name, address) IN (
            SELECT business_name, address
            FROM leads
            WHERE address IS NOT NULL AND address != ''
            GROUP BY business_name, address
            HAVING COUNT(*) > 1
        )
    """)
    print(f"  ✅ Removed {cursor.rowcount} duplicate entries")
    
    conn.commit()
    
    # Count after
    cursor.execute("SELECT COUNT(*) FROM leads")
    total_after = cursor.fetchone()[0]
    removed = total_before - total_after
    
    print()
    print("=" * 80)
    print("CLEANUP COMPLETE")
    print("=" * 80)
    print()
    print(f"Total leads before: {total_before:,}")
    print(f"Total leads after:  {total_after:,}")
    print(f"Total removed:      {removed:,}")
    print()
    
    # Show tier distribution
    cursor.execute("SELECT tier, COUNT(*) FROM leads GROUP BY tier ORDER BY tier")
    print("Updated tier distribution:")
    for tier, count in cursor.fetchall():
        pct = count / total_after * 100 if total_after > 0 else 0
        print(f"  Tier {tier}: {count:,} ({pct:.1f}%)")
    print()
    
    conn.close()

if __name__ == '__main__':
    cleanup()
