from database.models import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM leads WHERE gemini_status = 'enriched'")
enriched = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM leads")
total = cursor.fetchone()[0]

print(f"Total leads: {total}")
print(f"Enriched leads: {enriched}")

cursor.execute("SELECT tier, COUNT(*) as count FROM leads WHERE tier IS NOT NULL GROUP BY tier")
tiers = cursor.fetchall()

print("\nCurrent tier distribution:")
for row in tiers:
    print(f"  Tier {row['tier']}: {row['count']}")

conn.close()
