"""Tests for the export suite: copy-paste block, Editor CSV, Excel workbook."""

import csv
import io

import pandas as pd
from openpyxl import load_workbook

from src.exporter import (
    build_copy_paste_block,
    build_editor_csv,
    build_excel_report,
    format_negative,
    safe_filename,
)

KEYWORDS = ["cheap shoes", "free shipping", "red boots"]


def test_format_negative_match_types():
    assert format_negative("cheap shoes", "Exact") == "[cheap shoes]"
    assert format_negative("cheap shoes", "Phrase") == '"cheap shoes"'
    assert format_negative("cheap shoes", "Broad") == "cheap shoes"


def test_copy_paste_block():
    block = build_copy_paste_block(KEYWORDS, "Phrase", "Campaign", campaign="Search - Brand")
    lines = block.splitlines()
    assert any("#" in line for line in lines[:4])
    assert '"cheap shoes"' in lines
    assert '"free shipping"' in lines
    assert '"red boots"' in lines
    assert len([line for line in lines if line.startswith('"')]) == 3


def test_editor_csv_campaign_level():
    content = build_editor_csv(KEYWORDS, "Exact", "Campaign", campaign="Search - Brand")
    rows = list(csv.reader(io.StringIO(content)))
    assert rows[0] == ["Campaign", "Ad group", "Keyword", "Criterion Type"]
    assert len(rows) == 4
    for row in rows[1:]:
        assert row[0] == "Search - Brand"
        assert row[1] == ""
        assert row[3] == "Negative"
        assert row[2].startswith("[") and row[2].endswith("]")


def test_editor_csv_ad_group_level():
    content = build_editor_csv(["cheap shoes"], "Broad", "Ad Group",
                               campaign="Search", ad_group="AG1")
    rows = list(csv.reader(io.StringIO(content)))
    assert rows[1] == ["Search", "AG1", "cheap shoes", "Negative"]


def test_editor_csv_account_level_blank_campaign():
    content = build_editor_csv(KEYWORDS, "Phrase", "Account Negative List")
    rows = list(csv.reader(io.StringIO(content)))
    for row in rows[1:]:
        assert row[0] == "" and row[1] == ""


def _sample_frames():
    ngrams = pd.DataFrame(
        {
            "N-Gram": ["jobs", "free", "diy"],
            "Query Count": [12, 34, 9],
            "Clicks": [80, 210, 45],
            "Cost": [120.5, 310.2, 60.75],
            "Conversions": [0, 0, 0],
            "CPA": [0.0, 0.0, 0.0],
            "Wasted Spend": [120.5, 310.2, 60.75],
            "Waste Reason": ["Job Intent", "Free/Cheap Intent", "Free/DIY Intent"],
            "Priority Score": [38.8, 100.0, 19.6],
        }
    )
    terms = pd.DataFrame(
        {
            "Search term": ["crm jobs near me", "free crm download", "diy pest control"],
            "Campaign": ["SaaS | NonBrand", "SaaS | NonBrand", "Home | Pest"],
            "Ad group": ["AG - Jobs", "AG - Unsorted", "AG - Unsorted"],
            "Match type": ["Broad", "Broad", "Phrase"],
            "Clicks": [8, 21, 5],
            "Cost": [12.4, 30.1, 9.5],
            "Conversions": [0, 0, 0],
            "CPA": [0.0, 0.0, 0.0],
            "Wasted Spend": [12.4, 30.1, 9.5],
            "Waste Reason": ["Job Intent", "Free/Cheap Intent", "Free/DIY Intent"],
        }
    )
    negatives = pd.DataFrame(
        {
            "Keyword": ['"jobs"', '"free crm download"'],
            "Match Type": ["Phrase", "Phrase"],
            "Level": ["Account Negative List", "Account Negative List"],
            "Campaign": ["", ""],
            "Ad Group": ["", ""],
            "Source": ["1-Gram Explorer", "Search Term Auditor"],
            "Reason": ["Job Intent", "Free/Cheap Intent"],
            "Wasted Spend": [120.5, 30.1],
        }
    )
    return ngrams, terms, negatives


def test_excel_report_structure():
    ngrams, terms, negatives = _sample_frames()
    summary = {
        "total_spend": 38_742.11,
        "wasted_spend": 7_483.20,
        "waste_pct": 19.3,
        "annualized_savings": 88_112.94,
        "wasted_terms": 214,
        "wasted_ngrams": 389,
        "date_range": "Oct 1, 2025 - Oct 31, 2025",
        "days": 31,
        "currency": "$",
        "target_cpa": 84.2,
        "cpa_multiplier": 2.0,
        "zero_conv_threshold": 84.2,
        "min_clicks": 3,
        "brand_terms": "flowtrack",
        "presets": "Job Seekers, Free / Cheap / Piracy",
        "match_type": "Phrase",
        "level": "Account Negative List",
    }
    blob = build_excel_report(summary, ngrams, terms, negatives, currency="$")

    assert blob[:2] == b"PK"
    workbook = load_workbook(io.BytesIO(blob))
    assert workbook.sheetnames == [
        "Executive Summary", "Top Wasted N-Grams", "Flagged Search Terms",
        "Approved Negative List",
    ]

    exec_ws = workbook["Executive Summary"]
    labels = [cell.value for row in exec_ws.iter_rows() for cell in row]
    assert "Total Spend Analyzed" in labels
    assert "Projected Annualized Savings" in labels

    ngram_ws = workbook["Top Wasted N-Grams"]
    header = [cell.value for cell in ngram_ws[1]]
    assert "N-Gram" in header and "Wasted Spend" in header
    assert ngram_ws.max_row == 1 + len(ngrams)

    neg_ws = workbook["Approved Negative List"]
    assert neg_ws.max_row == 1 + len(negatives)


def test_excel_report_empty_sections_do_not_crash():
    empty = pd.DataFrame()
    ngrams, terms, _ = _sample_frames()
    blob = build_excel_report(
        {"total_spend": 100.0}, ngrams.head(0), terms.head(0), empty
    )
    assert blob[:2] == b"PK"


def test_safe_filename():
    assert safe_filename("Account Negative List") == "Account_Negative_List"
    assert safe_filename("campaign/name*!") == "campaign_name"
    assert safe_filename("") == "report"
