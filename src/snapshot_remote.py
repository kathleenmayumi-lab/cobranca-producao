"""Publica e lê o snapshot JSON no Google Drive (dashboard remoto)."""

from __future__ import annotations

import json
import os
from typing import Any

import requests
from google.auth.transport.requests import Request

from src.google_credentials import get_google_credentials

SNAPSHOT_FILENAME = "cobranca-latest.json"
DRIVE_UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"
DRIVE_API_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_QUERY_PARAMS = {"supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}


class SnapshotUploadError(RuntimeError):
    """Falha ao enviar snapshot para o Google Drive."""


def service_account_email() -> str:
    creds = get_google_credentials()
    return str(getattr(creds, "service_account_email", "") or "")


def _drive_error_message(response: requests.Response) -> str:
    try:
        detail = response.json().get("error", {}).get("message", "")
    except Exception:
        detail = response.text[:300]
    email = service_account_email()
    if response.status_code == 403:
        return (
            f"Google Drive recusou o envio (403 Forbidden). "
            f"Compartilhe a pasta com {email or 'a conta de serviço'} como Editor, "
            "confirme que a Google Drive API está ativa no Cloud Console "
            f"e que o ID da pasta está correto. Detalhe: {detail or response.reason}"
        )
    return f"Erro {response.status_code} no Google Drive: {detail or response.reason}"


def _auth_headers() -> dict[str, str]:
    creds = get_google_credentials()
    creds.refresh(Request())
    return {"Authorization": f"Bearer {creds.token}"}


def _setting(key: str) -> str:
    try:
        import streamlit as st

        if key in st.secrets:
            return str(st.secrets[key]).strip()
    except Exception:
        pass
    return os.getenv(key, "").strip()


def _snapshot_file_id() -> str:
    file_id = _setting("GOOGLE_DRIVE_SNAPSHOT_FILE_ID")
    if file_id:
        return file_id

    folder_id = _setting("GOOGLE_DRIVE_SNAPSHOT_FOLDER_ID")
    if not folder_id:
        return ""

    query = (
        f"'{folder_id}' in parents and "
        f"name = '{SNAPSHOT_FILENAME}' and trashed = false"
    )
    response = requests.get(
        DRIVE_API_URL,
        params={
            "q": query,
            "fields": "files(id,name)",
            "pageSize": 1,
            **DRIVE_QUERY_PARAMS,
        },
        headers=_auth_headers(),
        timeout=30,
    )
    if response.status_code == 403:
        return ""
    response.raise_for_status()
    files = response.json().get("files", [])
    return files[0]["id"] if files else ""


def remote_snapshot_configured() -> bool:
    return bool(_setting("GOOGLE_DRIVE_SNAPSHOT_FILE_ID") or _setting("GOOGLE_DRIVE_SNAPSHOT_FOLDER_ID"))


def upload_snapshot(summary: dict[str, Any]) -> str | None:
    """Grava/atualiza cobranca-latest.json no Drive. Retorna o file_id."""
    folder_id = _setting("GOOGLE_DRIVE_SNAPSHOT_FOLDER_ID")
    file_id = _snapshot_file_id()
    if not folder_id and not file_id:
        return None

    payload = json.dumps(summary, ensure_ascii=False).encode("utf-8")
    headers = {**_auth_headers(), "Content-Type": "application/json"}

    if file_id:
        response = requests.patch(
            f"{DRIVE_UPLOAD_URL}/{file_id}",
            params={"uploadType": "media", "supportsAllDrives": "true"},
            headers=headers,
            data=payload,
            timeout=120,
        )
    else:
        metadata = {
            "name": SNAPSHOT_FILENAME,
            "parents": [folder_id],
            "mimeType": "application/json",
        }
        response = requests.post(
            f"{DRIVE_UPLOAD_URL}",
            params={"uploadType": "multipart", "supportsAllDrives": "true"},
            headers=_auth_headers(),
            files={
                "metadata": (None, json.dumps(metadata), "application/json; charset=UTF-8"),
                "file": (SNAPSHOT_FILENAME, payload, "application/json"),
            },
            timeout=120,
        )

    if not response.ok:
        raise SnapshotUploadError(_drive_error_message(response))
    return response.json().get("id") or file_id


def download_snapshot() -> dict[str, Any] | None:
    """Baixa o snapshot do Drive."""
    file_id = _snapshot_file_id()
    if not file_id:
        return None

    response = requests.get(
        f"{DRIVE_API_URL}/{file_id}",
        params={"alt": "media"},
        headers=_auth_headers(),
        timeout=120,
    )
    response.raise_for_status()
    return response.json()
