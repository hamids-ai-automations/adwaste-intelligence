"""Tests for Gemini AI audit wrapper, UI helpers, and AppTest integration."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import plotly.graph_objects as go
import pytest
from streamlit.testing.v1 import AppTest

from src import ui_components as ui
from src.waste_detector import GeminiAuditError, _parse_gemini_payload, run_gemini_audit

ROOT = Path(__file__).resolve().parent.parent


def test_ui_formatting_and_math_escape():
    assert ui.display_currency("USD") == "$"
    assert ui.display_currency("AED") == "AED "
    assert ui.fmt_money(1234.5, "$") == "$1,234.50"
    assert ui.fmt_money(81200, "$", compact=True) == "$81.2k"
    assert ui.fmt_pct(18.56) == "18.6%"
    assert ui.fmt_int(1500) == "1,500"
    assert ui._escape_math("$100 and $200") == "&#36;100 and &#36;200"


def test_plotly_chart_builders_return_figures():
    alloc = ui.spend_allocation_chart(20_000.0, 7_000.0, 3_000.0, "$")
    assert isinstance(alloc, go.Figure)
    assert len(alloc.data) == 1

    ngrams_df = pd.DataFrame(
        {
            "N-Gram": ["jobs", "free", "expensive"],
            "Wasted Spend": [500.0, 900.0, 1200.0],
            "Waste Reason": ["Job Intent", "Free/Cheap Intent", "High CPA"],
        }
    )
    bar = ui.top_wasted_ngrams_chart(ngrams_df, "$")
    assert isinstance(bar, go.Figure)

    camp_df = pd.DataFrame(
        {
            "Campaign": ["Search - Brand", "Search - NonBrand"],
            "Total Spend": [5000.0, 12000.0],
            "Wasted Spend": [100.0, 4200.0],
        }
    )
    camp = ui.campaign_waste_chart(camp_df, "$")
    assert isinstance(camp, go.Figure)
    assert len(camp.data) == 2


def test_parse_gemini_payload_variants():
    assert _parse_gemini_payload('{"results": [{"term": "free crm", "intent": "Irrelevant"}]}') == [
        {"term": "free crm", "intent": "Irrelevant"}
    ]
    fenced = '```json\n{"results": [{"term": "crm jobs", "intent": "Job/Career"}]}\n```'
    assert _parse_gemini_payload(fenced)[0]["intent"] == "Job/Career"

    with pytest.raises(GeminiAuditError):
        _parse_gemini_payload("")
    with pytest.raises(GeminiAuditError):
        _parse_gemini_payload("not json")


def test_run_gemini_audit_mocked(monkeypatch):
    fake_response = SimpleNamespace(
        text='{"results": [{"term": "crm jobs", "intent": "Job/Career", "reason": "Employment query."}]}'
    )
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    fake_genai = SimpleNamespace(
        Client=lambda api_key: fake_client,
        types=SimpleNamespace(GenerateContentConfig=lambda **kw: kw),
    )
    fake_google = SimpleNamespace(genai=fake_genai)
    monkeypatch.setitem(sys.modules, "google", fake_google)
    monkeypatch.setitem(sys.modules, "google.genai", fake_genai)

    progress_calls: list[tuple[float, str]] = []
    df = run_gemini_audit(
        ["crm jobs", "unmatched term"],
        api_key="test-key",
        progress=lambda frac, msg: progress_calls.append((frac, msg)),
    )
    assert list(df.columns) == ["Search term", "AI Intent", "Justification"]
    assert df.loc[0, "AI Intent"] == "Job/Career"
    assert df.loc[1, "Justification"] == "Not classified"
    assert len(progress_calls) == 1

    with pytest.raises(GeminiAuditError):
        run_gemini_audit(["crm jobs"], api_key="")
    with pytest.raises(GeminiAuditError):
        run_gemini_audit([], api_key="test-key")


def test_apptest_demo_and_staging_flow():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not app.exception

    demo_btn = next(b for b in app.button if "demo" in b.label.lower())
    app = demo_btn.click().run()
    assert not app.exception
    assert len(app.tabs) == 4

    stage_btn = next(b for b in app.button if "add checked n-grams" in b.label.lower())
    app = stage_btn.click().run()
    assert not app.exception
