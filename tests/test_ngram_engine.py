"""Tests for the n-gram engine, waste rules and the conflict guard."""

import pandas as pd
import pytest

from src.ngram_engine import build_ngram_table, extract_ngrams, normalize_term, terms_containing
from src.waste_detector import (
    WasteConfig,
    apply_waste_rules,
    find_conflicts,
    flag_search_terms,
    keyword_blocks_term,
)


def make_df(rows):
    """rows: list of (term, impr, clicks, cost, conv, value)."""
    return pd.DataFrame(
        rows,
        columns=["Search term", "Impr.", "Clicks", "Cost", "Conversions", "Conv. value"],
    )


# ---------------------------------------------------------------------------
# Normalization & n-gram extraction
# ---------------------------------------------------------------------------
def test_normalize_term():
    assert normalize_term("How-To (Fix) Leaky Faucet!!") == "how-to fix leaky faucet"
    assert normalize_term("  CRM   Software  ") == "crm software"
    assert normalize_term("What's a CRM?") == "what's a crm"
    assert normalize_term("") == ""


def test_extract_ngrams_deduplicates_within_term():
    assert extract_ngrams("cheap cheap cheap hosting", 1) == ["cheap", "hosting"]
    # 2-grams of "a b a b" -> {a b, b a} (unique)
    assert set(extract_ngrams("a b a b", 2)) == {"a b", "b a"}
    assert extract_ngrams("crm", 2) == []
    assert extract_ngrams("best crm software", 3) == ["best crm software"]


def test_stopwords_excluded_from_1grams_preserved_in_phrases():
    df = make_df([("how to fix faucet", 100, 10, 10.0, 0, 0.0)])
    one_gram = build_ngram_table(df, 1, exclude_stopwords=True)
    tokens = set(one_gram["N-Gram"])
    assert "how" not in tokens and "to" not in tokens
    assert {"fix", "faucet"} <= tokens

    two_gram = build_ngram_table(df, 2, exclude_stopwords=True)
    assert "how to" in set(two_gram["N-Gram"])


# ---------------------------------------------------------------------------
# Aggregation math
# ---------------------------------------------------------------------------
def test_build_ngram_table_sums():
    df = make_df(
        [
            ("free crm download", 100, 10, 10.0, 0, 0.0),
            ("crm software", 200, 20, 40.0, 2, 800.0),
            ("best crm software", 150, 15, 30.0, 1, 400.0),
        ]
    )
    table = build_ngram_table(df, 1, exclude_stopwords=False)

    crm = table[table["N-Gram"] == "crm"].iloc[0]
    assert crm["Query Count"] == 3
    assert crm["Clicks"] == 45
    assert crm["Cost"] == pytest.approx(80.0)
    assert crm["Conversions"] == 3
    assert crm["Conv. Value"] == pytest.approx(1200.0)
    assert crm["CPA"] == pytest.approx(80.0 / 3)
    assert crm["Conv. Rate (%)"] == pytest.approx(3 / 45 * 100)
    assert crm["CTR (%)"] == pytest.approx(45 / 450 * 100)

    software = table[table["N-Gram"] == "software"].iloc[0]
    assert software["Query Count"] == 2
    assert software["Cost"] == pytest.approx(70.0)

    free = table[table["N-Gram"] == "free"].iloc[0]
    assert free["Query Count"] == 1
    assert free["ROAS"] == 0.0


def test_no_double_counting_within_single_term():
    df = make_df([("cheap cheap cheap hosting", 50, 5, 25.0, 0, 0.0)])
    table = build_ngram_table(df, 1, exclude_stopwords=False)
    cheap = table[table["N-Gram"] == "cheap"].iloc[0]
    assert cheap["Query Count"] == 1
    assert cheap["Cost"] == pytest.approx(25.0)


def test_terms_containing_drilldown():
    df = pd.DataFrame(
        {
            "Search term": ["free crm download", "crm software", "free trial"],
            "Campaign": ["C1", "C2", "C1"],
            "Clicks": [10, 20, 5],
            "Cost": [10.0, 40.0, 6.0],
            "Conversions": [0, 2, 0],
            "Impr.": [100, 200, 50],
            "Conv. value": [0.0, 800.0, 0.0],
        }
    )
    one = terms_containing(df, "free", 1)
    assert len(one) == 2
    two = terms_containing(df, "free crm", 2)
    assert len(two) == 1
    assert two.iloc[0]["Search term"] == "free crm download"


