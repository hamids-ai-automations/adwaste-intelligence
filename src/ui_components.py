"""Reusable UI: custom CSS, KPI cards, Plotly charts and lead-magnet banners."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.constants import (
    APP_NAME,
    APP_TAGLINE,
    APP_VERSION,
    AUTHOR_NAME,
    CHROME_EXTENSION_URL,
    GITHUB_URL,
    WHATSAPP_URL,
)

_CURRENCY_DISPLAY = {
    "USD": "$", "US$": "$", "EUR": "€", "GBP": "£", "INR": "₹",
    "Rs": "Rs ", "PKR": "PKR ", "AED": "AED ", "SAR": "SAR ",
    "CA$": "CA$", "A$": "A$", "$": "$", "€": "€", "£": "£", "₹": "₹",
}

REASON_COLORS = {
    "Zero-Conv Bleeder": "#DC2626",
    "High CPA": "#F59E0B",
    "Job Intent": "#C2410C",
    "Free/Cheap Intent": "#DB2777",
    "Free/DIY Intent": "#DB2777",
    "Support Intent": "#6B21A8",
}


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def display_currency(currency: str) -> str:
    return _CURRENCY_DISPLAY.get(currency, f"{currency} ")


def fmt_money(value: float, currency: str = "$", compact: bool = False) -> str:
    symbol = display_currency(currency)
    try:
        value = float(value)
    except (TypeError, ValueError):
        return f"{symbol}0"
    if compact and abs(value) >= 1000:
        return f"{symbol}{value / 1000:,.1f}k"
    return f"{symbol}{value:,.2f}"


def fmt_pct(value: float) -> str:
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return "0.0%"


def fmt_int(value) -> str:
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return "0"


# ---------------------------------------------------------------------------
# CSS + static banners
# ---------------------------------------------------------------------------
def inject_css() -> None:
    st.markdown(
        """
        <style>
          .adw-header { padding: 6px 0 2px 0; }
          .adw-title { font-size: 30px; font-weight: 800; color: #0F172A;
                       letter-spacing: -0.02em; line-height: 1.15; }
          .adw-sub { font-size: 14.5px; color: #475569; margin-top: 4px; }
          .adw-meta { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }

          .kpi-grid { display: grid; grid-template-columns:
                      repeat(auto-fit, minmax(170px, 1fr)); gap: 12px;
                      margin: 10px 0 16px 0; }
          .kpi-card { background: #FFFFFF; border: 1px solid #E2E8F0;
                      border-radius: 12px; padding: 14px 16px;
                      box-shadow: 0 1px 2px rgba(15,23,42,0.05); }
          .kpi-label { font-size: 10.5px; font-weight: 700; letter-spacing: 0.07em;
                       text-transform: uppercase; color: #64748B; }
          .kpi-value { font-size: 21px; font-weight: 800; color: #0F172A;
                       margin-top: 5px; word-break: break-word; }
          .kpi-sub { font-size: 12px; color: #64748B; margin-top: 3px; }
          .tone-bad .kpi-value { color: #DC2626; }
          .tone-good .kpi-value { color: #059669; }
          .tone-warn .kpi-value { color: #D97706; }

          .privacy-strip { display: inline-flex; align-items: center; gap: 8px;
                           background: #ECFDF5; border: 1px solid #A7F3D0;
                           color: #065F46; border-radius: 999px;
                           padding: 6px 14px; font-size: 12.5px; font-weight: 600;
                           margin: 4px 0 10px 0; }

          .reason-chip { display: inline-block; border-radius: 999px;
                         padding: 3px 10px; font-size: 11px; font-weight: 700;
                         margin: 0 6px 6px 0; }
          .chip-bleeder { background: #FEE2E2; color: #991B1B; }
          .chip-highcpa { background: #FEF3C7; color: #92400E; }
          .chip-job { background: #FFEDD5; color: #9A3412; }
          .chip-free { background: #FCE7F3; color: #9D174D; }
          .chip-support { background: #F3E8FF; color: #6B21A8; }
          .chip-protected { background: #ECFDF5; color: #065F46; }

          .cta-card { background: linear-gradient(135deg, #064E3B 0%, #059669 100%);
                      border-radius: 14px; padding: 16px 18px; color: #FFFFFF;
                      margin-top: 10px; }
          .cta-card .cta-title { font-size: 15px; font-weight: 800; }
          .cta-card .cta-text { font-size: 12.5px; opacity: 0.92; margin: 6px 0 10px 0;
                                line-height: 1.45; }
          .cta-btn { display: inline-block; background: #FFFFFF; color: #065F46;
                     font-weight: 700; font-size: 12.5px; border-radius: 999px;
                     padding: 7px 16px; text-decoration: none; margin-right: 8px; }
          .cta-btn.ghost { background: rgba(255,255,255,0.14); color: #FFFFFF;
                           border: 1px solid rgba(255,255,255,0.45); }

          .ext-card { border: 1px solid #E2E8F0; border-radius: 12px;
                      padding: 12px 14px; margin-top: 10px; background: #F8FAFC; }
          .ext-title { font-size: 13px; font-weight: 700; color: #0F172A; }
          .ext-text { font-size: 12px; color: #475569; margin-top: 4px;
                      line-height: 1.45; }

          .hero-wrap { padding: 10px 0 4px 0; }
          .hero-title { font-size: 34px; font-weight: 800; color: #0F172A;
                        letter-spacing: -0.02em; line-height: 1.1; }
          .hero-sub { font-size: 16px; color: #475569; margin-top: 8px;
                      line-height: 1.5; max-width: 780px; }
          .hero-points { margin-top: 14px; font-size: 13.5px; color: #334155;
                         line-height: 1.7; }

          .footer-cta { background: linear-gradient(135deg, #064E3B 0%, #059669 100%);
                        border-radius: 14px; padding: 20px 24px; color: #FFFFFF;
                        display: flex; align-items: center; justify-content: space-between;
                        gap: 16px; flex-wrap: wrap; margin-top: 22px; }
          .footer-cta .cta-title { font-size: 17px; font-weight: 800; }
          .footer-cta .cta-text { font-size: 13px; opacity: 0.92; margin-top: 4px; }

          .app-footer { margin-top: 26px; padding-top: 14px; border-top: 1px solid #E2E8F0;
                        font-size: 12px; color: #64748B; }
          .app-footer a { color: #059669; text-decoration: none; font-weight: 600; }

          .section-title { font-size: 17px; font-weight: 800; color: #0F172A;
                           margin: 18px 0 8px 0; }
          .dataframe td, .dataframe th { font-size: 12.5px !important; }
          div[data-testid="stDataFrame"] { border: 1px solid #E2E8F0; border-radius: 10px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(meta_html: str = "") -> None:
    st.markdown(
        f"""
        <div class="adw-header">
          <div class="adw-title">{APP_NAME}</div>
          <div class="adw-sub">{APP_TAGLINE} — v{APP_VERSION}</div>
          {meta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_privacy_strip() -> None:
    st.markdown(
        '<div class="privacy-strip">100% In-Memory Processing — '
        "your client CSV data is never saved or logged.</div>",
        unsafe_allow_html=True,
    )


def render_reason_legend() -> None:
    st.markdown(
        """
        <div>
          <span class="reason-chip chip-bleeder">Zero-Conv Bleeder</span>
          <span class="reason-chip chip-highcpa">High CPA</span>
          <span class="reason-chip chip-job">Job Intent</span>
          <span class="reason-chip chip-free">Free/Cheap/DIY Intent</span>
          <span class="reason-chip chip-support">Support Intent</span>
          <span class="reason-chip chip-protected">Protected (brand)</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_cta() -> None:
    extension_html = (
        f'<a class="cta-btn" href="{CHROME_EXTENSION_URL}" target="_blank" '
        'rel="noopener noreferrer">Open Chrome extension</a>'
        if CHROME_EXTENSION_URL
        else '<span class="ext-text">Chrome Web Store listing launching soon — '
        "watch this space.</span>"
    )
    st.markdown(
        f"""
        <div class="cta-card">
          <div class="cta-title">Found wasted spend?</div>
          <div class="cta-text">Book a free 15-minute Google Ads Account Waste
          Audit with {AUTHOR_NAME}. Bring your report, leave with a fix list.</div>
          <a class="cta-btn" href="{WHATSAPP_URL}" target="_blank" rel="noopener noreferrer">WhatsApp audit call</a>
          <a class="cta-btn ghost" href="{GITHUB_URL}" target="_blank" rel="noopener noreferrer">GitHub</a>
        </div>
        <div class="ext-card">
          <div class="ext-title">Google Ads Waste Detector — Chrome extension</div>
          <div class="ext-text">Companion extension that flags waste right inside
          the Google Ads UI. Run the deep n-gram audit and Excel export here.</div>
          {extension_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer_cta() -> None:
    st.markdown(
        f"""
        <div class="footer-cta">
          <div>
            <div class="cta-title">Stop paying for irrelevant clicks.</div>
            <div class="cta-text">Export your list, then book a free 15-minute
            waste audit with {AUTHOR_NAME} to implement it in one sitting.</div>
          </div>
          <div>
            <a class="cta-btn" href="{WHATSAPP_URL}" target="_blank" rel="noopener noreferrer">Book free audit</a>
            <a class="cta-btn ghost" href="{GITHUB_URL}" target="_blank" rel="noopener noreferrer">GitHub</a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    st.markdown(
        f"""
        <div class="app-footer">
          {APP_NAME} v{APP_VERSION} — built by <a href="{GITHUB_URL}"
          target="_blank" rel="noopener noreferrer">{AUTHOR_NAME}</a>.
          Companion to the Google Ads Waste Detector Chrome extension.
          100% in-memory processing: uploads are never stored.
          <a href="{WHATSAPP_URL}" target="_blank" rel="noopener noreferrer">Book a free waste audit</a>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
def _escape_math(text: str) -> str:
    """Escape $ so Streamlit's markdown->KaTeX pass never treats currency
    amounts as LaTeX math delimiters (two $ in one block = math mode)."""
    return str(text).replace("$", "&#36;")


def render_kpi_cards(cards: list[dict]) -> None:
    """cards: list of {label, value, sub, tone} dicts.

    All cards are emitted as a single-line HTML string: blank lines inside a
    markdown-embedded HTML block would terminate the block and render the
    remaining cards as an indented code block.
    """
    card_html = []
    for card in cards:
        tone = card.get("tone", "")
        cls = f"kpi-card tone-{tone}" if tone else "kpi-card"
        card_html.append(
            f'<div class="{cls}">'
            f'<div class="kpi-label">{_escape_math(card["label"])}</div>'
            f'<div class="kpi-value">{_escape_math(card["value"])}</div>'
            f'<div class="kpi-sub">{_escape_math(card.get("sub", ""))}</div>'
            f"</div>"
        )
    st.markdown(
        '<div class="kpi-grid">' + "".join(card_html) + "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Plotly charts
# ---------------------------------------------------------------------------
def reason_color(reason: str) -> str:
    for key, color in REASON_COLORS.items():
        if key in str(reason):
            return color
    return "#DC2626"


def spend_allocation_chart(
    converting: float, wasted: float, unproven: float, currency: str = "$"
) -> go.Figure:
    symbol = display_currency(currency)
    labels = ["Converting Spend", "Non-Converting Flagged Waste", "Low-Volume / Unproven Spend"]
    values = [converting, wasted, unproven]
    colors = ["#059669", "#DC2626", "#D97706"]

    total = sum(values)
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.62,
            marker_colors=colors,
            texttemplate="%{percent:.1%}",
            textfont_size=12,
            hovertemplate="%{label}<br>Spend: "
            + symbol
            + "%{value:,.2f}<extra></extra>",
        )
    )
    fig.add_annotation(
        text=f"<b>{fmt_money(total, currency, compact=True)}</b><br>"
        f"<span style='font-size:11px;color:#64748B'>total spend</span>",
        showarrow=False,
        font_size=15,
    )
    fig.update_layout(
        template="plotly_white",
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=-0.12, x=0.5, xanchor="center"),
    )
    return fig


def top_wasted_ngrams_chart(df: pd.DataFrame, currency: str = "$") -> go.Figure:
    """Horizontal bar of the top wasted n-grams, color-coded by reason."""
    symbol = display_currency(currency)
    data = df.sort_values("Wasted Spend", ascending=True).tail(15)
    colors = [
        "#F59E0B" if "High CPA" in str(r) else reason_color(r)
        for r in data["Waste Reason"]
    ]
    fig = go.Figure(
        go.Bar(
            y=data["N-Gram"],
            x=data["Wasted Spend"],
            orientation="h",
            marker_color=colors,
            hovertemplate=(
                "<b>%{y}</b><br>Wasted: "
                + symbol
                + "%{x:,.2f}<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        template="plotly_white",
        height=max(340, 28 * len(data)),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title=f"Wasted spend ({symbol})",
        yaxis=dict(autorange="reversed", tickfont_size=11.5),
    )
    return fig


def campaign_waste_chart(df: pd.DataFrame, currency: str = "$") -> go.Figure:
    """Grouped bar: total spend vs wasted spend per campaign."""
    symbol = display_currency(currency)
    top = df.sort_values("Total Spend", ascending=False).head(10)
    campaigns = [
        c if len(str(c)) <= 34 else str(c)[:32] + "…" for c in top["Campaign"]
    ]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=campaigns,
            y=top["Total Spend"],
            name="Total spend",
            marker_color="#94A3B8",
            hovertemplate="Total: " + symbol + "%{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=campaigns,
            y=top["Wasted Spend"],
            name="Wasted spend",
            marker_color="#DC2626",
            hovertemplate="Wasted: " + symbol + "%{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        template="plotly_white",
        barmode="group",
        height=340,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, xanchor="left"),
        xaxis_tickangle=-18,
    )
    fig.update_yaxes(title=f"Spend ({symbol})")
    return fig
