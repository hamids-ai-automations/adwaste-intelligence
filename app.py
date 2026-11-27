"""AdWaste Intelligence — main Streamlit entry point.

Full web SaaS companion to the Google Ads Waste Detector Chrome extension:
upload a Search Terms report (or load the demo account), run 1-4 gram waste
analysis, guard converting queries against negative-keyword conflicts, and
export ready-to-paste negative lists plus client-ready Excel audit reports.

Privacy-first: all processing runs 100% in-memory per session.
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitAPIException

from src import ui_components as ui
from src.constants import (
    APP_NAME,
    APP_TAGLINE,
    DEFAULT_CPA_MULTIPLIER,
    DEFAULT_DAYS,
    DEFAULT_EDITOR_ROW_CAP,
    DEFAULT_MIN_CLICKS,
    DEFAULT_ZERO_CONV_FALLBACK,
    GEMINI_MODELS,
    PRESET_WASTE_DICTIONARIES,
)
from src.exporter import (
    LEVELS,
    MATCH_TYPES,
    build_copy_paste_block,
    build_editor_csv,
    build_excel_report,
    safe_filename,
)
from src.ingestion import IngestionResult, MissingColumnsError, load_report
from src.ngram_engine import (
    NGRAM_LEVELS,
    build_ngram_table,
    extract_ngrams,
    terms_containing,
)
from src.sample_data import (
    DEMO_BRAND_TERMS,
    DEMO_CURRENCY,
    DEMO_DATE_RANGE,
    DEMO_DAYS,
    generate_sample_data,
)
from src.waste_detector import (
    GeminiAuditError,
    WasteConfig,
    apply_waste_rules,
    find_conflicts,
    flag_search_terms,
    run_gemini_audit,
)

st.set_page_config(
    page_title=f"{APP_NAME} | Google Ads Waste Detector",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="expanded",
)

ui.inject_css()


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------
def reset_session() -> None:
    for key in (
        "terms_df", "currency", "date_range", "days", "staged_negatives",
        "upload_bytes", "upload_name", "pending_mapping_error", "ai_audit",
        "upload_warnings", "target_cpa", "zero_threshold", "brand_terms",
    ):
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if key.startswith(("ngram_editor", "term_editor", "staging_editor", "map_")):
            st.session_state.pop(key, None)
    st.cache_data.clear()


def stage_negatives(entries: list[dict]) -> int:
    """Add entries to the unified staging list (deduped by keyword).

    Returns the number of newly added keywords.
    """
    staged = st.session_state.setdefault("staged_negatives", [])
    existing = {item["keyword"].lower() for item in staged}
    added = 0
    for entry in entries:
        keyword = str(entry.get("keyword", "")).strip()
        if keyword and keyword.lower() not in existing:
            staged.append(entry)
            existing.add(keyword.lower())
            added += 1
    if added:
        st.session_state.pop("staging_editor", None)
    return added


def _parse_csv_terms(text: str) -> tuple:
    return tuple(t.strip().lower() for t in str(text).split(",") if t.strip())


def _number_widget(label: str, key: str, default: float, **kwargs) -> float:
    """Number input that never conflicts with pre-seeded session state."""
    if key in st.session_state:
        return float(st.number_input(label, key=key, **kwargs))
    return float(st.number_input(label, value=default, key=key, **kwargs))


def _text_widget(label: str, key: str, default: str, **kwargs) -> str:
    if key in st.session_state:
        return str(st.text_input(label, key=key, **kwargs))
    return str(st.text_input(label, value=default, key=key, **kwargs))


# ---------------------------------------------------------------------------
# Cached analysis
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _ngram_table_cached(df: pd.DataFrame, n: int, exclude_stopwords: bool) -> pd.DataFrame:
    return build_ngram_table(df, n, exclude_stopwords)


@st.cache_data(show_spinner="Analyzing 1-4 gram waste...")
def compute_analysis(
    df: pd.DataFrame,
    exclude_stopwords: bool,
    target_cpa: float,
    cpa_multiplier: float,
    zero_conv_threshold: float,
    min_clicks: int,
    brand_terms: tuple,
    preset_names: tuple,
) -> dict:
    config = WasteConfig(
        target_cpa=target_cpa,
        cpa_multiplier=cpa_multiplier,
        zero_conv_threshold=zero_conv_threshold,
        min_clicks=min_clicks,
        brand_terms=tuple(brand_terms),
        presets={name: tuple(PRESET_WASTE_DICTIONARIES[name]) for name in preset_names},
    )
    flagged_terms = flag_search_terms(df, config)
    ngram_tables = {
        n: apply_waste_rules(_ngram_table_cached(df, n, exclude_stopwords), config)
        for n in NGRAM_LEVELS
    }
    return {"flagged_terms": flagged_terms, "ngram_tables": ngram_tables}


# ---------------------------------------------------------------------------
# Data loading (landing state)
# ---------------------------------------------------------------------------
def _set_data(result: IngestionResult | None = None, df: pd.DataFrame = None,
              currency: str = "$", date_range: str = "",
              days: int = DEFAULT_DAYS) -> None:
    final_df = result.df if result is not None else df
    st.session_state["terms_df"] = final_df
    st.session_state["currency"] = result.currency if result is not None else currency
    st.session_state["date_range"] = result.date_range if result is not None else date_range
    st.session_state["days"] = result.days if result is not None else days
    st.session_state["upload_warnings"] = result.warnings if result is not None else []
    st.session_state["staged_negatives"] = []
    st.cache_data.clear()

    total_cost = float(final_df["Cost"].sum())
    total_conv = float(final_df["Conversions"].sum())
    account_cpa = total_cost / total_conv if total_conv > 0 else DEFAULT_ZERO_CONV_FALLBACK
    st.session_state["target_cpa"] = round(account_cpa, 2)
    st.session_state["zero_threshold"] = round(
        account_cpa if total_conv > 0 else DEFAULT_ZERO_CONV_FALLBACK, 2
    )
    st.session_state.pop("brand_terms", None)
    if result is None:  # demo mode: pre-fill the brand whitelist
        st.session_state["brand_terms"] = DEMO_BRAND_TERMS


def _process_upload(data: bytes, name: str, mapping: dict | None = None) -> None:
    try:
        result = load_report(data, name, mapping)
    except MissingColumnsError as exc:
        st.session_state["pending_mapping_error"] = exc
        st.session_state["upload_bytes"] = data
        st.session_state["upload_name"] = name
        st.rerun()
        return
    except Exception as exc:  # noqa: BLE001 - surfaced to the user
        st.error(f"Could not parse this file: {exc}")
        return
    _set_data(result=result)
    st.session_state.pop("pending_mapping_error", None)
    st.session_state.pop("upload_bytes", None)
    st.session_state.pop("upload_name", None)
    st.toast(
        f"Loaded {len(result.df):,} search terms — "
        f"{ui.fmt_money(float(result.df['Cost'].sum()), result.currency)} analyzed."
    )
    st.rerun()


def render_mapping_ui() -> None:
    error = st.session_state["pending_mapping_error"]
    st.warning(
        "This report is missing required column(s): **"
        + ", ".join(error.missing)
        + "**. Map them to the correct report columns below."
    )
    available = [c for c in error.available if c and str(c).strip()]
    mapping: dict[str, str | None] = {}
    for canonical in error.missing:
        mapping[canonical] = st.selectbox(
            f"Column to use for '{canonical}'",
            options=available,
            index=None,
            placeholder="Choose a column…",
            key=f"map_{canonical}",
        )
    ready = all(v is not None for v in mapping.values())
    cols = st.columns([1, 1])
    if cols[0].button("Run Analysis", type="primary", disabled=not ready,
                      width="stretch"):
        _process_upload(
            st.session_state["upload_bytes"],
            st.session_state.get("upload_name", "report.csv"),
            {k: v for k, v in mapping.items() if v},
        )
    if cols[1].button("Discard this file", width="stretch"):
        st.session_state.pop("pending_mapping_error", None)
        st.session_state.pop("upload_bytes", None)
        st.session_state.pop("upload_name", None)
        st.rerun()


def render_landing() -> None:
    st.markdown(
        f"""
        <div class="hero-wrap">
          <div class="hero-title">Stop paying for clicks that never convert.</div>
          <div class="hero-sub">{APP_NAME} runs a full 1-4 gram waste audit on any
          Google Ads Search Terms report — flags bleeder n-grams, protects your
          converting queries, and exports ready-to-paste negative keyword lists
          plus a client-ready Excel audit report.</div>
          <div class="hero-points">
            <b>Upload</b> a CSV/XLSX Search Terms export &nbsp;·&nbsp;
            <b>Detect</b> wasted spend with configurable rules &nbsp;·&nbsp;
            <b>Guard</b> converting queries with the conflict checker &nbsp;·&nbsp;
            <b>Export</b> negatives in 60 seconds.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    ui.render_privacy_strip()

    left, right = st.columns([1.6, 1], gap="large")
    with left:
        uploaded = st.file_uploader(
            "Upload your Google Ads Search Terms report (.csv or .xlsx)",
            type=["csv", "xlsx", "xls"],
            help="Standard Google Ads exports are supported — metadata rows, "
            "'Total:' rows, UTF-16 and $ / AED / PKR / € currencies are cleaned "
            "automatically. Max 100 MB.",
        )
    with right:
        st.markdown(
            """
            <div class="ext-card">
              <div class="ext-title">No report handy?</div>
              <div class="ext-text">Load the demo account — 1,500 realistic search
              terms, ~$30k spend, deliberate waste clusters — and explore every
              feature instantly.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if st.button(
        "Load Demo Account (1,500 Search Terms)",
        type="primary",
        width="stretch",
    ):
        _set_data(df=generate_sample_data(), currency=DEMO_CURRENCY,
                  date_range=DEMO_DATE_RANGE, days=DEMO_DAYS)
        st.rerun()
        return

    if st.session_state.get("pending_mapping_error"):
        render_mapping_ui()
    elif uploaded is not None:
        _process_upload(uploaded.getvalue(), uploaded.name)

    st.markdown('<div class="section-title">How it works</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    steps = [
        ("1. Ingest", "Bulletproof parser handles messy Google Ads exports: 2-row metadata headers, Total: rows, UTF-16, currency symbols."),
        ("2. Analyze", "Vectorized 1-4 gram engine rolls up cost, clicks, CPA and conversions per n-gram with zero double-counting."),
        ("3. Guard", "Conflict checker cross-checks every staged negative against converting queries before you paste anything."),
        ("4. Export", "Copy-paste block, Google Ads Editor CSV, and a branded multi-tab Excel client audit report."),
    ]
    for col, (title, text) in zip(cols, steps, strict=True):
        col.markdown(
            f"""
            <div class="kpi-card">
              <div class="kpi-label">{title}</div>
              <div class="kpi-sub" style="font-size:12.5px;line-height:1.5;margin-top:6px;">{text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
def build_sidebar(df: pd.DataFrame) -> tuple[WasteConfig, bool]:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="adw-title" style="font-size:20px;">{APP_NAME}</div>
            <div class="adw-sub" style="font-size:12px;">{APP_TAGLINE}</div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("Start over / load a new file", width="stretch"):
            reset_session()
            st.rerun()
        st.divider()

        st.markdown('<div class="section-title" style="margin:0 0 8px 0;">Waste rules</div>',
                    unsafe_allow_html=True)
        target_cpa = _number_widget(
            "Target CPA", "target_cpa", 100.0,
            min_value=1.0, step=5.0, format="%.2f",
            help="Auto-initialized to your account average CPA (editable). "
            "High-CPA flags and waste calculations use this value.",
        )
        cpa_multiplier = st.number_input(
            "CPA bleeder multiplier (x Target CPA)",
            min_value=1.0, max_value=10.0, value=DEFAULT_CPA_MULTIPLIER, step=0.1,
            help="Terms / n-grams converting above this CPA multiple are flagged "
            "as High CPA waste.",
        )
        zero_threshold = _number_widget(
            "Zero-conversion spend threshold", "zero_threshold",
            DEFAULT_ZERO_CONV_FALLBACK,
            min_value=0.0, step=5.0, format="%.2f",
            help="Zero-conv terms costing at least this much (with enough clicks) "
            "are flagged as bleeders. Defaults to 1x account CPA ($50 if the "
            "account has no conversions).",
        )
        min_clicks = st.number_input(
            "Minimum clicks threshold",
            min_value=0, max_value=100, value=DEFAULT_MIN_CLICKS, step=1,
            help="Avoids prematurely flagging 1-click noise.",
        )
        brand_terms = _text_widget(
            "Brand & protected terms", "brand_terms", "",
            help="Comma-separated tokens. Any search term or n-gram containing "
            "them is protected from automatic waste flagging.",
        )
        stopwords_on = st.toggle(
            "Exclude stopwords from 1-grams",
            value=True,
            key="stopwords_on",
            help="Stopwords are excluded from 1-grams but preserved inside "
            "2-4 gram phrases like 'how to' or 'near me'.",
        )
        presets_selected = st.multiselect(
            "Preset waste dictionaries",
            options=list(PRESET_WASTE_DICTIONARIES),
            default=list(PRESET_WASTE_DICTIONARIES),
            help="Ready-made negative-intent dictionaries. Matches are flagged "
            "when they have zero conversions.",
        )
        st.divider()
        ui.render_sidebar_cta()

    config = WasteConfig(
        target_cpa=float(target_cpa),
        cpa_multiplier=float(cpa_multiplier),
        zero_conv_threshold=float(zero_threshold),
        min_clicks=int(min_clicks),
        brand_terms=_parse_csv_terms(brand_terms),
        presets={name: tuple(PRESET_WASTE_DICTIONARIES[name]) for name in presets_selected},
    )
    return config, bool(stopwords_on)


# ---------------------------------------------------------------------------
# Tab 1 — Executive Waste Overview
# ---------------------------------------------------------------------------
def render_overview(analysis: dict, df: pd.DataFrame, currency: str,
                    days: int, date_range: str) -> None:
    flagged_terms = analysis["flagged_terms"]
    total_spend = float(df["Cost"].sum())
    wasted_spend = float(flagged_terms["Wasted Spend"].sum())
    waste_pct = (wasted_spend / total_spend * 100) if total_spend > 0 else 0.0
    annualized = wasted_spend / max(days, 1) * 365
    wasted_term_count = int(flagged_terms["Waste Flag"].sum())
    wasted_ngram_count = sum(
        int(table["Waste Flag"].sum()) for table in analysis["ngram_tables"].values()
    )

    st.caption(
        f"Window analyzed: {date_range or 'not detected — assuming 30 days'} "
        f"({days} days) · currency {ui.display_currency(currency)} · "
        "waste rules as configured in the sidebar."
    )
    ui.render_kpi_cards(
        [
            {"label": "Total Spend Analyzed",
             "value": ui.fmt_money(total_spend, currency),
             "sub": f"{ui.fmt_int(len(df))} search terms", "tone": ""},
            {"label": "Flagged Wasted Spend",
             "value": ui.fmt_money(wasted_spend, currency),
             "sub": f"{ui.fmt_pct(waste_pct)} of total spend", "tone": "bad"},
            {"label": "Projected Annualized Savings",
             "value": ui.fmt_money(annualized, currency, compact=True),
             "sub": f"waste / {days}d x 365", "tone": "good"},
            {"label": "Wasted Search Terms",
             "value": ui.fmt_int(wasted_term_count),
             "sub": f"of {ui.fmt_int(len(df))} terms", "tone": "warn"},
            {"label": "Wasted N-Grams (1-4)",
             "value": ui.fmt_int(wasted_ngram_count),
             "sub": "unique flagged n-grams", "tone": "warn"},
        ]
    )

    converting_mask = pd.to_numeric(df["Conversions"], errors="coerce").fillna(0) > 0
    converting_spend = float(df.loc[converting_mask, "Cost"].sum())
    flagged_zero_mask = flagged_terms["Waste Flag"].to_numpy() & (
        pd.to_numeric(flagged_terms["Conversions"], errors="coerce").fillna(0).to_numpy() <= 0
    )
    flagged_spend = float(flagged_terms.loc[flagged_zero_mask, "Cost"].sum())
    unproven = max(total_spend - converting_spend - flagged_spend, 0.0)

    chart1, chart2 = st.columns([1, 1.35], gap="medium")
    with chart1:
        st.markdown('<div class="section-title">Spend allocation</div>', unsafe_allow_html=True)
        st.plotly_chart(
            ui.spend_allocation_chart(converting_spend, flagged_spend, unproven, currency),
            width="stretch",
        )
    with chart2:
        st.markdown('<div class="section-title">Top 15 wasted n-grams</div>', unsafe_allow_html=True)
        combined = pd.concat(
            [table[table["Waste Flag"]] for table in analysis["ngram_tables"].values()],
            ignore_index=True,
        )
        if combined.empty:
            st.info("No n-grams are currently flagged with these settings. "
                    "Loosen the thresholds in the sidebar.")
        else:
            top15 = combined.sort_values("Wasted Spend", ascending=False).head(15)
            st.plotly_chart(ui.top_wasted_ngrams_chart(top15, currency),
                            width="stretch")

    st.markdown('<div class="section-title">Campaign-level waste breakdown</div>',
                unsafe_allow_html=True)
    campaign_total = df.groupby("Campaign")["Cost"].sum().reset_index(name="Total Spend")
    campaign_waste = (
        flagged_terms[flagged_terms["Waste Flag"]]
        .groupby("Campaign")["Wasted Spend"].sum().reset_index(name="Wasted Spend")
    )
    campaign_view = campaign_total.merge(campaign_waste, on="Campaign", how="left").fillna(0.0)
    st.plotly_chart(ui.campaign_waste_chart(campaign_view, currency),
                    width="stretch")


# ---------------------------------------------------------------------------
# Tab 2 — N-Gram Intelligence Explorer
# ---------------------------------------------------------------------------
def _grams_for_subset(df: pd.DataFrame, mask, n: int) -> set:
    grams = set()
    for term in df.loc[mask, "Search term"].astype(str).head(5000):
        grams.update(extract_ngrams(term, n))
    return grams


def render_ngram_explorer(analysis: dict, df: pd.DataFrame, currency: str) -> None:
    n = st.radio(
        "N-gram level",
        options=list(NGRAM_LEVELS),
        horizontal=True,
        format_func=lambda level: f"{level}-Gram",
        key="ngram_n",
    )
    table = analysis["ngram_tables"][n]

    filters = st.columns([2, 1.6, 1.4, 1.4, 1.6])
    with filters[0]:
        search = st.text_input("Search n-grams", placeholder="e.g. free, jobs, login…",
                               key="ngram_search")
    with filters[1]:
        campaigns = ["All"] + sorted(df["Campaign"].astype(str).unique().tolist())
        campaign_filter = st.selectbox("Campaign", campaigns, key="ngram_campaign")
    with filters[2]:
        match_types = ["All"] + sorted(df["Match type"].astype(str).unique().tolist())
        match_filter = st.selectbox("Match type", match_types, key="ngram_match")
    with filters[3]:
        min_spend = st.number_input("Min spend", min_value=0.0, value=0.0,
                                    step=10.0, key="ngram_min_spend")
    with filters[4]:
        flagged_only = st.toggle("Flagged waste only", value=True, key="ngram_flagged_only")

    view = table.copy()
    if flagged_only:
        view = view[view["Waste Flag"]]
    if campaign_filter != "All":
        allowed = _grams_for_subset(df, df["Campaign"] == campaign_filter, n)
        view = view[view["N-Gram"].isin(allowed)]
    if match_filter != "All":
        allowed = _grams_for_subset(df, df["Match type"] == match_filter, n)
        view = view[view["N-Gram"].isin(allowed)]
    if min_spend > 0:
        view = view[view["Cost"] >= min_spend]
    if search.strip():
        view = view[view["N-Gram"].str.contains(search.strip(), case=False, na=False)]

    view = view.sort_values("Wasted Spend", ascending=False, ignore_index=True)
    if view.empty:
        st.info("No n-grams match the current filters.")
        return

    capped = view.head(DEFAULT_EDITOR_ROW_CAP).copy()
    if len(view) > len(capped):
        st.caption(f"Showing top {len(capped):,} of {len(view):,} matching n-grams "
                   "(sorted by wasted spend).")

    display = capped[
        ["N-Gram", "Query Count", "Clicks", "Cost", "Conversions", "CPA",
         "Wasted Spend", "Waste Reason", "Priority Score"]
    ].round(2)
    display.insert(0, "Add to Negatives",
                   (capped["Waste Flag"] & (capped["Priority Score"] >= 60)).tolist())

    edited = st.data_editor(
        display,
        key=f"ngram_editor_{n}",
        hide_index=True,
        width="stretch",
        height=430,
        disabled=[col for col in display.columns if col != "Add to Negatives"],
        column_config={
            "Add to Negatives": st.column_config.CheckboxColumn(
                "Add to Negatives",
                help="Check rows to stage them as negative keywords in Tab 4.",
                default=False,
            ),
            "N-Gram": st.column_config.TextColumn("N-Gram", width="medium"),
            "Waste Reason": st.column_config.TextColumn("Waste Reason", width="medium"),
            "Cost": st.column_config.NumberColumn("Cost", format="%.2f"),
            "CPA": st.column_config.NumberColumn("CPA", format="%.2f"),
            "Wasted Spend": st.column_config.NumberColumn("Wasted Spend", format="%.2f"),
        },
    )

    checked = int(edited["Add to Negatives"].sum())
    if st.button(f"Add checked n-grams to Negative Staging ({checked})", type="primary"):
        selected = edited[edited["Add to Negatives"]]
        added = stage_negatives(
            [
                {
                    "keyword": row["N-Gram"],
                    "source": f"{n}-Gram Explorer",
                    "reason": row.get("Waste Reason", ""),
                    "wasted": float(row.get("Wasted Spend", 0.0) or 0),
                }
                for _, row in selected.iterrows()
            ]
        )
        st.success(f"Added {added} new negative keyword(s) to the staging list in Tab 4.")

    st.markdown('<div class="section-title">N-gram drill-down</div>', unsafe_allow_html=True)
    options = capped["N-Gram"].head(300).tolist()
    if options:
        selected_ngram = st.selectbox(
            "Inspect every raw search term behind an n-gram", options,
            key="ngram_drill",
        )
        detail = terms_containing(df, selected_ngram, n)
        detail_view = detail[
            ["Search term", "Campaign", "Ad group", "Match type", "Impr.",
             "Clicks", "Cost", "Conversions", "Conv. value", "Added/Excluded"]
        ].round(2)
        st.dataframe(detail_view, hide_index=True, width="stretch", height=260)
        st.caption(
            f"{len(detail):,} raw search terms contain '{selected_ngram}' — "
            f"{ui.fmt_money(float(detail['Cost'].sum()), currency)} spend, "
            f"{int(detail['Conversions'].sum())} conversions."
        )


# ---------------------------------------------------------------------------
# Tab 3 — Search Term Auditor + optional AI intent audit
# ---------------------------------------------------------------------------
def render_term_auditor(analysis: dict, df: pd.DataFrame, currency: str) -> None:
    flagged = analysis["flagged_terms"]
    ui.render_reason_legend()

    flagged_view = flagged[flagged["Waste Flag"]].sort_values(
        "Wasted Spend", ascending=False, ignore_index=True
    )
    if flagged_view.empty:
        st.info("No search terms are currently flagged. Loosen the thresholds "
                "or enable more preset dictionaries in the sidebar.")
        return

    st.caption(
        f"{len(flagged_view):,} flagged search terms · "
        f"{ui.fmt_money(float(flagged_view['Wasted Spend'].sum()), currency)} wasted spend."
    )

    reason_filter = st.multiselect(
        "Filter by waste reason",
        options=sorted(
            {r for reasons in flagged_view["Waste Reason"] for r in str(reasons).split(" + ")}
        ),
        default=[],
        key="term_reason_filter",
    )
    if reason_filter:
        mask = flagged_view["Waste Reason"].apply(
            lambda reasons: any(r in str(reasons) for r in reason_filter)
        )
        flagged_view = flagged_view[mask]

    capped = flagged_view.head(DEFAULT_EDITOR_ROW_CAP).copy()
    display = capped[
        ["Search term", "Campaign", "Match type", "Clicks", "Cost",
         "Conversions", "CPA", "Wasted Spend", "Waste Reason", "Priority Score"]
    ].round(2)
    display.insert(0, "Add to Negatives", (capped["Priority Score"] >= 60).tolist())

    edited = st.data_editor(
        display,
        key="term_editor",
        hide_index=True,
        width="stretch",
        height=430,
        disabled=[col for col in display.columns if col != "Add to Negatives"],
        column_config={
            "Add to Negatives": st.column_config.CheckboxColumn(
                "Add to Negatives",
                help="Check rows to stage them as negative keywords in Tab 4.",
                default=False,
            ),
            "Search term": st.column_config.TextColumn("Search term", width="large"),
            "Waste Reason": st.column_config.TextColumn("Waste Reason", width="medium"),
            "Cost": st.column_config.NumberColumn("Cost", format="%.2f"),
            "CPA": st.column_config.NumberColumn("CPA", format="%.2f"),
            "Wasted Spend": st.column_config.NumberColumn("Wasted Spend", format="%.2f"),
        },
    )

    checked = int(edited["Add to Negatives"].sum())
    if st.button(f"Add checked search terms to Negative Staging ({checked})", type="primary"):
        selected = edited[edited["Add to Negatives"]]
        added = stage_negatives(
            [
                {
                    "keyword": row["Search term"],
                    "source": "Search Term Auditor",
                    "reason": row.get("Waste Reason", ""),
                    "wasted": float(row.get("Wasted Spend", 0.0) or 0),
                }
                for _, row in selected.iterrows()
            ]
        )
        st.success(f"Added {added} new negative keyword(s) to the staging list in Tab 4.")

    render_ai_audit(df)


def _gemini_secret_key() -> str:
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        return str(st.secrets.get("GEMINI_API_KEY", "") or "").strip()
    except (FileNotFoundError, KeyError, RuntimeError, StreamlitAPIException):
        return ""


def render_ai_audit(df: pd.DataFrame) -> None:
    with st.expander("Optional: AI Intent Audit (Gemini, BYOK)", expanded=False):
        st.caption(
            "Classifies the top 100 highest-spend non-converting search terms into "
            "High Commercial Intent / Informational / Competitor / Job / Irrelevant "
            "with a one-sentence justification. Entirely optional — the app is 100% "
            "functional without it. Your key is used in-memory only and never stored."
        )
        api_key = st.text_input(
            "Gemini API key (paste here, or set GEMINI_API_KEY in st.secrets)",
            value=_gemini_secret_key(),
            type="password",
            key="gemini_key",
        )
        model = st.selectbox("Model", list(GEMINI_MODELS), key="gemini_model")

        candidates = (
            df[pd.to_numeric(df["Conversions"], errors="coerce").fillna(0) <= 0]
            .sort_values("Cost", ascending=False)
            .head(100)["Search term"].tolist()
        )
        st.caption(f"{len(candidates)} candidate terms ready to classify.")

        if st.button("Run AI Intent Audit", disabled=not api_key or not candidates):
            try:
                with st.status("Classifying search intent…", expanded=True) as status:

                    def _progress(fraction: float, message: str) -> None:
                        status.update(
                            label=f"Classifying… {int(fraction * 100)}% — {message}"
                        )

                    result = run_gemini_audit(candidates, api_key, model=model,
                                              progress=_progress)
                    status.update(
                        label=f"Audit complete — {len(result)} terms classified.",
                        state="complete",
                    )
                st.session_state["ai_audit"] = result
            except GeminiAuditError as exc:
                st.error(str(exc))

        if st.session_state.get("ai_audit") is not None:
            audit = st.session_state["ai_audit"]
            st.dataframe(audit, hide_index=True, width="stretch", height=320)
            addable = audit[audit["AI Intent"].isin(["Irrelevant", "Job/Career", "Competitor"])]
            st.caption(
                f"{len(addable)} terms classified as Irrelevant / Job / Competitor "
                "are recommended negatives."
            )
            if not addable.empty and st.button(
                f"Add {len(addable)} AI-flagged terms to Negative Staging"
            ):
                added = stage_negatives(
                    [
                        {
                            "keyword": row["Search term"],
                            "source": "AI Intent Audit",
                            "reason": row["AI Intent"],
                            "wasted": 0.0,
                        }
                        for _, row in addable.iterrows()
                    ]
                )
                st.success(f"Added {added} new negative keyword(s) to Tab 4.")


# ---------------------------------------------------------------------------
# Tab 4 — Negative Keyword Builder, Conflict Guard & Exports
# ---------------------------------------------------------------------------
def render_export_builder(analysis: dict, df: pd.DataFrame, currency: str,
                          config: WasteConfig, days: int, date_range: str) -> None:
    staged = st.session_state.get("staged_negatives", [])
    if not staged:
        st.info(
            "No negatives staged yet. Check rows in the **N-Gram Explorer** "
            "(Tab 2) or the **Search Term Auditor** (Tab 3) and add them here."
        )
        ui.render_footer_cta()
        return

    display = pd.DataFrame(staged)[["keyword", "source", "reason", "wasted"]].copy()
    display.columns = ["Keyword", "Source", "Reason", "Wasted Spend"]
    display = display.round(2)
    display.insert(0, "Include", True)

    edited = st.data_editor(
        display,
        key="staging_editor",
        hide_index=True,
        width="stretch",
        height=min(120 + 35 * len(display), 420),
        disabled=[col for col in display.columns if col != "Include"],
        column_config={
            "Include": st.column_config.CheckboxColumn("Include", default=True),
            "Keyword": st.column_config.TextColumn("Keyword", width="large"),
            "Wasted Spend": st.column_config.NumberColumn("Wasted Spend", format="%.2f"),
        },
    )
    selected_rows = edited[edited["Include"]]
    keywords = selected_rows["Keyword"].astype(str).str.strip().tolist()
    if not keywords:
        st.warning("All staged keywords are excluded. Re-check rows to export.")
        return

    st.markdown('<div class="section-title">Apply & export</div>', unsafe_allow_html=True)
    controls = st.columns([1, 1, 1.2, 1.2])
    with controls[0]:
        match_type = st.radio(
            "Match type", list(MATCH_TYPES), horizontal=True, key="match_type",
            help="Exact blocks only identical queries. Phrase blocks queries "
                 "containing the phrase. Broad blocks queries containing all "
                 "the negative's words.",
        )
    with controls[1]:
        level = st.selectbox("Apply at level", list(LEVELS), key="negative_level")
    campaign, ad_group = "", ""
    if level in ("Campaign", "Ad Group"):
        campaigns = sorted(df["Campaign"].astype(str).unique().tolist())
        with controls[2]:
            campaign = st.selectbox("Campaign", campaigns, key="negative_campaign")
    if level == "Ad Group":
        ad_groups = sorted(
            df.loc[df["Campaign"] == campaign, "Ad group"].astype(str).unique().tolist()
        )
        with controls[3]:
            ad_group = st.selectbox("Ad group", ad_groups or ["All"], key="negative_adgroup")

    # --- conflict guard (critical differentiator) ----------------------------
    conflicts = find_conflicts(keywords, match_type, df)
    if not conflicts.empty:
        blocked_conv = float(conflicts["Conversions"].sum())
        blocked_value = float(conflicts["Conv. Value"].sum())
        st.error(
            f"Conflict guard: **{conflicts['Negative Keyword'].nunique()} staged "
            f"negative(s) would block {len(conflicts)} converting quer(ies)** "
            f"representing {int(blocked_conv)} conversions and "
            f"{ui.fmt_money(blocked_value, currency)} of conversion value."
        )
        st.dataframe(conflicts, hide_index=True, width="stretch", height=240)
        if st.button("Remove Conflicting Negatives", type="primary"):
            bad = set(conflicts["Negative Keyword"].astype(str))
            st.session_state["staged_negatives"] = [
                item for item in staged if item["keyword"] not in bad
            ]
            st.session_state.pop("staging_editor", None)
            st.success("Conflicting negatives removed from the staging list.")
            st.rerun()
    else:
        st.success("No conflicts — none of the staged negatives block a converting query.")

    # --- export channel 1: copy-paste block ----------------------------------
    st.markdown('<div class="section-title">1. Copy-paste block</div>', unsafe_allow_html=True)
    st.caption("Paste directly into Google Ads negative keyword lists (Shared "
               "Library > Negative keyword lists, or per-campaign negatives).")
    st.code(build_copy_paste_block(keywords, match_type, level, campaign, ad_group),
            language=None)

    # --- export channel 2: Google Ads Editor CSV ------------------------------
    st.markdown('<div class="section-title">2. Google Ads Editor CSV</div>', unsafe_allow_html=True)
    if level == "Account Negative List":
        st.caption("Account-level rows have blank Campaign cells — for account "
                   "negative lists, prefer the copy-paste block above.")
    editor_csv = build_editor_csv(keywords, match_type, level, campaign, ad_group)

    # --- export channel 3: Excel client audit report ---------------------------
    st.markdown('<div class="section-title">3. Client Audit Excel Report (.xlsx)</div>',
                unsafe_allow_html=True)
    st.caption("Branded multi-tab workbook: Executive Summary, Top Wasted "
               "N-Grams, Flagged Search Terms, Approved Negative List.")
    flagged_terms = analysis["flagged_terms"]
    combined_ngrams = pd.concat(
        [t[t["Waste Flag"]] for t in analysis["ngram_tables"].values()],
        ignore_index=True,
    ).sort_values("Wasted Spend", ascending=False).head(50)
    flagged_terms_top = (
        flagged_terms[flagged_terms["Waste Flag"]]
        .sort_values("Wasted Spend", ascending=False).head(200)
    )
    negatives_sheet = pd.DataFrame(
        {
            "Keyword": selected_rows["Keyword"].tolist(),
            "Match Type": match_type,
            "Level": level,
            "Campaign": campaign,
            "Ad Group": ad_group,
            "Source": selected_rows["Source"].tolist(),
            "Reason": selected_rows["Reason"].tolist(),
            "Wasted Spend": selected_rows["Wasted Spend"].tolist(),
        }
    )
    total_spend = float(df["Cost"].sum())
    wasted_spend = float(flagged_terms["Wasted Spend"].sum())
    summary = {
        "total_spend": total_spend,
        "wasted_spend": wasted_spend,
        "waste_pct": (wasted_spend / total_spend * 100) if total_spend else 0.0,
        "annualized_savings": wasted_spend / max(days, 1) * 365,
        "wasted_terms": int(flagged_terms["Waste Flag"].sum()),
        "wasted_ngrams": sum(int(t["Waste Flag"].sum())
                             for t in analysis["ngram_tables"].values()),
        "date_range": date_range,
        "days": days,
        "currency": currency,
        "target_cpa": config.target_cpa,
        "cpa_multiplier": config.cpa_multiplier,
        "zero_conv_threshold": config.zero_conv_threshold,
        "min_clicks": config.min_clicks,
        "brand_terms": ", ".join(config.brand_terms),
        "presets": ", ".join(config.presets.keys()) or "none",
        "match_type": match_type,
        "level": level,
    }
    xlsx = build_excel_report(summary, combined_ngrams, flagged_terms_top,
                              negatives_sheet, currency)

    download_cols = st.columns(2)
    with download_cols[0]:
        st.download_button(
            "Download Google Ads Editor CSV",
            data=editor_csv,
            file_name=f"adwaste_negatives_{safe_filename(level or 'account')}.csv",
            mime="text/csv",
            width="stretch",
            type="primary",
        )
    with download_cols[1]:
        st.download_button(
            "Download Client Audit Report (.xlsx)",
            data=xlsx,
            file_name=f"AdWaste_Audit_{pd.Timestamp.now():%Y%m%d}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
            type="primary",
        )

    ui.render_footer_cta()


# ---------------------------------------------------------------------------
# Main flow
# ---------------------------------------------------------------------------
def main() -> None:
    st.markdown(f"### {APP_NAME}")
    st.caption(APP_TAGLINE)

    if st.session_state.get("terms_df") is None:
        render_landing()
        ui.render_footer()
        return

    df: pd.DataFrame = st.session_state["terms_df"]
    currency: str = st.session_state.get("currency", "$")
    days: int = int(st.session_state.get("days", DEFAULT_DAYS))
    date_range: str = st.session_state.get("date_range", "")

    config, stopwords_on = build_sidebar(df)

    st.markdown(
        f'<div class="adw-meta">'
        f'<span class="reason-chip chip-protected">{ui.fmt_int(len(df))} search terms</span>'
        f'<span class="reason-chip chip-highcpa">'
        f'{ui.fmt_money(float(df["Cost"].sum()), currency).replace("$", "&#36;")} spend</span>'
        f'<span class="reason-chip chip-job">{date_range or "window unknown"} · {days} days</span>'
        f"</div>",
        unsafe_allow_html=True,
    )
    if st.session_state.get("upload_warnings"):
        with st.expander("Import notes"):
            for warning in st.session_state["upload_warnings"]:
                st.write(f"- {warning}")

    analysis = compute_analysis(
        df,
        exclude_stopwords=stopwords_on,
        target_cpa=config.target_cpa,
        cpa_multiplier=config.cpa_multiplier,
        zero_conv_threshold=config.zero_conv_threshold,
        min_clicks=config.min_clicks,
        brand_terms=tuple(config.brand_terms),
        preset_names=tuple(config.presets.keys()),
    )

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "Executive Waste Overview",
            "N-Gram Intelligence Explorer",
            "Search Term Auditor & AI Intent",
            "Negative Builder & Exports",
        ]
    )
    with tab1:
        render_overview(analysis, df, currency, days, date_range)
    with tab2:
        render_ngram_explorer(analysis, df, currency)
    with tab3:
        render_term_auditor(analysis, df, currency)
    with tab4:
        render_export_builder(analysis, df, currency, config, days, date_range)

    ui.render_footer()


main()
