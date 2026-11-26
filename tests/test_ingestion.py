"""Tests for the bulletproof Google Ads ingestion pipeline."""

import io

import pandas as pd
import pytest

from src.ingestion import MissingColumnsError, load_report, sanitize_number

MESSY_CSV = "\n".join(
    [
        "Search terms report",
        "Oct 1, 2026 - Oct 31, 2026",
        "Search term,Match type,Campaign,Ad group,Impr.,Clicks,Avg. CPC,Cost,Conversions,Conv. rate,Conv. value,Added/Excluded",
        '"crm software for small business",Exact,SaaS - NonBrand,AG-2,"3,150",95,"$3.10","$294.50",7,"7.37%","$3,360.00",Added',
        '"cheap free crm download",Broad,SaaS - NonBrand,AG-1,"1,204",18,"$0.98","$17.64",0,"0.00%","$0.00",--',
        '"jobs in crm sales",Phrase,SaaS - NonBrand,AG-1,890,12,"$1.40","$16.80",0,"0.00%","$0.00",--',
        '"Total: Search terms",,,,,,,,"$328.94",0,,"$3,360.00",',
        "",
    ]
)


def test_messy_csv_headers_totals_and_currency():
    result = load_report(MESSY_CSV.encode("utf-8"), "search_terms.csv")

    # 2 metadata rows skipped, Total row stripped
    assert len(result.df) == 3
    # date range parsed -> 31 days
    assert result.days == 31
    assert "Oct 1, 2026" in result.date_range
    # currency symbol detected from Cost column
    assert result.currency == "$"
    # spend never double-counted
    assert result.df["Cost"].sum() == pytest.approx(294.50 + 17.64 + 16.80)
    # numbers sanitized (commas, $, placeholders)
    assert result.df.loc[0, "Impr."] == 3150
    assert result.df.loc[0, "Conv. value"] == pytest.approx(3360.0)
    assert result.df.loc[0, "Conversions"] == 7
    # placeholder '--' coerced
    assert result.df["Added/Excluded"].tolist().count("--") == 2


def test_currency_and_placeholder_sanitization():
    csv_text = "\n".join(
        [
            "Search term,Cost,Clicks,Conversions,Conv. value",
            'crm aed,"AED 1,234.56",10,0,"--"',
            'crm euro,"€89.50",5,"--","N/A"',
            'crm placeholder,"--","< 10%","< 10%","< 10%"',
            "",
        ]
    )
    result = load_report(csv_text.encode("utf-8"), "cur.csv")
    assert result.currency == "AED"
    assert result.df.loc[0, "Cost"] == pytest.approx(1234.56)
    assert result.df.loc[1, "Cost"] == pytest.approx(89.50)
    assert result.df.loc[2, "Cost"] == 0.0
    assert result.df.loc[1, "Conversions"] == 0.0
    assert result.df.loc[0, "Conv. value"] == 0.0


def test_sanitize_number_unit():
    assert sanitize_number("--") == 0.0
    assert sanitize_number("< 10%") == 0.0
    assert sanitize_number("N/A") == 0.0
    assert sanitize_number("$1,234.56") == pytest.approx(1234.56)
    assert sanitize_number("CA$ 99.5") == pytest.approx(99.5)
    assert sanitize_number("1 234") == pytest.approx(1234.0)
    assert sanitize_number("") == 0.0
    assert sanitize_number(None) == 0.0


def test_utf16_tab_delimited():
    rows = [
        "Search term\tCost\tClicks\tConversions",
        "free crm\t$12.50\t7\t0",
        "crm software\t$300.00\t40\t3",
    ]
    text = "\n".join(rows)
    result = load_report(text.encode("utf-16"), "report.csv")
    assert len(result.df) == 2
    assert result.df["Cost"].sum() == pytest.approx(312.50)
    assert result.df.loc[1, "Search term"] == "crm software"


