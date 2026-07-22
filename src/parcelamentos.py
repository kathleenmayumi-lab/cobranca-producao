"""Controle de parcelamentos (entrada + boletos) via Google Sheets ou fallback local."""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

import gspread

from src.google_credentials import get_google_credentials
from src.wpp_loader import _api_retry, _clean_cell

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "parcelamentos.json"
WPP_CONFIG_PATH = ROOT / "config" / "wpp_sheets.json"
LOCAL_STORE_PATH = ROOT / "data" / "parcelamentos_local.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

STATUS_PENDENTE = "pendente"
STATUS_PAGO = "pago"
STATUS_CANCELADO = "cancelado"
TIPO_ENTRADA = "entrada"
TIPO_PARCELA = "parcela"

ALERTA_EM_DIA = "em_dia"
ALERTA_EM_ATRASO = "em_atraso"
ALERTA_A_VENCER = "a_vencer"
ALERTA_CANCELADO = "cancelado"

ALERTA_LABELS = {
    ALERTA_EM_DIA: "Em dia",
    ALERTA_EM_ATRASO: "Em atraso",
    ALERTA_A_VENCER: "A vencer",
    ALERTA_CANCELADO: "Cancelado",
}


def add_months(d: date, months: int, *, day: int | None = None) -> date:
    """Soma meses civis; `day` fixo (ex.: todo dia 22)."""
    import calendar

    target_day = int(day) if day is not None else d.day
    m0 = d.month - 1 + months
    year = d.year + m0 // 12
    month = m0 % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(max(1, target_day), last))


def vencimentos_mensais(
    *,
    ancora: date,
    dia_vencimento: int,
    n_parcelas: int,
    primeiro_apos_meses: int = 1,
) -> list[date]:
    """
    Gera N vencimentos no mesmo dia do mês (ex.: todo dia 22).
    Por padrão a 1ª parcela é 1 mês após a âncora (formalização/entrada).
    """
    if n_parcelas < 1:
        return []
    dia = max(1, min(int(dia_vencimento), 31))
    primeira = add_months(ancora, primeiro_apos_meses, day=dia)
    return [add_months(primeira, i, day=dia) for i in range(n_parcelas)]


ACORDOS_HEADERS = [
    "acordo_id",
    "created_at",
    "formalizacao",
    "agente",
    "cpf",
    "ccb",
    "produto",
    "cliente",
    "telefone",
    "valor_total",
    "pct_entrada",
    "valor_entrada",
    "data_entrada",
    "n_parcelas",
    "valor_parcela",
    "status_acordo",
    "observacao",
]

PARCELAS_HEADERS = [
    "parcela_id",
    "acordo_id",
    "agente",
    "cpf",
    "ccb",
    "produto",
    "cliente",
    "telefone",
    "tipo",
    "numero",
    "vencimento",
    "valor",
    "status",
    "pago_em",
    "formalizacao",
    "observacao",
    "created_at",
]

PRODUTOS_PADRAO = (
    "Early Stage",
    "Over 90",
    "IRPF",
    "Outro",
)


def _money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fmt_money(value: Decimal | float | int | str) -> str:
    return f"{_money(value):.2f}".replace(".", ",")


def _parse_money(text: Any) -> Decimal:
    raw = _clean_cell(text).replace("R$", "").replace(" ", "")
    if not raw:
        return Decimal("0.00")
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        raw = raw.replace(",", ".")
    return _money(raw)


def _fmt_date(d: date | datetime | None) -> str:
    if d is None:
        return ""
    if isinstance(d, datetime):
        d = d.date()
    return d.strftime("%d/%m/%Y")


def _parse_date(text: Any) -> date | None:
    raw = _clean_cell(text)
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw[:10], fmt).date()
        except ValueError:
            continue
    return None


