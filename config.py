# Credentials for KeyAccess API (Produção - API de integração)
# Fornecidos pela equipe KeyAccess / visitantes.online
# No CI (GitHub Actions), use variáveis de ambiente / Secrets (prefixo KEYACCESS_*).

import os

def _env(key: str, default: str) -> str:
    return os.environ.get(key, default).strip() or default

def _env_int(key: str, default: int) -> int:
    v = os.environ.get(key)
    return int(v) if v and str(v).strip() else default

CLIENT_ID = _env("KEYACCESS_CLIENT_ID", "companyshopee")
CLIENT_SECRET = _env("KEYACCESS_CLIENT_SECRET", "a38a60421c2f1ccba852f6e42")
COMPANY_INSTANCE_NAME = _env("KEYACCESS_COMPANY_INSTANCE", "companylogsbcshopee")

BASE_URL = _env("KEYACCESS_BASE_URL", "https://api.visitantes.online/api")
AUTH_URL = _env("KEYACCESS_AUTH_URL", "https://visitantes.online/auth/login/client")

HOST_REF_ID = _env_int("KEYACCESS_HOST_REF_ID", 2559690)

SPREADSHEET_ID = _env("KEYACCESS_SPREADSHEET_ID", "1LUunSuW8yQLSrwT5t1EpX45akyyH3zPj1ojr2rT6qkc")
SERVICE_ACCOUNT_FILE = _env("KEYACCESS_SERVICE_ACCOUNT_FILE", "service_account.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"] 