def test_column_alias_mapping():
    csv_text = "\n".join(
        [
            "Search query,Spend,Clicks,Total conv.,Impressions,Conversion value,Campaign name,Ad group name,Search keyword match type",
            "crm software,250.00,30,2,1200,900.00,SaaS,AG1,Exact",
            "",
        ]
    )
    result = load_report(csv_text.encode("utf-8"), "aliases.csv")
    assert result.df.loc[0, "Cost"] == pytest.approx(250.0)
    assert result.df.loc[0, "Conversions"] == 2
    assert result.df.loc[0, "Impr."] == 1200
    assert result.df.loc[0, "Conv. value"] == pytest.approx(900.0)
    assert result.df.loc[0, "Campaign"] == "SaaS"
    assert result.df.loc[0, "Match type"] == "Exact"


def test_missing_optional_columns_default_cleanly():
    csv_text = "\n".join(
        [
            "Search term,Cost,Clicks,Conversions",
            "crm software,250.00,30,2",
            "",
        ]
    )
    result = load_report(csv_text.encode("utf-8"), "minimal.csv")
    assert result.df.loc[0, "Impr."] == 0
    assert result.df.loc[0, "Conv. value"] == 0.0
    assert result.df.loc[0, "Campaign"] == "All"
    assert any("defaulted" in w.lower() for w in result.warnings)


def test_missing_required_raises_and_manual_mapping_resolves():
    # 'Budget' does not match any Cost alias, so the auto-mapper must fail
    # and the manual mapping UI path (column_mapping) must resolve it.
    csv_text = "\n".join(
        [
            "Search term,Budget,Clicks,Conversions",
            "crm software,250.00,30,2",
            "",
        ]
    )
    data = csv_text.encode("utf-8")
    with pytest.raises(MissingColumnsError) as exc:
        load_report(data, "missing.csv")
    assert "Cost" in exc.value.missing
    assert "budget" in exc.value.available  # headers are normalized to lowercase

    resolved = load_report(data, "missing.csv", column_mapping={"Cost": "Budget"})
    assert resolved.df.loc[0, "Cost"] == pytest.approx(250.0)


def test_ragged_total_row_is_handled():
    csv_text = "\n".join(
        [
            "Search term,Cost,Clicks,Conversions",
            "crm software,100.00,10,1",
            '"Total: Search terms",,,',
            "",
        ]
    )
    result = load_report(csv_text.encode("utf-8"), "ragged.csv")
    assert len(result.df) == 1
    assert result.df["Cost"].sum() == pytest.approx(100.0)


def test_xlsx_roundtrip():
    source = pd.DataFrame(
        {
            "Search term": ["crm software", "free crm", "jobs crm"],
            "Cost": [294.5, 17.64, 16.8],
            "Clicks": [95, 18, 12],
            "Conversions": [7, 0, 0],
            "Conv. value": [3360.0, 0.0, 0.0],
        }
    )
    buffer = io.BytesIO()
    source.to_excel(buffer, index=False)
    result = load_report(buffer.getvalue(), "report.xlsx")
    assert len(result.df) == 3
    assert result.df["Cost"].sum() == pytest.approx(328.94)
    assert result.df.loc[0, "Conversions"] == 7


def test_demo_dataset_shape():
    from src.sample_data import DEMO_DATE_RANGE, generate_sample_data

    demo = generate_sample_data()
    assert len(demo) == 1500
    assert set(demo.columns) >= {
        "Search term", "Cost", "Clicks", "Impr.", "Conversions", "Conv. value",
        "Campaign", "Ad group", "Match type",
    }
    spend = demo["Cost"].sum()
    assert 25_000 <= spend <= 40_000
    assert demo["Conversions"].sum() > 100
    # deterministic
    assert generate_sample_data()["Cost"].sum() == pytest.approx(spend)
    # waste clusters exist
    terms = " ".join(demo["Search term"].str.lower())
    for token in ("jobs", "free", "salary", "diy", "login"):
        assert token in terms
    assert DEMO_DATE_RANGE
