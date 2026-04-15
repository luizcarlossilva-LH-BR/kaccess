# Credenciais da API KeyAccess (Produção - API de integração)
#
# CONFIGURAÇÃO LOCAL:
#   Copie o arquivo .env.example para .env e preencha os valores.
#   O .env está no .gitignore e NUNCA deve ser commitado.
#
# CONFIGURAÇÃO CI (GitHub Actions):
#   Use Secrets em Settings > Secrets and variables > Actions.
#
# VARIÁVEIS OBRIGATÓRIAS:
#   KEYACCESS_CLIENT_ID, KEYACCESS_CLIENT_SECRET, KEYACCESS_COMPANY_INSTANCE
#   KEYACCESS_SPREADSHEET_ID, KEYACCESS_HOST_REF_ID
#   GCP_SERVICE_ACCOUNT_JSON  (GitHub Actions) ou KEYACCESS_SERVICE_ACCOUNT_FILE (local)

import os

def _env(key: str, default: str = "") -> str:
    """Lê variável de ambiente, retornando default se não encontrada."""
    return os.environ.get(key, default).strip() or default

def _env_int(key: str, default: int = 0) -> int:
    """Lê variável de ambiente como inteiro."""
    v = os.environ.get(key)
    return int(v) if v and str(v).strip() else default

# --- Credenciais da API (OBRIGATÓRIAS via variável de ambiente) ---
CLIENT_ID             = _env("KEYACCESS_CLIENT_ID")
CLIENT_SECRET         = _env("KEYACCESS_CLIENT_SECRET")
COMPANY_INSTANCE_NAME = _env("KEYACCESS_COMPANY_INSTANCE")

# --- URLs da API (possuem valor padrão seguro) ---
BASE_URL = _env("KEYACCESS_BASE_URL", "https://api.visitantes.online/api")
AUTH_URL = _env("KEYACCESS_AUTH_URL", "https://visitantes.online/auth/login/client")

# --- Configurações da planilha (OBRIGATÓRIAS via variável de ambiente) ---
HOST_REF_ID          = _env_int("KEYACCESS_HOST_REF_ID", 2559690)
SPREADSHEET_ID       = _env("KEYACCESS_SPREADSHEET_ID")
SERVICE_ACCOUNT_FILE = _env("KEYACCESS_SERVICE_ACCOUNT_FILE", "service_account.json")
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

# --- Validação antecipada: falha imediata se variáveis obrigatórias estiverem ausentes ---
_REQUIRED = {
    "KEYACCESS_CLIENT_ID":        CLIENT_ID,
    "KEYACCESS_CLIENT_SECRET":    CLIENT_SECRET,
    "KEYACCESS_COMPANY_INSTANCE": COMPANY_INSTANCE_NAME,
    "KEYACCESS_SPREADSHEET_ID":   SPREADSHEET_ID,
}

def validate_config():
    """Verifica se todas as variáveis obrigatórias estão definidas."""
    missing = [key for key, val in _REQUIRED.items() if not val]
    if missing:
        raise EnvironmentError(
            "As seguintes variáveis de ambiente obrigatórias não estão definidas:\n"
            + "\n".join(f"  - {k}" for k in missing)
            + "\n\nConsulte o .env.example para configuração local ou "
              "adicione os Secrets no GitHub Actions."
        )
