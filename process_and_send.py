import pandas as pd
import config
from keyaccess_api import KeyAccessClient
import datetime
from zoneinfo import ZoneInfo
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os

LOG_SHEET = "log"
LOG_HEADERS = [
    "timestamp", "data", "hora_inicio", "hora_fim", "sentido",
    "titulo", "driver_name", "cpf", "placa_veiculo", "multiCheckin",
    "hostRefId", "resultado", "link", "erro"
]

def format_date_iso(date_str, time_str, is_end=False):
    try:
        dt_str = f"{date_str} {time_str}"
        dt = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        local_tz = ZoneInfo("America/Sao_Paulo")
        dt_local = dt.replace(tzinfo=local_tz)
        dt_utc = dt_local.astimezone(ZoneInfo("UTC"))
        return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        print(f"Warning: Could not parse date {date_str} {time_str}")
        return None

def ensure_log_sheet(sheet, spreadsheet_id):
    """Cria a aba 'log' com cabeçalho se não existir."""
    meta = sheet.get(spreadsheetId=spreadsheet_id).execute()
    existing = [s["properties"]["title"] for s in meta["sheets"]]
    if LOG_SHEET not in existing:
        body = {"requests": [{"addSheet": {"properties": {"title": LOG_SHEET}}}]}
        sheet.batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
        sheet.values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{LOG_SHEET}!A1",
            valueInputOption="RAW",
            body={"values": [LOG_HEADERS]}
        ).execute()
        print(f"Aba '{LOG_SHEET}' criada com cabeçalho.")

def append_log(sheet, spreadsheet_id, row):
    """Adiciona uma linha na aba de log."""
    sheet.values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{LOG_SHEET}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]}
    ).execute()

def main():
    # 1. Valida variáveis de ambiente obrigatórias (falha imediata se ausentes)
    try:
        config.validate_config()
    except EnvironmentError as e:
        print(f"ERRO DE CONFIGURAÇÃO:\n{e}")
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
        sheet = service.spreadsheets()

        result = sheet.values().get(spreadsheetId=config.SPREADSHEET_ID, range="A:Z").execute()
        values = result.get('values', [])

        if not values:
            print('No data found in Google Sheet.')
            return

        # Find the header row
        header_row_index = -1
        for i, row in enumerate(values):
            row_str = [str(x).lower() for x in row]
            if "titulo" in row_str or "sentido" in row_str:
                header_row_index = i
                break

        if header_row_index == -1:
            print("Error: Could not find header row with 'Titulo' or 'sentido'.")
            return

        headers = values[header_row_index]
        data_rows = values[header_row_index+1:]

        max_cols = len(headers)
        cleaned_rows = []
        for row in data_rows:
            if len(row) < max_cols:
                row += [''] * (max_cols - len(row))
            elif len(row) > max_cols:
                row = row[:max_cols]
            cleaned_rows.append(row)

        df = pd.DataFrame(cleaned_rows, columns=headers)
        df.columns = df.columns.str.strip()

        ensure_log_sheet(sheet, config.SPREADSHEET_ID)

    except Exception as e:
        print(f"Error reading from Google Sheets: {e}")
        return

    # 4. Process Rows
    success_count = 0
    fail_count = 0
    timestamp_run = datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")

    print(f"Processing {len(df)} rows...")

    for index, row in df.iterrows():
        print(f"\n--- Row {index + 1} ---")

        behavior = "ENTRY"
        if str(row['sentido']).upper().strip() == "SAIDA":
            behavior = "EXIT"

        start_at = format_date_iso(row['data'], row['hora_inicio'])
        end_at = format_date_iso(row['data'], row['hora_fim'])

        raw_cpf = str(row['cpf']).replace(".", "").replace("-", "").strip()
        cpf_formatted = raw_cpf.zfill(11)

        if not start_at or not end_at:
            print("Skipping due to date error.")
            append_log(sheet, config.SPREADSHEET_ID, [
                timestamp_run, str(row['data']), str(row['hora_inicio']), str(row['hora_fim']),
                behavior, str(row['Titulo']), str(row['driver_name']), cpf_formatted,
                str(row['placa_veiculo']), "", config.HOST_REF_ID, "FAILED", "", "Erro ao formatar data"
            ])
            fail_count += 1
            continue

        raw_multi = row.get('multichein', 'NÃO')
        print(f"[DEBUG] multichein raw value: '{raw_multi}' | type: {type(raw_multi)}")
        multi_checkin = str(raw_multi).upper().strip() == "SIM"

        payload = {
            "title": str(row['Titulo']),
            "startAt": start_at,
            "endAt": end_at,
            "behavior": behavior,
            "target": "LOGISTIC",
            "autoRelease": True,
            "multiCheckin": multi_checkin,
            "hostRefId": config.HOST_REF_ID,
            "driver": {
                "fullName": str(row['driver_name']),
                "document": cpf_formatted,
                "licensePlateOne": str(row['placa_veiculo']),
                "onFoot": False
            },
            "assistants": []
        }

        ajudante = str(row['nome_ajudante']).strip()
        doc_ajudante = str(row['doc_ajudante']).strip()

        if ajudante and ajudante != "-" and ajudante.lower() != "nan":
            payload["assistants"].append({
                "fullName": ajudante,
                "document": doc_ajudante if doc_ajudante != "-" else ""
            })

        print(f"Sending event for driver: {row['driver_name']}")
        print(f"Payload: {payload}")

        api_result = client.create_event(payload)

        if api_result:
            link = api_result.get("fullPathLocator", "")
            print("SUCCESS! Event Created.")
            if link:
                print(f"Link: {link}")
            append_log(sheet, config.SPREADSHEET_ID, [
                timestamp_run, str(row['data']), str(row['hora_inicio']), str(row['hora_fim']),
                behavior, str(row['Titulo']), str(row['driver_name']), cpf_formatted,
                str(row['placa_veiculo']), str(multi_checkin), config.HOST_REF_ID, "SUCCESS", link, ""
            ])
            success_count += 1
        else:
            print("FAILED.")
            append_log(sheet, config.SPREADSHEET_ID, [
                timestamp_run, str(row['data']), str(row['hora_inicio']), str(row['hora_fim']),
                behavior, str(row['Titulo']), str(row['driver_name']), cpf_formatted,
                str(row['placa_veiculo']), str(multi_checkin), config.HOST_REF_ID, "FAILED", "", ""
            ])
            fail_count += 1

    print(f"\nProcessing Complete. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    main()
