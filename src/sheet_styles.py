"""Formatação visual das abas — estilo dashboard."""

from __future__ import annotations

from typing import Any

import gspread

PRIMARY = {"red": 0.12, "green": 0.23, "blue": 0.37}
PRIMARY_LIGHT = {"red": 0.85, "green": 0.91, "blue": 0.98}
WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
GRAY_LIGHT = {"red": 0.96, "green": 0.97, "blue": 0.98}
GRAY_TEXT = {"red": 0.35, "green": 0.38, "blue": 0.43}
TOTAL_BG = {"red": 0.75, "green": 0.85, "blue": 0.95}


def _fmt(
    bg: dict[str, float] | None = None,
    fg: dict[str, float] | None = None,
    bold: bool = False,
    size: int = 10,
    align: str = "LEFT",
) -> dict[str, Any]:
    fmt: dict[str, Any] = {
        "textFormat": {"fontSize": size, "bold": bold},
        "verticalAlignment": "MIDDLE",
        "horizontalAlignment": align,
    }
    if fg:
        fmt["textFormat"]["foregroundColor"] = fg
    if bg:
        fmt["backgroundColor"] = bg
    return fmt


def _merge_row(spreadsheet: gspread.Spreadsheet, ws: gspread.Worksheet, row: int, cols: int) -> None:
    spreadsheet.batch_update(
        {
            "requests": [
                {
                    "mergeCells": {
                        "range": {
                            "sheetId": ws.id,
                            "startRowIndex": row - 1,
                            "endRowIndex": row,
                            "startColumnIndex": 0,
                            "endColumnIndex": cols,
                        },
                        "mergeType": "MERGE_ALL",
                    }
                }
            ]
        }
    )


def _set_col_widths(spreadsheet: gspread.Spreadsheet, ws: gspread.Worksheet, widths: list[int]) -> None:
    requests = []
    for idx, width in enumerate(widths):
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": ws.id,
                        "dimension": "COLUMNS",
                        "startIndex": idx,
                        "endIndex": idx + 1,
                    },
                    "properties": {"pixelSize": width},
                    "fields": "pixelSize",
                }
            }
        )
    if requests:
        spreadsheet.batch_update({"requests": requests})


def style_resumo(
    spreadsheet: gspread.Spreadsheet,
    ws: gspread.Worksheet,
    num_agents: int,
) -> None:
    header_row = 12
    first_data = 13
    last_data = 12 + num_agents
    total_row = 14 + num_agents if num_agents else 15

    _merge_row(spreadsheet, ws, 1, 4)
    ws.format("A1:D1", _fmt(bg=PRIMARY, fg=WHITE, bold=True, size=16, align="CENTER"))
    ws.format("A2:B3", _fmt(fg=GRAY_TEXT, size=9))

    ws.format("A5:B5", _fmt(bg=PRIMARY, fg=WHITE, bold=True))
    ws.format("A6:B10", _fmt(bg=GRAY_LIGHT))
    ws.format("B6:B10", _fmt(bg=GRAY_LIGHT, bold=True, align="RIGHT"))
    ws.format("B8:B10", _fmt(bg=PRIMARY_LIGHT, bold=True, align="RIGHT"))

    ws.format(f"A{header_row}:D{header_row}", _fmt(bg=PRIMARY, fg=WHITE, bold=True, align="CENTER"))
    if num_agents:
        for i, row in enumerate(range(first_data, last_data + 1)):
            bg = WHITE if i % 2 == 0 else GRAY_LIGHT
            ws.format(f"A{row}:D{row}", _fmt(bg=bg))
            ws.format(f"B{row}:C{row}", _fmt(bg=bg, align="CENTER"))
            ws.format(f"D{row}", _fmt(bg=bg, align="CENTER", bold=True))

    ws.format(f"A{total_row}:D{total_row}", _fmt(bg=TOTAL_BG, bold=True))
    ws.format(f"B{total_row}:D{total_row}", _fmt(bg=TOTAL_BG, bold=True, align="CENTER"))

    ws.freeze(rows=header_row)
    _set_col_widths(spreadsheet, ws, [220, 90, 90, 110])


def style_detail_table(
    spreadsheet: gspread.Spreadsheet,
    ws: gspread.Worksheet,
    num_rows: int,
    cols: int = 6,
) -> None:
    col_letter = chr(ord("A") + cols - 1)
    ws.format(f"A1:{col_letter}1", _fmt(bg=PRIMARY, fg=WHITE, bold=True, align="CENTER"))
    if num_rows:
        for i in range(num_rows):
            row = i + 2
            bg = WHITE if i % 2 == 0 else GRAY_LIGHT
            ws.format(f"A{row}:{col_letter}{row}", _fmt(bg=bg))
    ws.freeze(rows=1)
    widths = [180, 110, 160, 140, 260, 130][:cols]
    _set_col_widths(spreadsheet, ws, widths)


def style_cpc_matrix(
    spreadsheet: gspread.Spreadsheet,
    ws: gspread.Worksheet,
    num_cols: int,
    num_agents: int,
) -> None:
    if num_cols < 2:
        return
    col_letter = chr(ord("A") + num_cols - 1)
    _merge_row(spreadsheet, ws, 1, num_cols)
    ws.format(f"A1:{col_letter}1", _fmt(bg=PRIMARY, fg=WHITE, bold=True, size=14, align="CENTER"))
    ws.format("A2", _fmt(fg=GRAY_TEXT, size=9))

    header_row = 4
    ws.format(f"A{header_row}:{col_letter}{header_row}", _fmt(bg=PRIMARY, fg=WHITE, bold=True, align="CENTER"))

    first_data = 5
    last_data = 4 + num_agents
    for i, row in enumerate(range(first_data, last_data + 1)):
        bg = WHITE if i % 2 == 0 else GRAY_LIGHT
        ws.format(f"A{row}:{col_letter}{row}", _fmt(bg=bg))
        ws.format(f"B{row}:{col_letter}{row}", _fmt(bg=bg, align="CENTER"))

    total_row = last_data + 1
    ws.format(f"A{total_row}:{col_letter}{total_row}", _fmt(bg=TOTAL_BG, bold=True, align="CENTER"))

    ws.freeze(rows=header_row, cols=1)
    widths = [200] + [105] * (num_cols - 1)
    _set_col_widths(spreadsheet, ws, widths)


def style_cpc_por_tipo(ws: gspread.Worksheet, spreadsheet: gspread.Spreadsheet) -> None:
    _merge_row(spreadsheet, ws, 1, 2)
    ws.format("A1:B1", _fmt(bg=PRIMARY, fg=WHITE, bold=True, size=14, align="CENTER"))
    ws.format("A2:B3", _fmt(fg=GRAY_TEXT, size=9))
    ws.freeze(rows=3)
    _set_col_widths(spreadsheet, ws, [220, 100])

    values = ws.get_all_values()
    for idx, row in enumerate(values, start=1):
        if len(row) >= 2 and row[0] and row[1] == "Ligações":
            ws.format(f"A{idx}:B{idx}", _fmt(bg=PRIMARY, fg=WHITE, bold=True, align="CENTER"))
        elif len(row) >= 2 and row[0] == "TOTAL":
            ws.format(f"A{idx}:B{idx}", _fmt(bg=TOTAL_BG, bold=True, align="CENTER"))
        elif row and row[0] and (len(row) == 1 or not row[1]):
            if row[0] not in ("CPC por tipo de finalização", "Atualizado em", "Data referência"):
                ws.format(f"A{idx}:B{idx}", _fmt(bg=PRIMARY_LIGHT, bold=True))