# ---------------------------------------------------------------------------
# Waste rules
# ---------------------------------------------------------------------------
def base_config(**overrides):
    defaults = dict(
        target_cpa=20.0,
        cpa_multiplier=2.0,
        zero_conv_threshold=25.0,
        min_clicks=3,
        brand_terms=("flowtrack",),
        presets={"Job Seekers": ("job", "jobs")},
    )
    defaults.update(overrides)
    return WasteConfig(**defaults)


def test_waste_rule_preset_job_intent():
    df = make_df([("crm software jobs", 100, 10, 30.0, 0, 0.0)])
    flagged = flag_search_terms(df, base_config())
    assert bool(flagged.iloc[0]["Waste Flag"]) is True
    assert "Job Intent" in flagged.iloc[0]["Waste Reason"]
    assert flagged.iloc[0]["Wasted Spend"] == pytest.approx(30.0)


def test_waste_rule_zero_conv_bleeder():
    df = make_df([("bleeder widget", 100, 5, 30.0, 0, 0.0)])
    flagged = flag_search_terms(df, base_config(presets={}))
    assert bool(flagged.iloc[0]["Waste Flag"]) is True
    assert "Zero-Conv Bleeder" in flagged.iloc[0]["Waste Reason"]


def test_waste_rule_high_cpa_excess():
    # CPA = 100/2 = 50 >= 20 * 2 -> flagged; waste = 100 - 20*2 = 60
    df = make_df([("expensive software", 100, 20, 100.0, 2, 500.0)])
    flagged = flag_search_terms(df, base_config(presets={}))
    assert bool(flagged.iloc[0]["Waste Flag"]) is True
    assert "High CPA" in flagged.iloc[0]["Waste Reason"]
    assert flagged.iloc[0]["Wasted Spend"] == pytest.approx(60.0)


def test_brand_whitelist_protects():
    df = make_df([("flowtrack jobs", 100, 10, 30.0, 0, 0.0)])
    flagged = flag_search_terms(df, base_config())
    assert bool(flagged.iloc[0]["Waste Flag"]) is False
    assert "Protected" in flagged.iloc[0]["Waste Reason"]


def test_min_clicks_and_threshold_gating():
    # cost above threshold but only 2 clicks (< min 3) and no preset word
    df = make_df([("tiny widget", 100, 2, 30.0, 0, 0.0)])
    flagged = flag_search_terms(df, base_config(presets={}))
    assert bool(flagged.iloc[0]["Waste Flag"]) is False
    # 3 clicks but cost below threshold
    df2 = make_df([("small widget", 100, 3, 10.0, 0, 0.0)])
    flagged2 = flag_search_terms(df2, base_config(presets={}))
    assert bool(flagged2.iloc[0]["Waste Flag"]) is False


def test_priority_score_ranks_wasted_impact():
    df = make_df(
        [
            ("crm jobs", 100, 10, 100.0, 0, 0.0),   # preset + zero conv -> 100 waste
            ("other jobs", 100, 10, 50.0, 0, 0.0),   # preset -> 50 waste
        ]
    )
    flagged = flag_search_terms(df, base_config())
    scores = flagged[flagged["Waste Flag"]]["Priority Score"].tolist()
    assert scores[0] == pytest.approx(100.0)
    assert scores[1] == pytest.approx(50.0)


def test_ngram_table_waste_flagging():
    df = make_df(
        [
            ("free crm download", 100, 10, 10.0, 0, 0.0),
            ("free crm", 100, 10, 20.0, 0, 0.0),
        ]
    )
    table = build_ngram_table(df, 1, exclude_stopwords=False)
    flagged = apply_waste_rules(
        table, base_config(presets={"Free / Cheap / Piracy": ("free",)}),
        term_column="N-Gram",
    )
    free = flagged[flagged["N-Gram"] == "free"].iloc[0]
    assert bool(free["Waste Flag"]) is True
    assert free["Wasted Spend"] == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# Conflict guard
