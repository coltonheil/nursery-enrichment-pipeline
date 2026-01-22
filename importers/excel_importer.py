import pandas as pd
import os
from database.models import insert_lead, log_action

def import_excel_file(file_path, original_filename):
    """
    Import leads from an Excel file.
    Returns a dictionary with import statistics.
    """
    results = {
        'total': 0,
        'imported': 0,
        'duplicates': 0,
        'errors': 0,
        'error_details': []
    }

    try:
        # Read Excel file
        df = pd.read_excel(file_path)

        # Normalize column names (strip whitespace, lowercase)
        df.columns = df.columns.str.strip().str.lower()

        # Check for required columns
        required_columns = ['business name', 'city']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            results['errors'] += 1
            results['error_details'].append(f"Missing required columns: {', '.join(missing_columns)}")
            return results

        # Optional columns mapping
        column_mapping = {
            'business name': 'business_name',
            'address': 'address',
            'city': 'city',
            'state': 'state',
            'zip': 'zip',
            'phone': 'phone',
            'website': 'website'
        }

        # Process each row
        for idx, row in df.iterrows():
            results['total'] += 1

            try:
                # Extract data with validation
                business_name = str(row.get('business name', '')).strip()
                city = str(row.get('city', '')).strip()

                # Skip if business name or city is empty
                if not business_name or business_name == 'nan':
                    results['errors'] += 1
                    results['error_details'].append(f"Row {idx + 2}: Missing business name")
                    continue

                if not city or city == 'nan':
                    results['errors'] += 1
                    results['error_details'].append(f"Row {idx + 2}: Missing city")
                    continue

                # Get optional fields
                address = str(row.get('address', '')).strip() if pd.notna(row.get('address')) else None
                state = str(row.get('state', '')).strip() if pd.notna(row.get('state')) else None
                zip_code = str(row.get('zip', '')).strip() if pd.notna(row.get('zip')) else None
                phone = str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else None
                website = str(row.get('website', '')).strip() if pd.notna(row.get('website')) else None

                # Clean up 'nan' strings
                if address == 'nan':
                    address = None
                if state == 'nan':
                    state = None
                if zip_code == 'nan':
                    zip_code = None
                if phone == 'nan':
                    phone = None
                if website == 'nan':
                    website = None

                # Insert lead
                lead_id, created = insert_lead(
                    business_name=business_name,
                    address=address,
                    city=city,
                    state=state,
                    zip_code=zip_code,
                    phone=phone,
                    website=website,
                    source_file=original_filename
                )

                if created:
                    results['imported'] += 1
                else:
                    results['duplicates'] += 1

            except Exception as e:
                results['errors'] += 1
                results['error_details'].append(f"Row {idx + 2}: {str(e)}")

    except Exception as e:
        results['errors'] += 1
        results['error_details'].append(f"Failed to read Excel file: {str(e)}")

    return results

def validate_excel_file(file_path):
    """
    Validate an Excel file before import.
    Returns (is_valid, error_message).
    """
    try:
        # Try to read the file
        df = pd.read_excel(file_path)

        # Check if file is empty
        if df.empty:
            return (False, "Excel file is empty")

        # Normalize column names
        df.columns = df.columns.str.strip().str.lower()

        # Check for required columns
        required_columns = ['business name', 'city']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            available_cols = ', '.join(df.columns.tolist())
            return (False, f"Missing required columns: {', '.join(missing_columns)}. Available columns: {available_cols}")

        return (True, None)

    except Exception as e:
        return (False, f"Failed to read Excel file: {str(e)}")
