"""Export builders: copy-paste negative list, Google Ads Editor CSV and the
client-ready multi-tab Excel audit workbook (all generated in-memory)."""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from src.constants import APP_NAME, AUTHOR_NAME, GITHUB_URL, WHATSAPP_URL

MATCH_TYPES = ("Exact", "Phrase", "Broad")
LEVELS = ("Account Negative List", "Campaign", "Ad Group")

EDITOR_CSV_COLUMNS = ("Campaign", "Ad group", "Keyword", "Criterion Type")
EXCEL_SHEETS = ("Executive Summary", "Top Wasted N-Grams", "Flagged Search Terms",
                "Approved Negative List")


# ---------------------------------------------------------------------------
# Copy-paste block
# ---------------------------------------------------------------------------
def format_negative(keyword: str, match_type: str) -> str:
    """Format a keyword with Google Ads match-type syntax."""
    kw = str(keyword).strip()
    if match_type == "Exact":
        return f"[{kw}]"
    if match_type == "Phrase":
        return f'"{kw}"'
    return kw


def build_copy_paste_block(
    keywords: list[str],
    match_type: str,
    level: str = "Account Negative List",
    campaign: str = "",
    ad_group: str = "",
) -> str:
    """Ready-to-paste negative keyword list for Google Ads UI."""
    lines = [
        f"# {APP_NAME} — Negative Keyword List",
        f"# Match type: {match_type} | Level: {level}",
    ]
    if campaign:
        lines.append(f"# Campaign: {campaign}")
    if ad_group:
        lines.append(f"# Ad group: {ad_group}")
    lines.append(f"# {len(keywords)} keywords | generated {datetime.now():%Y-%m-%d}")
    lines.extend(format_negative(kw, match_type) for kw in keywords)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Google Ads Editor CSV
# ---------------------------------------------------------------------------
def build_editor_csv(
    keywords: list[str],
    match_type: str,
    level: str,
    campaign: str = "",
    ad_group: str = "",
) -> str:
    """Bulk-import CSV for Google Ads Editor.

    Columns: Campaign, Ad group, Keyword, Criterion Type. Match type is
    embedded in the keyword string ([exact] / "phrase" / broad). For the
    Account Negative List level, campaign/ad group cells are left blank —
    use the copy-paste block for account-level lists in the Google Ads UI.
    """
    campaign_cell, ad_group_cell = "", ""
    if level == "Campaign":
        campaign_cell = campaign
    elif level == "Ad Group":
        campaign_cell, ad_group_cell = campaign, ad_group

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EDITOR_CSV_COLUMNS)
    for kw in keywords:
        writer.writerow(
            [campaign_cell, ad_group_cell, format_negative(kw, match_type), "Negative"]
        )
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Client-ready Excel audit workbook
# ---------------------------------------------------------------------------
_DARK_FILL = PatternFill("solid", fgColor="0F172A")
_BRAND_FILL = PatternFill("solid", fgColor="059669")
_LIGHT_ROW_FILL = PatternFill("solid", fgColor="F8FAFC")
_HEADER_FONT = Font(color="FFFFFF", bold=True, size=11)
_TITLE_FONT = Font(color="0F172A", bold=True, size=16)
_SUB_FONT = Font(color="475569", size=11)
_KPI_FONT = Font(color="0F172A", bold=True, size=14)


