"""Credenciais Google — arquivo local ou JSON em variável/secrets."""

from __future__ import annotations

import json
import os
from typing import Any

from google.oauth2.service_account import Credentials

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _parse_service_account_info(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON inválido")


def _secrets_value(key: str) -> Any | None:
    try:
        import streamlit as st

        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return None


def get_google_credentials(scopes: list[str] | None = None) -> Credentials:
    scopes = scopes or DEFAULT_SCOPES

    for key in ("GOOGLE_SERVICE_ACCOUNT_JSON", "GOOGLE_SERVICE_ACCOUNT"):
        secret = _secrets_value(key)
        if secret:
            return Credentials.from_service_account_info(_parse_service_account_info(secret), scopes=scopes)

    json_env = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if json_env:
        return Credentials.from_service_account_info(json.loads(json_env), scopes=scopes)

    creds_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/service_account.json")
    if os.path.exists(creds_file):
        return Credentials.from_service_account_file(creds_file, scopes=scopes)

    raise FileNotFoundError(
        "Credenciais Google não encontradas. Configure credentials/service_account.json "
        "ou GOOGLE_SERVICE_ACCOUNT_JSON (local/.env ou Streamlit Secrets)."
    )
