"""
Test script for Phase 8: CSV Export
Tests exporting Tier A+B leads to CSV for Instantly.ai
"""

from database.models import get_leads_for_export, get_export_preview_count
from exporters.instantly_exporter import export_to_csv, export_to_excel, get_export_filename

def test_export():
    """Test CSV export for Tier A and B leads."""

    print("Testing CSV Export for Instantly.ai")
    print("=" * 80)
    print()

    # Test 1: Preview count
    print("Test 1: Export Preview Count")
    print("-" * 80)

    # Count Tier A+B (no email requirement)
    count_ab = get_export_preview_count(tier_filter='AB', require_email=False, require_personalization=False)
    print(f"Tier A+B (any): {count_ab} leads")

    # Count Tier A+B with email
    count_ab_email = get_export_preview_count(tier_filter='AB', require_email=True, require_personalization=False)
    print(f"Tier A+B with email: {count_ab_email} leads")

    # Count Tier A+B with email AND personalization
    count_ab_email_pers = get_export_preview_count(tier_filter='AB', require_email=True, require_personalization=True)
    print(f"Tier A+B with email + personalization: {count_ab_email_pers} leads")

    # Count all tiers
    count_all = get_export_preview_count(tier_filter=None, require_email=False, require_personalization=False)
    print(f"All leads: {count_all} leads")

    print()

    # Test 2: Get leads for export (without email requirement for testing)
    print("Test 2: Get Leads for Export (Testing Mode - No Email Required)")
    print("-" * 80)

    leads = get_leads_for_export(tier_filter='AB', require_email=False, require_personalization=False)
    print(f"Retrieved {len(leads)} leads for export")

    if leads:
        print()
        print("Sample lead data:")
        lead = leads[0]
        print(f"  Business: {lead['business_name']}")
        print(f"  Email: {lead['owner_email']}")
        print(f"  Tier: {lead['tier_override'] or lead['tier']}")
        print(f"  Score: {lead['score']}")
        print(f"  Custom Line: {lead['custom_line']}")
        print(f"  Business Type: {lead['business_type']}")
    else:
        print("No leads found matching criteria")
        print()
        print("This is expected if:")
        print("  - No Tier A or B leads exist")
        print("  - No leads have owner_email")
        print()
        return False

    print()

    # Test 3: Generate CSV
    print("Test 3: Generate CSV with Metadata")
    print("-" * 80)

    leads_list = [dict(lead) for lead in leads]
    csv_content = export_to_csv(leads_list, include_metadata=True)

    # Show first few lines
    lines = csv_content.split('\n')
    print(f"Generated CSV with {len(lines)} lines")
    print()
    print("First 5 lines of CSV:")
    for i, line in enumerate(lines[:5], 1):
        print(f"  {i}: {line}")

    print()

    # Test 4: Generate CSV without metadata
    print("Test 4: Generate CSV without Metadata (Instantly.ai format)")
    print("-" * 80)

    csv_content_no_meta = export_to_csv(leads_list, include_metadata=False)
    lines_no_meta = csv_content_no_meta.split('\n')

    print(f"Generated CSV with {len(lines_no_meta)} lines")
    print()
    print("First 5 lines of CSV:")
    for i, line in enumerate(lines_no_meta[:5], 1):
        print(f"  {i}: {line}")

    print()

    # Test 5: Filename generation
    print("Test 5: Filename Generation")
    print("-" * 80)

    filename_csv_ab = get_export_filename(format='csv', tier_filter='AB')
    filename_csv_all = get_export_filename(format='csv', tier_filter=None)
    filename_xlsx_ab = get_export_filename(format='xlsx', tier_filter='AB')

    print(f"CSV (Tier A+B): {filename_csv_ab}")
    print(f"CSV (All): {filename_csv_all}")
    print(f"Excel (Tier A+B): {filename_xlsx_ab}")

    print()

    # Test 6: Column validation
    print("Test 6: Validate CSV Columns")
    print("-" * 80)

    # Parse header using proper CSV parsing
    import csv
    import io
    csv_reader = csv.DictReader(io.StringIO(csv_content_no_meta))
    columns = csv_reader.fieldnames

    expected_columns = [
        'email', 'first_name', 'last_name', 'company_name',
        'phone', 'website', 'location', 'custom_line'
    ]

    print("Expected columns for Instantly.ai:")
    for col in expected_columns:
        present = col in columns
        status = "[OK]" if present else "[MISSING]"
        print(f"  {status} {col}")

    all_present = all(col in columns for col in expected_columns)

    print()

    if all_present:
        print("[OK] All required columns present")
    else:
        print("[ERROR] Missing required columns")
        return False

    # Test 7: Data validation
    print()
    print("Test 7: Validate Data Fields")
    print("-" * 80)

    # Reset CSV reader to read data
    csv_reader = csv.DictReader(io.StringIO(csv_content_no_meta))
    first_row = next(csv_reader, None)

    if first_row:
        print("First exported lead:")
        for col in expected_columns:
            value = first_row.get(col, '')
            # Truncate long values
            display_value = value[:50] + '...' if len(value) > 50 else value
            print(f"  {col}: {display_value if display_value else '(empty)'}")

    print()

    # Summary
    print("=" * 80)
    print("EXPORT TEST SUMMARY")
    print("=" * 80)
    print(f"[OK] Preview count: {count_ab} leads (Tier A+B, any)")
    print(f"[OK] Retrieved leads: {len(leads)} leads")
    print(f"[OK] CSV generated: {len(lines_no_meta)} lines")
    print(f"[OK] Column validation: {'PASSED' if all_present else 'FAILED'}")
    print()

    if all_present and len(leads) > 0:
        print("Phase 8A testing complete! Export system is ready.")
        print()
        print("Next steps:")
        print("  1. Start Flask app: python app.py")
        print("  2. Navigate to: http://localhost:5000/export")
        print("  3. Test export to CSV")
        print("  4. Upload CSV to Instantly.ai")
        print()
        return True
    else:
        print("Phase 8A testing incomplete. Check errors above.")
        return False

if __name__ == '__main__':
    test_export()