def load_config() -> dict[str, Any]:
    path = Path(os.getenv("PARCELAMENTOS_CONFIG", str(CONFIG_PATH)))
    if not path.exists():
        return {
            "spreadsheet_id": "",
            "acordos_worksheet": "Acordos",
            "parcelas_worksheet": "Parcelas",
            "entrada_pct_padrao": 30,
            "max_parcelas": 5,
            "titulo_planilha": "Controle Parcelamentos — Cobrança",
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    env_id = os.getenv("PARCELAMENTOS_SPREADSHEET_ID", "").strip()
    if env_id:
        data["spreadsheet_id"] = env_id
    return data


def save_config(config: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def spreadsheet_configured() -> bool:
    return bool(str(load_config().get("spreadsheet_id", "")).strip())


def list_produtos() -> list[str]:
    cfg = load_config()
    custom = cfg.get("produtos")
    if isinstance(custom, list) and custom:
        return [str(p).strip() for p in custom if str(p).strip()]
    return list(PRODUTOS_PADRAO)


def normalizar_cpf(value: Any) -> str:
    digits = "".join(ch for ch in _clean_cell(value) if ch.isdigit())
    return digits


def formatar_cpf(value: Any) -> str:
    digits = normalizar_cpf(value)
    if len(digits) != 11:
        return digits
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def validar_cpf(value: Any) -> str:
    digits = normalizar_cpf(value)
    if len(digits) != 11:
        raise ValueError("CPF deve ter 11 dígitos")
    if digits == digits[0] * 11:
        raise ValueError("CPF inválido")
    return formatar_cpf(digits)


def list_agents(*, squads: list[str] | None = None) -> list[str]:
    """Lista agentes. Por padrão só squads de parcelamentos (Over 90 / IRPF)."""
    if not WPP_CONFIG_PATH.exists():
        return []
    allowed = squads
    if allowed is None:
        cfg_squads = load_config().get("squads")
        if isinstance(cfg_squads, list) and cfg_squads:
            allowed = [str(s).strip() for s in cfg_squads if str(s).strip()]
    allowed_cf = {s.casefold() for s in (allowed or [])}

    data = json.loads(WPP_CONFIG_PATH.read_text(encoding="utf-8"))
    names: list[str] = []
    for item in data.get("agents", []):
        name = str(item.get("agent") or "").strip()
        if not name:
            continue
        if allowed_cf:
            squad = str(item.get("squad") or "").strip()
            if squad.casefold() not in allowed_cf:
                continue
        if name not in names:
            names.append(name)
    return names


def calcular_plano(
    valor_total: Decimal | float | int | str,
    pct_entrada: Decimal | float | int | str,
    n_parcelas: int,
) -> dict[str, Any]:
    total = _money(valor_total)
    pct = Decimal(str(pct_entrada))
    max_parc = int(load_config().get("max_parcelas", 5))
    if pct < 0 or pct > 100:
        raise ValueError("Percentual de entrada deve estar entre 0 e 100")
    if n_parcelas < 1 or n_parcelas > max_parc:
        raise ValueError(f"Número de parcelas deve ser entre 1 e {max_parc}")

    valor_entrada = _money(total * pct / Decimal("100"))
    restante = _money(total - valor_entrada)
    if n_parcelas == 1:
        valores = [restante]
    else:
        base = _money(restante / Decimal(n_parcelas))
        valores = [base] * (n_parcelas - 1)
        valores.append(_money(restante - base * (n_parcelas - 1)))

    return {
        "valor_total": total,
        "pct_entrada": pct,
        "valor_entrada": valor_entrada,
        "n_parcelas": n_parcelas,
        "restante": restante,
        "valores_parcelas": valores,
        "valor_parcela": valores[0] if valores else Decimal("0.00"),
    }


def effective_status(status: str, vencimento: date | None, today: date | None = None) -> str:
    status = (status or STATUS_PENDENTE).strip().lower()
    if status in {STATUS_PAGO, STATUS_CANCELADO}:
        return status
    today = today or date.today()
    if vencimento and vencimento < today:
        return "atrasado"
    return STATUS_PENDENTE


def _client() -> gspread.Client:
    return gspread.authorize(get_google_credentials(scopes=SCOPES))


def _ensure_worksheet(spreadsheet: gspread.Spreadsheet, title: str, headers: list[str]) -> gspread.Worksheet:
    try:
        ws = _api_retry(lambda: spreadsheet.worksheet(title))
    except gspread.exceptions.WorksheetNotFound:
        ws = _api_retry(lambda: spreadsheet.add_worksheet(title=title, rows=2000, cols=len(headers) + 2))
        _api_retry(lambda: ws.update("A1", [headers], value_input_option="USER_ENTERED"))
        return ws

    values = _api_retry(ws.get_all_values)
    if not values:
        _api_retry(lambda: ws.update("A1", [headers], value_input_option="USER_ENTERED"))
    elif [h.strip() for h in values[0]] != headers:
        # Mantém dados; só garante cabeçalho se a aba estiver vazia além do header.
        if len(values) == 1 and all(not _clean_cell(c) for c in values[0]):
            _api_retry(lambda: ws.update("A1", [headers], value_input_option="USER_ENTERED"))
    return ws


def ensure_workbook(*, create_if_missing: bool = False) -> dict[str, Any]:
    """Garante planilha + abas. Se create_if_missing e sem ID, cria no Drive da service account."""
    config = load_config()
    spreadsheet_id = str(config.get("spreadsheet_id", "")).strip()
    acordos_ws = str(config.get("acordos_worksheet") or "Acordos")
    parcelas_ws = str(config.get("parcelas_worksheet") or "Parcelas")
    title = str(config.get("titulo_planilha") or "Controle Parcelamentos — Cobrança")

    client = _client()
    if not spreadsheet_id:
        if not create_if_missing:
            raise ValueError(
                "Planilha de parcelamentos não configurada. "
                "Rode: python scripts/setup_parcelamentos_sheet.py"
            )
        spreadsheet = _api_retry(lambda: client.create(title))
        spreadsheet_id = spreadsheet.id
        config["spreadsheet_id"] = spreadsheet_id
        save_config(config)
        try:
            default = spreadsheet.sheet1
            if default.title not in {acordos_ws, parcelas_ws}:
                _api_retry(lambda: default.update_title(acordos_ws))
        except Exception:
            pass
    else:
        spreadsheet = _api_retry(lambda: client.open_by_key(spreadsheet_id))

    _ensure_worksheet(spreadsheet, acordos_ws, ACORDOS_HEADERS)
    _ensure_worksheet(spreadsheet, parcelas_ws, PARCELAS_HEADERS)
    return {
        "ok": True,
        "spreadsheet_id": spreadsheet_id,
        "url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
    }


def _load_local() -> dict[str, list[dict[str, Any]]]:
    if not LOCAL_STORE_PATH.exists():
        return {"acordos": [], "parcelas": []}
    return json.loads(LOCAL_STORE_PATH.read_text(encoding="utf-8"))


def _save_local(store: dict[str, list[dict[str, Any]]]) -> None:
    LOCAL_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_STORE_PATH.write_text(json.dumps(store, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _rows_from_worksheet(ws: gspread.Worksheet, headers: list[str]) -> list[dict[str, Any]]:
    values = _api_retry(ws.get_all_values)
    if not values:
        return []
    head = [h.strip() for h in values[0]]
    rows: list[dict[str, Any]] = []
    for raw in values[1:]:
        if not any(_clean_cell(c) for c in raw):
            continue
        item = {h: _clean_cell(raw[i] if i < len(raw) else "") for i, h in enumerate(head)}
        # Normaliza chaves esperadas
        normalized = {h: item.get(h, "") for h in headers}
        rows.append(normalized)
    return rows


def load_acordos() -> list[dict[str, Any]]:
    if not spreadsheet_configured():
        return list(_load_local().get("acordos", []))
    config = load_config()
    spreadsheet = _api_retry(lambda: _client().open_by_key(str(config["spreadsheet_id"]).strip()))
    ws = _ensure_worksheet(spreadsheet, str(config.get("acordos_worksheet") or "Acordos"), ACORDOS_HEADERS)
    return _rows_from_worksheet(ws, ACORDOS_HEADERS)


def load_parcelas() -> list[dict[str, Any]]:
    if not spreadsheet_configured():
        return list(_load_local().get("parcelas", []))
    config = load_config()
    spreadsheet = _api_retry(lambda: _client().open_by_key(str(config["spreadsheet_id"]).strip()))
    ws = _ensure_worksheet(spreadsheet, str(config.get("parcelas_worksheet") or "Parcelas"), PARCELAS_HEADERS)
    return _rows_from_worksheet(ws, PARCELAS_HEADERS)


def _append_acordo_sheets(acordo: dict[str, Any], parcelas: list[dict[str, Any]]) -> None:
    config = load_config()
    spreadsheet = _api_retry(lambda: _client().open_by_key(str(config["spreadsheet_id"]).strip()))
    ws_a = _ensure_worksheet(spreadsheet, str(config.get("acordos_worksheet") or "Acordos"), ACORDOS_HEADERS)
    ws_p = _ensure_worksheet(spreadsheet, str(config.get("parcelas_worksheet") or "Parcelas"), PARCELAS_HEADERS)
    acordo_row = [str(acordo.get(h, "")) for h in ACORDOS_HEADERS]
    parcela_rows = [[str(p.get(h, "")) for h in PARCELAS_HEADERS] for p in parcelas]
    _api_retry(lambda: ws_a.append_row(acordo_row, value_input_option="USER_ENTERED"))
    if parcela_rows:
        _api_retry(lambda: ws_p.append_rows(parcela_rows, value_input_option="USER_ENTERED"))


def criar_acordo(
    *,
    agente: str,
    cpf: str,
    ccb: str,
    produto: str,
    valor_total: Decimal | float | int | str,
    valor_entrada: Decimal | float | int | str,
    valores_parcelas: list[Decimal | float | int | str],
    data_entrada: date,
    vencimentos_parcelas: list[date],
    formalizacao: date,
    n_parcelas: int | None = None,
    pct_entrada: Decimal | float | int | str | None = None,
    cliente: str = "",
    telefone: str = "",
    observacao: str = "",
) -> dict[str, Any]:
    """Cria acordo com campos obrigatórios da operação."""
    agente = _clean_cell(agente)
    ccb = _clean_cell(ccb)
    produto = _clean_cell(produto)
    cpf_fmt = validar_cpf(cpf)

    if not agente:
        raise ValueError("Informe o agente")
    if not ccb:
        raise ValueError("Informe o CCB")
    if not produto:
        raise ValueError("Informe o produto")
    if formalizacao is None:
        raise ValueError("Informe a data de formalização")
    if data_entrada is None:
        raise ValueError("Informe a data da entrada")

    total = _money(valor_total)
    entrada = _money(valor_entrada)
    if total <= 0:
        raise ValueError("Valor total do acordo deve ser maior que zero")
    if entrada <= 0:
        raise ValueError("Valor da entrada deve ser maior que zero")
    if entrada > total:
        raise ValueError("Valor da entrada não pode ser maior que o valor total")

    valores = [_money(v) for v in valores_parcelas]
    if not valores:
        raise ValueError("Informe o valor das parcelas")
    if any(v <= 0 for v in valores):
        raise ValueError("Cada parcela deve ter valor maior que zero")
    n = n_parcelas if n_parcelas is not None else len(valores)
    if n != len(valores):
        raise ValueError("Quantidade de valores de parcela não confere com o número de parcelas")
    if len(vencimentos_parcelas) != n:
        raise ValueError(f"Informe o vencimento das {n} parcela(s)")
    if any(v is None for v in vencimentos_parcelas):
        raise ValueError("Todos os vencimentos das parcelas são obrigatórios")

    # Demais parcelas iguais: com total = entrada + n×valor, a soma fecha exatamente.
    esperado = _money(total - entrada)
    base = valores[0]
    if any(v != base for v in valores):
        soma_parcelas = sum(valores, start=Decimal("0.00"))
        if abs(soma_parcelas - esperado) > Decimal("0.05"):
            raise ValueError(
                f"Soma das parcelas ({_fmt_money(soma_parcelas)}) deve fechar o restante "
                f"após a entrada ({_fmt_money(esperado)})"
            )
    else:
        if abs(_money(base * n) - esperado) > Decimal("0.05"):
            raise ValueError(
                f"{n}x de {_fmt_money(base)} = {_fmt_money(base * n)}, "
                f"mas o restante é {_fmt_money(esperado)}."
            )
        valores = [base] * n

    if pct_entrada is None:
        pct = _money(entrada * Decimal("100") / total) if total else Decimal("0")
    else:
        pct = Decimal(str(pct_entrada))

    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    acordo_id = uuid.uuid4().hex[:12]
    cliente_txt = _clean_cell(cliente)
    telefone_txt = _clean_cell(telefone)
    acordo = {
        "acordo_id": acordo_id,
        "created_at": now,
        "formalizacao": _fmt_date(formalizacao),
        "agente": agente,
        "cpf": cpf_fmt,
        "ccb": ccb,
        "produto": produto,
        "cliente": cliente_txt,
        "telefone": telefone_txt,
        "valor_total": _fmt_money(total),
        "pct_entrada": str(pct).replace(".", ","),
        "valor_entrada": _fmt_money(entrada),
        "data_entrada": _fmt_date(data_entrada),
        "n_parcelas": str(n),
        "valor_parcela": _fmt_money(valores[0]),
        "status_acordo": "ativo",
        "observacao": _clean_cell(observacao),
    }

    parcelas: list[dict[str, Any]] = [
        {
            "parcela_id": f"{acordo_id}-E",
            "acordo_id": acordo_id,
            "agente": agente,
            "cpf": cpf_fmt,
            "ccb": ccb,
            "produto": produto,
            "cliente": cliente_txt,
            "telefone": telefone_txt,
            "tipo": TIPO_ENTRADA,
            "numero": "0",
            "vencimento": _fmt_date(data_entrada),
            "valor": _fmt_money(entrada),
            "status": STATUS_PENDENTE,
            "pago_em": "",
            "formalizacao": _fmt_date(formalizacao),
            "observacao": "",
            "created_at": now,
        }
    ]
    for i, valor in enumerate(valores, start=1):
        parcelas.append(
            {
                "parcela_id": f"{acordo_id}-P{i}",
                "acordo_id": acordo_id,
                "agente": agente,
                "cpf": cpf_fmt,
                "ccb": ccb,
                "produto": produto,
                "cliente": cliente_txt,
                "telefone": telefone_txt,
                "tipo": TIPO_PARCELA,
                "numero": str(i),
                "vencimento": _fmt_date(vencimentos_parcelas[i - 1]),
                "valor": _fmt_money(valor),
                "status": STATUS_PENDENTE,
                "pago_em": "",
                "formalizacao": _fmt_date(formalizacao),
                "observacao": "",
                "created_at": now,
            }
        )

    if spreadsheet_configured():
        _append_acordo_sheets(acordo, parcelas)
    else:
        store = _load_local()
        store.setdefault("acordos", []).append(acordo)
        store.setdefault("parcelas", []).extend(parcelas)
        _save_local(store)

    return {"acordo": acordo, "parcelas": parcelas, "storage": "sheets" if spreadsheet_configured() else "local"}


def enrich_parcela(row: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    item = dict(row)
    venc = _parse_date(item.get("vencimento"))
    item["vencimento_date"] = venc
    item["valor_num"] = float(_parse_money(item.get("valor")))
    item["status_efetivo"] = effective_status(str(item.get("status", "")), venc, today=today)
    tipo = str(item.get("tipo", "")).lower()
    num = str(item.get("numero", ""))
    if tipo == TIPO_ENTRADA or num == "0":
        item["rotulo"] = "Entrada"
    else:
        item["rotulo"] = f"Parcela {num}"
    return item


def listar_parcelas_enriquecidas(
    *,
    agente: str | None = None,
    status_filtro: str | None = None,
    mes: int | None = None,
    ano: int | None = None,
    only_open: bool = False,
    today: date | None = None,
) -> list[dict[str, Any]]:
    today = today or date.today()
    rows = [enrich_parcela(r, today=today) for r in load_parcelas()]
    out: list[dict[str, Any]] = []
    for row in rows:
        if agente and _clean_cell(row.get("agente")).casefold() != agente.casefold():
            continue
        st_eff = row["status_efetivo"]
        if only_open and st_eff in {STATUS_PAGO, STATUS_CANCELADO}:
            continue
        if status_filtro and status_filtro != "todos":
            if status_filtro == "atrasado" and st_eff != "atrasado":
                continue
            if status_filtro == "pendente" and st_eff != STATUS_PENDENTE:
                continue
            if status_filtro == "pago" and st_eff != STATUS_PAGO:
                continue
            if status_filtro == "a_vencer" and st_eff != STATUS_PENDENTE:
                continue
        venc: date | None = row.get("vencimento_date")
        if mes is not None and ano is not None:
            if not venc or venc.month != mes or venc.year != ano:
                continue
        out.append(row)

    out.sort(key=lambda r: (r.get("vencimento_date") or date.max, r.get("ccb") or ""))
    return out


def parcelas_a_vencer(*, dias: int = 30, agente: str | None = None, today: date | None = None) -> list[dict[str, Any]]:
    today = today or date.today()
    limite = date.fromordinal(today.toordinal() + max(dias, 0))
    rows = listar_parcelas_enriquecidas(agente=agente, only_open=True, today=today)
    return [
        r
        for r in rows
        if r.get("vencimento_date")
        and today <= r["vencimento_date"] <= limite
        and r["status_efetivo"] == STATUS_PENDENTE
    ]


def parcelas_atrasadas(*, agente: str | None = None, today: date | None = None) -> list[dict[str, Any]]:
    return listar_parcelas_enriquecidas(agente=agente, status_filtro="atrasado", only_open=True, today=today)


def _update_parcela_status(parcela_id: str, status: str, pago_em: str = "") -> dict[str, Any]:
    parcela_id = _clean_cell(parcela_id)
    if not parcela_id:
        raise ValueError("parcela_id inválido")

    if not spreadsheet_configured():
        store = _load_local()
        found = None
        for row in store.get("parcelas", []):
            if _clean_cell(row.get("parcela_id")) == parcela_id:
                row["status"] = status
                row["pago_em"] = pago_em
                found = row
                break
        if not found:
            raise ValueError(f"Parcela {parcela_id} não encontrada")
        _save_local(store)
        return found

    config = load_config()
    spreadsheet = _api_retry(lambda: _client().open_by_key(str(config["spreadsheet_id"]).strip()))
    ws = _ensure_worksheet(spreadsheet, str(config.get("parcelas_worksheet") or "Parcelas"), PARCELAS_HEADERS)
    values = _api_retry(ws.get_all_values)
    if not values:
        raise ValueError("Aba Parcelas vazia")
    head = [h.strip() for h in values[0]]
    try:
        idx_id = head.index("parcela_id")
        idx_status = head.index("status")
        idx_pago = head.index("pago_em")
    except ValueError as exc:
        raise ValueError("Cabeçalhos da aba Parcelas incompletos") from exc

    for row_num, raw in enumerate(values[1:], start=2):
        if idx_id >= len(raw):
            continue
        if _clean_cell(raw[idx_id]) != parcela_id:
            continue
        _api_retry(lambda: ws.update_cell(row_num, idx_status + 1, status))
        _api_retry(lambda: ws.update_cell(row_num, idx_pago + 1, pago_em))
        item = {h: _clean_cell(raw[i] if i < len(raw) else "") for i, h in enumerate(head)}
        item["status"] = status
        item["pago_em"] = pago_em
        return item
    raise ValueError(f"Parcela {parcela_id} não encontrada")


def marcar_pago(parcela_id: str, pago_em: date | None = None) -> dict[str, Any]:
    return _update_parcela_status(parcela_id, STATUS_PAGO, pago_em=_fmt_date(pago_em or date.today()))


def marcar_pendente(parcela_id: str) -> dict[str, Any]:
    return _update_parcela_status(parcela_id, STATUS_PENDENTE, pago_em="")


def marcar_parcela_cancelada(parcela_id: str) -> dict[str, Any]:
    return _update_parcela_status(parcela_id, STATUS_CANCELADO, pago_em="")


def alerta_acordo(
    parcelas: list[dict[str, Any]],
    status_acordo: str = "",
    today: date | None = None,
) -> str:
    """
    - cancelado
    - em_atraso: vencimento passado sem pagamento
    - em_dia: parcela do mês paga e sem atraso
    - a_vencer: anteriores pagas e parcela do mês ainda a vencer
    """
    today = today or date.today()
    st_ac = (status_acordo or "").strip().casefold()
    if st_ac in {"cancelado", "cancelada", "quebra"}:
        return ALERTA_CANCELADO
    if not parcelas:
        return ALERTA_EM_DIA
    if all(str(p.get("status_efetivo", p.get("status", ""))).casefold() == STATUS_CANCELADO for p in parcelas):
        return ALERTA_CANCELADO

    ativos = [
        p
        for p in parcelas
        if str(p.get("status_efetivo", p.get("status", ""))).casefold() != STATUS_CANCELADO
    ]
    if not ativos:
        return ALERTA_CANCELADO

    if any(str(p.get("status_efetivo", "")).casefold() == "atrasado" for p in ativos):
        return ALERTA_EM_ATRASO

    do_mes = [
        p
        for p in ativos
        if p.get("vencimento_date")
        and p["vencimento_date"].month == today.month
        and p["vencimento_date"].year == today.year
    ]
    anteriores = [
        p
        for p in ativos
        if p.get("vencimento_date")
        and (
            p["vencimento_date"].year < today.year
            or (p["vencimento_date"].year == today.year and p["vencimento_date"].month < today.month)
        )
    ]
    anteriores_ok = (not anteriores) or all(
        str(p.get("status_efetivo", "")).casefold() == STATUS_PAGO for p in anteriores
    )

    if do_mes:
        if all(str(p.get("status_efetivo", "")).casefold() == STATUS_PAGO for p in do_mes) and anteriores_ok:
            return ALERTA_EM_DIA
        if anteriores_ok:
            return ALERTA_A_VENCER
        return ALERTA_A_VENCER

    futuras = [
        p
        for p in ativos
        if p.get("vencimento_date")
        and p["vencimento_date"] > today
        and str(p.get("status_efetivo", "")).casefold() != STATUS_PAGO
    ]
    if anteriores_ok and futuras:
        return ALERTA_A_VENCER
    if all(str(p.get("status_efetivo", "")).casefold() == STATUS_PAGO for p in ativos):
        return ALERTA_EM_DIA
    return ALERTA_A_VENCER


def resumo_acordos(*, agente: str | None = None, today: date | None = None) -> list[dict[str, Any]]:
    """Um card/linha por acordo, com alerta (em dia / atraso / a vencer / cancelado)."""
    today = today or date.today()
    acordos = {str(a.get("acordo_id", "")).strip(): a for a in load_acordos() if str(a.get("acordo_id", "")).strip()}
    parcelas = [enrich_parcela(r, today=today) for r in load_parcelas()]
    by_acordo: dict[str, list[dict[str, Any]]] = {}
    for p in parcelas:
        aid = str(p.get("acordo_id", "")).strip()
        if not aid:
            continue
        if agente and _clean_cell(p.get("agente")).casefold() != agente.casefold():
            continue
        by_acordo.setdefault(aid, []).append(p)

    rows: list[dict[str, Any]] = []
    for aid, plist in by_acordo.items():
        meta = acordos.get(aid, {})
        alerta = alerta_acordo(plist, status_acordo=str(meta.get("status_acordo", "")), today=today)
        abertas = [p for p in plist if p.get("status_efetivo") not in {STATUS_PAGO, STATUS_CANCELADO}]
        atrasadas = [p for p in plist if p.get("status_efetivo") == "atrasado"]
        sample = plist[0]
        rows.append(
            {
                "acordo_id": aid,
                "alerta": alerta,
                "alerta_label": ALERTA_LABELS.get(alerta, alerta),
                "ccb": sample.get("ccb") or meta.get("ccb", ""),
                "cpf": sample.get("cpf") or meta.get("cpf", ""),
                "produto": sample.get("produto") or meta.get("produto", ""),
                "agente": sample.get("agente") or meta.get("agente", ""),
                "formalizacao": sample.get("formalizacao") or meta.get("formalizacao", ""),
                "valor_total": meta.get("valor_total", ""),
                "n_parcelas": meta.get("n_parcelas", ""),
                "parcelas_abertas": len(abertas),
                "parcelas_atrasadas": len(atrasadas),
                "parcelas_total": len(plist),
                "status_acordo": meta.get("status_acordo", ""),
            }
        )

    order = {
        ALERTA_EM_ATRASO: 0,
        ALERTA_A_VENCER: 1,
        ALERTA_EM_DIA: 2,
        ALERTA_CANCELADO: 3,
    }
    rows.sort(key=lambda r: (order.get(r["alerta"], 9), r.get("ccb") or ""))
    return rows


def _update_acordo_status(acordo_id: str, status_acordo: str) -> None:
    acordo_id = _clean_cell(acordo_id)
    if not acordo_id:
        raise ValueError("acordo_id inválido")
    if not spreadsheet_configured():
        store = _load_local()
        for row in store.get("acordos", []):
            if _clean_cell(row.get("acordo_id")) == acordo_id:
                row["status_acordo"] = status_acordo
                _save_local(store)
                return
        raise ValueError(f"Acordo {acordo_id} não encontrado")

    config = load_config()
    spreadsheet = _api_retry(lambda: _client().open_by_key(str(config["spreadsheet_id"]).strip()))
    ws = _ensure_worksheet(spreadsheet, str(config.get("acordos_worksheet") or "Acordos"), ACORDOS_HEADERS)
    values = _api_retry(ws.get_all_values)
    if not values:
        raise ValueError("Aba Acordos vazia")
    head = [h.strip() for h in values[0]]
    idx_id = head.index("acordo_id")
    idx_st = head.index("status_acordo")
    for row_num, raw in enumerate(values[1:], start=2):
        if idx_id < len(raw) and _clean_cell(raw[idx_id]) == acordo_id:
            _api_retry(lambda: ws.update_cell(row_num, idx_st + 1, status_acordo))
            return
    raise ValueError(f"Acordo {acordo_id} não encontrado")


def cancelar_acordo(acordo_id: str) -> dict[str, Any]:
    """Mantém no histórico: status_acordo=cancelado e parcelas abertas → cancelado."""
    acordo_id = _clean_cell(acordo_id)
    _update_acordo_status(acordo_id, STATUS_CANCELADO)
    canceladas = 0
    for p in load_parcelas():
        if _clean_cell(p.get("acordo_id")) != acordo_id:
            continue
        st = str(p.get("status", "")).strip().lower()
        if st in {STATUS_PAGO, STATUS_CANCELADO}:
            continue
        marcar_parcela_cancelada(str(p.get("parcela_id", "")))
        canceladas += 1
    return {"acordo_id": acordo_id, "parcelas_canceladas": canceladas}


def cancelar_acordos_por_ccbs(ccbs: list[str]) -> dict[str, Any]:
    """Cancela acordos por CCB em lote (evita estourar cota da API Sheets)."""
    wanted = {_clean_cell(c) for c in ccbs if _clean_cell(c)}
    if not wanted:
        return {"cancelados": [], "ccbs_nao_encontrados": [], "parcelas_atualizadas": 0}

    if not spreadsheet_configured():
        store = _load_local()
        done: list[str] = []
        missing: list[str] = []
        found_ccbs: set[str] = set()
        for a in store.get("acordos", []):
            ccb = _clean_cell(a.get("ccb"))
            if ccb in wanted:
                a["status_acordo"] = STATUS_CANCELADO
                done.append(_clean_cell(a.get("acordo_id")))
                found_ccbs.add(ccb)
        aids = set(done)
        n_parc = 0
        for p in store.get("parcelas", []):
            if _clean_cell(p.get("acordo_id")) not in aids:
                continue
            st = str(p.get("status", "")).strip().lower()
            if st in {STATUS_PAGO, STATUS_CANCELADO}:
                continue
            p["status"] = STATUS_CANCELADO
            p["pago_em"] = ""
            n_parc += 1
        _save_local(store)
        missing = sorted(wanted - found_ccbs)
        return {"cancelados": done, "ccbs_nao_encontrados": missing, "parcelas_atualizadas": n_parc}

    config = load_config()
    spreadsheet = _api_retry(lambda: _client().open_by_key(str(config["spreadsheet_id"]).strip()))
    ws_a = _ensure_worksheet(spreadsheet, str(config.get("acordos_worksheet") or "Acordos"), ACORDOS_HEADERS)
    ws_p = _ensure_worksheet(spreadsheet, str(config.get("parcelas_worksheet") or "Parcelas"), PARCELAS_HEADERS)

    vals_a = _api_retry(ws_a.get_all_values)
    vals_p = _api_retry(ws_p.get_all_values)
    if not vals_a or not vals_p:
        raise ValueError("Abas Acordos/Parcelas vazias")

    head_a = [h.strip() for h in vals_a[0]]
    head_p = [h.strip() for h in vals_p[0]]
    idx_aid = head_a.index("acordo_id")
    idx_ccb_a = head_a.index("ccb")
    idx_st_a = head_a.index("status_acordo")
    idx_pid = head_p.index("parcela_id")
    idx_aid_p = head_p.index("acordo_id")
    idx_st_p = head_p.index("status")
    idx_pago = head_p.index("pago_em")

    done: list[str] = []
    found_ccbs: set[str] = set()
    acordo_updates: list[dict[str, Any]] = []
    for row_num, raw in enumerate(vals_a[1:], start=2):
        ccb = _clean_cell(raw[idx_ccb_a] if idx_ccb_a < len(raw) else "")
        aid = _clean_cell(raw[idx_aid] if idx_aid < len(raw) else "")
        if ccb not in wanted or not aid:
            continue
        found_ccbs.add(ccb)
        done.append(aid)
        acordo_updates.append(
            {"range": f"{gspread.utils.rowcol_to_a1(row_num, idx_st_a + 1)}", "values": [[STATUS_CANCELADO]]}
        )

    aids = set(done)
    parcela_updates: list[dict[str, Any]] = []
    n_parc = 0
    for row_num, raw in enumerate(vals_p[1:], start=2):
        aid = _clean_cell(raw[idx_aid_p] if idx_aid_p < len(raw) else "")
        if aid not in aids:
            continue
        st = _clean_cell(raw[idx_st_p] if idx_st_p < len(raw) else "").lower()
        if st in {STATUS_PAGO, STATUS_CANCELADO}:
            continue
        parcela_updates.append(
            {"range": f"{gspread.utils.rowcol_to_a1(row_num, idx_st_p + 1)}", "values": [[STATUS_CANCELADO]]}
        )
        parcela_updates.append(
            {"range": f"{gspread.utils.rowcol_to_a1(row_num, idx_pago + 1)}", "values": [[""]]}
        )
        n_parc += 1

    # batch update em pedaços
    def _flush(ws: gspread.Worksheet, updates: list[dict[str, Any]]) -> None:
        for i in range(0, len(updates), 80):
            chunk = updates[i : i + 80]
            _api_retry(lambda c=chunk: ws.batch_update(c, value_input_option="USER_ENTERED"))

    if acordo_updates:
        _flush(ws_a, acordo_updates)
    if parcela_updates:
        _flush(ws_p, parcela_updates)

    return {
        "cancelados": done,
        "ccbs_nao_encontrados": sorted(wanted - found_ccbs),
        "parcelas_atualizadas": n_parc,
    }