def build_excel_report(
    summary: dict,
    top_ngrams: pd.DataFrame,
    flagged_terms: pd.DataFrame,
    negatives: pd.DataFrame,
    currency: str = "$",
) -> bytes:
    """Build the branded multi-tab client audit workbook in-memory.

    Tabs: Executive Summary, Top Wasted N-Grams, Flagged Search Terms,
    Approved Negative List — with formatted headers, currency number
    formats and auto-adjusted column widths.
    """
    wb = Workbook()

    money_fmt = f'"{currency}" #,##0.00'
    _write_exec_summary(wb.active, summary, money_fmt)

    ngram_cols = {
        "N-Gram": ("text", None),
        "Query Count": ("int", None),
        "Clicks": ("int", None),
        "Cost": ("money", money_fmt),
        "Conversions": ("int", None),
        "CPA": ("money", money_fmt),
        "Wasted Spend": ("money", money_fmt),
        "Waste Reason": ("text", None),
        "Priority Score": ("float", "0.0"),
    }
    _write_table_sheet(
        wb.create_sheet("Top Wasted N-Grams"), top_ngrams, ngram_cols
    )

    term_cols = {
        "Search term": ("text", None),
        "Campaign": ("text", None),
        "Ad group": ("text", None),
        "Match type": ("text", None),
        "Clicks": ("int", None),
        "Cost": ("money", money_fmt),
        "Conversions": ("int", None),
        "CPA": ("money", money_fmt),
        "Wasted Spend": ("money", money_fmt),
        "Waste Reason": ("text", None),
    }
    _write_table_sheet(wb.create_sheet("Flagged Search Terms"), flagged_terms, term_cols)

    neg_cols = {
        "Keyword": ("text", None),
        "Match Type": ("text", None),
        "Level": ("text", None),
        "Campaign": ("text", None),
        "Ad Group": ("text", None),
        "Source": ("text", None),
        "Reason": ("text", None),
        "Wasted Spend": ("money", money_fmt),
    }
    _write_table_sheet(wb.create_sheet("Approved Negative List"), negatives, neg_cols)

    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _write_exec_summary(ws, summary: dict, money_fmt: str) -> None:
    ws.title = "Executive Summary"
    ws.sheet_view.showGridLines = False

    ws["B2"] = f"{APP_NAME} — Google Ads Waste Audit"
    ws["B2"].font = _TITLE_FONT
    ws["B3"] = (
        f"Generated {datetime.now():%Y-%m-%d %H:%M} | window: "
        f"{summary.get('date_range') or 'last 30 days'} "
        f"({summary.get('days', 30)} days) | currency {summary.get('currency', '$')}"
    )
    ws["B3"].font = _SUB_FONT

    kpis = [
        ("Total Spend Analyzed", summary.get("total_spend", 0.0), money_fmt),
        ("Flagged Wasted Spend", summary.get("wasted_spend", 0.0), money_fmt),
        ("Waste Share of Spend", summary.get("waste_pct", 0.0), '0.0"%"'),
        ("Projected Annualized Savings", summary.get("annualized_savings", 0.0), money_fmt),
        ("Wasted Search Terms", summary.get("wasted_terms", 0), "#,##0"),
        ("Wasted N-Grams (1-4)", summary.get("wasted_ngrams", 0), "#,##0"),
    ]
    start = 5
    for i, (label, value, fmt) in enumerate(kpis):
        row = start + i
        label_cell = ws.cell(row=row, column=2, value=label)
        label_cell.font = Font(color="475569", bold=True, size=10)
        value_cell = ws.cell(row=row, column=3, value=float(value) if isinstance(value, (int, float)) else value)
        value_cell.number_format = fmt
        value_cell.font = _KPI_FONT
        value_cell.fill = _LIGHT_ROW_FILL

    config_start = start + len(kpis) + 2
    ws.cell(row=config_start - 1, column=2, value="Detection Settings").font = Font(
        color="0F172A", bold=True, size=12
    )
    config_rows = [
        ("Target CPA", summary.get("target_cpa", "")),
        ("CPA Bleeder Multiplier", summary.get("cpa_multiplier", "")),
        ("Zero-Conv Spend Threshold", summary.get("zero_conv_threshold", "")),
        ("Minimum Clicks Threshold", summary.get("min_clicks", "")),
        ("Brand & Protected Terms", summary.get("brand_terms", "")),
        ("Enabled Preset Dictionaries", summary.get("presets", "")),
        ("Negative Match Type", summary.get("match_type", "")),
        ("Negative Level", summary.get("level", "")),
    ]
    for i, (label, value) in enumerate(config_rows):
        ws.cell(row=config_start + i, column=2, value=label).font = Font(
            color="475569", size=10
        )
        ws.cell(row=config_start + i, column=3, value=str(value)).font = Font(
            color="0F172A", size=10
        )

    footer_row = config_start + len(config_rows) + 2
    ws.cell(row=footer_row, column=2, value="Privacy: 100% in-memory processing — client CSV data is never saved or logged.").font = Font(color="64748B", size=9, italic=True)
    ws.cell(row=footer_row + 1, column=2, value=f"Prepared by {AUTHOR_NAME} — {WHATSAPP_URL} | {GITHUB_URL}").font = Font(color="059669", size=10, bold=True)

    ws.column_dimensions["A"].width = 2
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 24


def _write_table_sheet(ws, df: pd.DataFrame, column_specs: dict) -> None:
    ws.sheet_view.showGridLines = False
    if df is None or df.empty:
        ws["A1"] = "No rows to export for this section."
        ws["A1"].font = _SUB_FONT
        return

    headers = [col for col in column_specs if col in df.columns]
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = _DARK_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = "A2"

    subset = df[headers]
    for row_idx, (_, record) in enumerate(subset.iterrows(), start=2):
        for col_idx, header in enumerate(headers, start=1):
            value = record[header]
            kind, fmt = column_specs[header]
            if pd.isna(value):
                value = "" if kind == "text" else 0
            elif kind == "int":
                value = int(round(float(value)))
                fmt = fmt or "#,##0"
            elif kind in ("money", "float"):
                value = float(value)
            else:
                value = str(value)
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            if fmt:
                cell.number_format = fmt
            if row_idx % 2 == 0:
                cell.fill = _LIGHT_ROW_FILL

    for col_idx, header in enumerate(headers, start=1):
        width = max(
            [len(str(header)) + 4]
            + [min(len(str(v)) + 2, 55) for v in subset[header].head(200).tolist()]
        )
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def safe_filename(text: str) -> str:
    """Filesystem-safe string for download filenames."""
    cleaned = re.sub(r"[^\w\-]+", "_", str(text)).strip("_")
    return cleaned or "report"
