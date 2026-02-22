import pandas as pd
import config
from keyaccess_api import KeyAccessClient
import datetime
from zoneinfo import ZoneInfo
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

# --- Helper Functions ---
def format_date_iso(date_str, time_str, is_end=False):
    """
    Combines date and time into ISO 8601 format (UTC).
    Assumes input is in America/Sao_Paulo time.
    """
    try:
        # User data format: 2026-02-03
        dt_str = f"{date_str} {time_str}"
        dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        
        # Set timezone to Sao Paulo
        local_tz = ZoneInfo("America/Sao_Paulo")
        dt_local = dt.replace(tzinfo=local_tz)
        
        # Convert to UTC
        dt_utc = dt_local.astimezone(ZoneInfo("UTC"))
        
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        # Fallback if formats differ
        print(f"Warning: Could not parse date {date_str} {time_str}")
        return None

def main():
    # 1. Check Credentials
    if not config.CLIENT_ID or config.CLIENT_ID == "YOUR_CLIENT_ID":
        print("ERROR: Configure KEYACCESS_CLIENT_ID (config.py or env).")
        return

    # 2. Initialize Client and Login
    client = KeyAccessClient(config.CLIENT_ID, config.CLIENT_SECRET, config.COMPANY_INSTANCE_NAME)
    if not client.login():
        return

    # 3. Read Data from Google Sheets
    try:
        print(f"Connecting to Google Sheets (ID: {config.SPREADSHEET_ID})...")
        creds = service_account.Credentials.from_service_account_file(
            config.SERVICE_ACCOUNT_FILE, scopes=config.SCOPES
        )
        service = build('sheets', 'v4', credentials=creds)

        # Call the Sheets API
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=config.SPREADSHEET_ID,
                                    range="A:Z").execute() # Read all columns
        values = result.get('values', [])

        if not values:
            print('No data found in Google Sheet.')
            return


        
        # Find the header row
        header_row_index = -1
        for i, row in enumerate(values):
            # Check for key columns to identify header
            # Convert to lower case for check
            row_str = [str(x).lower() for x in row]
            if "titulo" in row_str or "sentido" in row_str:
                header_row_index = i
                break
        
        if header_row_index == -1:
            print("Error: Could not find header row with 'Titulo' or 'sentido'.")

            return

        headers = values[header_row_index]

        
        # Data starts after header
        data_rows = values[header_row_index+1:]

        
        # Pad or truncate rows to ensure they match header length
        max_cols = len(headers)
        cleaned_rows = []
        for row in data_rows:
            # Pad
            if len(row) < max_cols:
                row += [''] * (max_cols - len(row))
            # Truncate
            elif len(row) > max_cols:
                row = row[:max_cols]
            cleaned_rows.append(row)
            
        df = pd.DataFrame(cleaned_rows, columns=headers)
        
        # Strip whitespace from headers just in case
        df.columns = df.columns.str.strip()

        # Ensure we have the expected columns or map them if needed
        # (The user script uses specific column names like 'sentido', 'data', etc.)
        
    except Exception as e:
        print(f"Error reading from Google Sheets: {e}")
        return

    # 4. Process Rows
    success_count = 0
    fail_count = 0
    
    print(f"Processing {len(df)} rows...")
    
    for index, row in df.iterrows():
        print(f"\n--- Row {index + 1} ---")
        
        # Determine Behavior (ENTRY/EXIT)
        behavior = "ENTRY" # Default as per most rows
        if str(row['sentido']).upper().strip() == "SAIDA":
             behavior = "EXIT"
        
        # Format Dates
        start_at = format_date_iso(row['data'], row['hora_inicio'])
        end_at = format_date_iso(row['data'], row['hora_fim'], is_end=True)
        
        # CPF Cleaning and Padding
        raw_cpf = str(row['cpf']).replace(".", "").replace("-", "").strip()
        # Ensure it has at least 11 digits (pad with zeros if pandas stripped them or csv was raw)
        cpf_formatted = raw_cpf.zfill(11)
        
        if not start_at or not end_at:
            print("Skipping due to date error.")
            fail_count += 1
            continue

        # Build payload
        # Note: 'titulo' in CSV is mapped to 'title'
        # 'driver_name' -> driver.fullName
        # 'cpf' -> driver.document
        # 'placa_veiculo' -> driver.licensePlateOne
        
        payload = {
            "title": str(row['Titulo']),
            "startAt": start_at,
            "endAt": end_at,
            "behavior": behavior,
            "target": "LOGISTIC",
            "autoRelease": False, # Default from PDF
            "hostRefId": config.HOST_REF_ID,
            "driver": {
                "fullName": str(row['driver_name']),
                "document": cpf_formatted,
                "licensePlateOne": str(row['placa_veiculo']),
                "onFoot": False
            },
            "assistants": []
        }
        
        # Add Assistant if present (nome_ajudante is not '-' and not empty)
        ajudante = str(row['nome_ajudante']).strip()
        doc_ajudante = str(row['doc_ajudante']).strip()
        
        if ajudante and ajudante != "-" and ajudante.lower() != "nan":
             assistant_data = {
                 "fullName": ajudante,
                 "document": doc_ajudante if doc_ajudante != "-" else ""
             }
             payload["assistants"].append(assistant_data)

        print(f"Sending event for driver: {row['driver_name']}")
        
        # Call API
        result = client.create_event(payload)
        
        if result:
            print("SUCCESS! Event Created.")
            # If entry, maybe print the fullPathLocator
            if "fullPathLocator" in result:
                print(f"Link: {result['fullPathLocator']}")
            success_count += 1
        else:
            print("FAILED.")
            fail_count += 1

    print(f"\nProcessing Complete. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    main()