# ---------------------------------------------------------------------------
def test_match_type_semantics():
    assert keyword_blocks_term("free crm", "Exact", "free crm download") is False
    assert keyword_blocks_term("free crm", "Exact", "free crm") is True
    assert keyword_blocks_term("free crm", "Phrase", "free crm download") is True
    assert keyword_blocks_term("free crm", "Phrase", "download free crm") is True
    assert keyword_blocks_term("free crm", "Phrase", "free crmsoftware") is True
    assert keyword_blocks_term("crm free", "Broad", "free crm download") is True
    assert keyword_blocks_term("crm free", "Broad", "free download") is False
    assert keyword_blocks_term("Free CRM", "Phrase", "best FREE crm tools") is True


CONVERTING_DF = pd.DataFrame(
    {
        "Search term": ["flowtrack login", "crm software", "flowtrack pricing"],
        "Campaign": ["Brand", "NonBrand", "Brand"],
        "Conversions": [5, 2, 3],
        "Conv. value": [2000.0, 800.0, 1200.0],
        "Clicks": [40, 20, 30],
        "Cost": [50.0, 100.0, 60.0],
        "Impr.": [400, 200, 300],
    }
)


def test_find_conflicts_and_removal():
    conflicts = find_conflicts(["flowtrack login", "software"], "Exact", CONVERTING_DF)
    assert len(conflicts) == 1
    assert conflicts.iloc[0]["Converting Query"] == "flowtrack login"

    phrase_conflicts = find_conflicts(["flowtrack"], "Phrase", CONVERTING_DF)
    # "flowtrack" phrase blocks both converting brand queries
    assert len(phrase_conflicts) == 2
    assert phrase_conflicts["Conv. Value"].sum() == pytest.approx(3200.0)

    # removal flow: stage two negatives, run the guard on the full staged
    # list, then drop every keyword that appears in the conflict table
    staged = [
        {"keyword": "flowtrack login", "source": "test", "reason": "", "wasted": 0},
        {"keyword": "free crm", "source": "test", "reason": "", "wasted": 0},
    ]
    staged_conflicts = find_conflicts(
        [item["keyword"] for item in staged], "Phrase", CONVERTING_DF
    )
    assert set(staged_conflicts["Negative Keyword"]) == {"flowtrack login"}
    bad = set(staged_conflicts["Negative Keyword"])
    kept = [item for item in staged if item["keyword"] not in bad]
    assert [item["keyword"] for item in kept] == ["free crm"]


def test_find_conflicts_empty_cases():
    assert find_conflicts([], "Exact", CONVERTING_DF).empty
    no_conv = CONVERTING_DF.copy()
    no_conv["Conversions"] = 0
    assert find_conflicts(["crm"], "Broad", no_conv).empty


# ---------------------------------------------------------------------------
# Performance guard (50k-row stress test)
# ---------------------------------------------------------------------------
def test_50k_row_performance():
    import time

    import numpy as np

    rng = np.random.default_rng(7)
    n = 50_000
    words = ["free", "crm", "software", "jobs", "near", "me", "best", "cheap",
             "plumber", "pest", "control", "login", "diy", "tutorial", "pdf"]
    terms = [
        " ".join(rng.choice(words, size=int(rng.integers(2, 6)))) for _ in range(n)
    ]
    df = pd.DataFrame(
        {
            "Search term": terms,
            "Impr.": rng.integers(10, 500, n),
            "Clicks": rng.integers(0, 30, n),
            "Cost": rng.uniform(0.5, 60.0, n).round(2),
            "Conversions": rng.integers(0, 4, n),
            "Conv. value": rng.uniform(0, 500, n).round(2),
        }
    )
    config = base_config()
    start = time.perf_counter()
    for n_level in (1, 2, 3, 4):
        table = build_ngram_table(df, n_level, exclude_stopwords=True)
        assert len(table) > 0
        apply_waste_rules(table, config, term_column="N-Gram")
    elapsed = time.perf_counter() - start
    assert elapsed < 15.0, f"50k-row analysis took {elapsed:.2f}s (budget 15s)"
