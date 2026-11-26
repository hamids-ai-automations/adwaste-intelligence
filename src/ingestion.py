"""Bulletproof Google Ads Search Terms report ingestion.

Handles the notorious formatting quirks of Google Ads exports:

* 2 leading metadata rows ("Search terms report", date range) before the real
  header row -> auto-scans the first 10 rows for the header containing
  ``Search term``.
* Trailing ``Total: Search terms`` / ``Total: Account`` / ``Total: Filtered``
  summary rows -> stripped so spend is never double-counted.
* Encoding resilience: UTF-8, UTF-8-SIG (BOM), UTF-16 and Latin-1.
* Delimiter resilience: comma or tab.
* Currency sanitization: strips ``$``, ``AED``, ``PKR``, ``INR``, ``CA$`` ...
  symbols, thousands commas and ``%`` signs; coerces ``--`` / ``< 10%`` /
  ``N/A`` placeholders to ``0.0``.
* Flexible column auto-mapping with variant names + a runtime fallback mapping
  (used by the Streamlit column-mapping UI when a required column is missing).
"""

from __future__ import annotations

import codecs
import csv
import io
import re
from dataclasses import dataclass, field

import pandas as pd

from src.constants import (
    CANONICAL_COLUMNS,
    CURRENCY_TOKENS,
    NUMERIC_PLACEHOLDERS,
    NUMERIC_COLUMNS,
    REQUIRED_COLUMNS,
)

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

_TEXT_DATE_RANGE_RE = re.compile(
    r"([A-Za-z]{3,9}\.?\s+\d{1,2},?\s*\d{4})\s*(?:-|–|—|to)\s*"
    r"([A-Za-z]{3,9}\.?\s+\d{1,2},?\s*\d{4})",
    re.IGNORECASE,
)
_ISO_DATE_RANGE_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2})\s*(?:-|–|—|to)\s*(\d{4}-\d{2}-\d{2})"
)
_WS_RE = re.compile(r"\s+")

# Currency tokens ordered longest-first (safe for chained replacement)
_CURRENCY_REPLACEMENTS = sorted(CURRENCY_TOKENS, key=len, reverse=True)


class MissingColumnsError(Exception):
    """Raised when a required column cannot be auto-mapped.

    The Streamlit UI catches this and renders a column-mapping selectbox
    fallback, then re-runs :func:`load_report` with an explicit mapping.
    """

    def __init__(self, missing: list[str], available: list[str]) -> None:
        self.missing = list(missing)
        self.available = list(available)
        super().__init__(
            "Missing required column(s): "
            + ", ".join(self.missing)
            + ". Map them manually in the column-mapping step."
        )


@dataclass
class IngestionResult:
    """Cleaned search-terms data plus metadata gathered during parsing."""

    df: pd.DataFrame
    currency: str = "$"
    date_range: str = ""
    days: int = 30
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_report(
    data: bytes,
    filename: str = "",
    column_mapping: dict[str, str] | None = None,
) -> IngestionResult:
    """Parse raw Google Ads Search Terms CSV/XLSX bytes into a clean DataFrame.

    Args:
        data: raw file bytes (from ``st.file_uploader.getbuffer()`` etc.).
        filename: original file name (used to detect Excel files).
        column_mapping: optional explicit mapping ``canonical -> actual column``
            provided by the fallback mapping UI.

    Returns:
        IngestionResult with a canonical-schema DataFrame, detected currency,
        date range and warnings.

    Raises:
        MissingColumnsError: when a required column is missing and no explicit
            mapping resolves it.
        ValueError: when no header row containing a search-term column exists.
    """
    warnings: list[str] = []

    if _looks_like_excel(filename, data):
        rows = _read_excel_rows(data)
    else:
        rows = _read_csv_rows(data)

    if not rows:
        raise ValueError(
            "The uploaded file appears to be empty. Export a Search Terms "
            "report from Google Ads (Campaigns > Insights > Search terms)."
        )

    header_idx = _find_header_row(rows)
    if header_idx is None:
        raise ValueError(
            "Could not find a header row containing a 'Search term' column. "
            "Make sure you exported a Search Terms report, not another "
            "report type."
        )

    date_range, days = _extract_date_range(rows[:header_idx])

    headers = _clean_headers(rows[header_idx])
    body = [row for row in rows[header_idx + 1:] if _row_has_content(row)]
    df = _rows_to_dataframe(body, headers)

    mapping = dict(column_mapping) if column_mapping else {}
    auto = _map_columns(headers)
    for canonical, actual in auto.items():
        mapping.setdefault(canonical, actual)

    missing = [c for c in REQUIRED_COLUMNS if c not in mapping]
    if missing:
        raise MissingColumnsError(missing, available=headers)

    mapped_headers = set(mapping.values())
    ignored = [h for h in headers if h and h not in mapped_headers]
    if ignored:
        warnings.append("Ignored unmapped column(s): " + ", ".join(ignored))
    for optional in CANONICAL_COLUMNS:
        if optional not in mapping and optional not in REQUIRED_COLUMNS:
            warnings.append(f"Optional column '{optional}' missing — defaulted.")

    df = _apply_mapping(df, mapping)
    df = _strip_total_rows(df)
    df = df[df["Search term"].str.strip() != ""].reset_index(drop=True)

    if df.empty:
        raise ValueError(
            "No search-term rows found after cleaning. The report may only "
            "contain total/summary rows."
        )

    currency = _detect_currency(df["Cost"])
    for col in NUMERIC_COLUMNS:
        df[col] = df[col].map(sanitize_number)

    return IngestionResult(
        df=df, currency=currency, date_range=date_range, days=days, warnings=warnings
    )


# ---------------------------------------------------------------------------
# Row readers (CSV / Excel)
# ---------------------------------------------------------------------------
def _looks_like_excel(filename: str, data: bytes) -> bool:
    if filename.lower().endswith((".xlsx", ".xls")):
        return True
    return data[:2] == b"PK"


def _read_csv_rows(data: bytes) -> list[list[str]]:
    encoding = _detect_encoding(data)
    text = data.decode(encoding)
    text = text.lstrip("\ufeff")
    delimiter = _detect_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = []
    for row in reader:
        if _row_has_content(row):
            rows.append([str(cell) for cell in row])
    return rows


def _read_excel_rows(data: bytes) -> list[list[str]]:
    raw = pd.read_excel(io.BytesIO(data), header=None, dtype=str)
    return [
        ["" if pd.isna(v) else str(v) for v in record]
        for record in raw.values.tolist()
    ]


def _detect_encoding(data: bytes) -> str:
    if data.startswith(codecs.BOM_UTF16_LE) or data.startswith(codecs.BOM_UTF16_BE):
        return "utf-16"
    try:
        data.decode("utf-8-sig")
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "latin-1"


def _detect_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:12])
    counts = {
        "\t": sample.count("\t"),
        ",": sample.count(","),
        ";": sample.count(";"),
    }
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def _row_has_content(row: list) -> bool:
    return any(str(cell).strip() for cell in row)


# ---------------------------------------------------------------------------
# Header detection / column mapping
# ---------------------------------------------------------------------------
_HEADER_EXACT = {
    "Search term": {"search term", "search terms", "search query", "search keyword", "query", "keyword"},
    "Conv. value": {"conv. value", "conv value", "conversion value", "value / conv.", "value/conv."},
    "Conversions": {"conversions", "conv.", "conv", "total conv.", "total conversions", "conversions (1)"},
    "Cost": {"cost", "spend", "cost / spend"},
    "Clicks": {"clicks"},
    "Impr.": {"impr.", "impr", "impressions", "impressions."},
    "Campaign": {"campaign", "campaign name"},
    "Ad group": {"ad group", "ad group name"},
    "Match type": {"match type", "search keyword match type", "keyword match type"},
    "Added/Excluded": {"added/excluded", "added / excluded"},
}

_HEADER_CONTAINS = {
    "Search term": ("search term",),
    "Conv. value": ("conv. value", "conv value", "conversion value", "value / conv", "value/conv"),
    "Conversions": ("conversion", "conv"),
    "Cost": ("cost", "spend"),
    "Clicks": ("click",),
    "Impr.": ("impr", "impression"),
    "Campaign": ("campaign",),
    "Ad group": ("ad group",),
    "Match type": ("match type", "match"),
    "Added/Excluded": ("added/excluded", "added / excluded", "added exclusions"),
}

# Mapping priority matters: "Conv. value" must resolve before "Conversions".
_MAPPING_PRIORITY = (
    "Search term", "Conv. value", "Conversions", "Cost", "Clicks", "Impr.",
    "Campaign", "Ad group", "Match type", "Added/Excluded",
)


def _clean_headers(row: list) -> list[str]:
    headers = []
    used: dict[str, int] = {}
    for cell in row:
        name = _norm_header(cell)
        if not name:
            name = "unnamed"
        if name in used:
            used[name] += 1
            name = f"{name}.{used[name]}"
        else:
            used[name] = 1
        headers.append(name)
    return headers


def _norm_header(header: str) -> str:
    return _WS_RE.sub(" ", str(header).strip().lower())


def _rows_to_dataframe(body: list[list[str]], headers: list[str]) -> pd.DataFrame:
    """Build a DataFrame from possibly-ragged CSV rows.

    Google Ads total/summary rows frequently have a different field count
    than the header row, so every row is padded or truncated to a common
    width before construction (extra columns become ``unnamed.N``).
    """
    if not body:
        return pd.DataFrame(columns=headers)
    width = max([len(headers)] + [len(row) for row in body])
    padded_headers = list(headers) + [f"unnamed.{i}" for i in range(len(headers), width)]
    padded_rows = []
    for row in body:
        if len(row) < width:
            row = row + [""] * (width - len(row))
        elif len(row) > width:
            row = row[:width]
        padded_rows.append(row)
    return pd.DataFrame(padded_rows, columns=padded_headers)


def _find_header_row(rows: list[list[str]]) -> int | None:
    for idx, row in enumerate(rows[:10]):
        cells = [_norm_header(c) for c in row if str(c).strip()]
        if any(c in _HEADER_EXACT["Search term"] for c in cells):
            return idx
    for idx, row in enumerate(rows[:10]):
        joined = " ".join(str(c) for c in row).lower()
        if "search term" in joined:
            return idx
    return None


def _map_columns(headers: list[str]) -> dict[str, str]:
    """Best-effort automatic mapping of canonical columns to actual headers."""
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for canonical in _MAPPING_PRIORITY:
        exact = _HEADER_EXACT[canonical]
        contains = _HEADER_CONTAINS[canonical]
        # Pass 1: exact match
        for header in headers:
            if header in used:
                continue
            if _norm_header(header) in exact:
                mapping[canonical] = header
                used.add(header)
                break
        if canonical in mapping:
            continue
        # Pass 2: contains match
        for header in headers:
            if header in used:
                continue
            norm = _norm_header(header)
            if any(pattern in norm for pattern in contains):
                mapping[canonical] = header
                used.add(header)
                break
    return mapping


def _resolve_column(source, columns) -> str | None:
    """Resolve a mapped header name against actual columns (case-insensitive)."""
    if source is None:
        return None
    source = str(source)
    if source in columns:
        return source
    lowered = {str(c).lower(): c for c in columns}
    return lowered.get(source.lower().strip())


def _apply_mapping(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    term_col = _resolve_column(mapping["Search term"], df.columns)
    out["Search term"] = df[term_col].astype(str).str.strip()
    for canonical in NUMERIC_COLUMNS:
        source = _resolve_column(mapping.get(canonical), df.columns)
        if source is not None:
            out[canonical] = df[source].tolist()
        else:
            out[canonical] = 0.0
    for canonical in ("Campaign", "Ad group", "Match type", "Added/Excluded"):
        source = _resolve_column(mapping.get(canonical), df.columns)
        if source is not None:
            out[canonical] = df[source].astype(str).str.strip()
        else:
            out[canonical] = "All"
    return out


def _strip_total_rows(df: pd.DataFrame) -> pd.DataFrame:
    if "Search term" not in df.columns:
        return df
    terms = df["Search term"].astype(str).str.strip().str.lower()
    mask = ~terms.str.startswith("total:")
    return df[mask].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Numeric / currency sanitization
# ---------------------------------------------------------------------------
def sanitize_number(value) -> float:
    """Coerce a messy Google Ads metric value to a safe float.

    Handles currency symbols, thousands commas, percent signs and
    placeholder values such as ``--`` or ``< 10%``.
    """
    if value is None:
        return 0.0
    if isinstance(value, float) and pd.isna(value):
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    if text.lower() in NUMERIC_PLACEHOLDERS:
        return 0.0
    if text.startswith("<"):
        # "< 10%" / "<1" style privacy-threshold placeholders
        return 0.0
    for token in _CURRENCY_REPLACEMENTS:
        text = text.replace(token, " ")
    text = text.replace(",", "").replace("%", "").replace("\xa0", " ")
    text = text.replace(" ", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _detect_currency(series: pd.Series) -> str:
    """Scan raw cost values for a leading currency token."""
    for value in series.head(500):
        text = str(value).strip()
        if not text:
            continue
        for token in _CURRENCY_REPLACEMENTS:
            if text.startswith(token):
                rest = text[len(token):].lstrip()
                if rest and (rest[0].isdigit() or rest[0] in "(.-"):
                    return token
    return "$"


# ---------------------------------------------------------------------------
# Date-range extraction (annualized savings math)
# ---------------------------------------------------------------------------
def _parse_loose_date(text: str):
    text = text.strip().rstrip(".")
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso:
        return int(iso.group(1)), int(iso.group(2)), int(iso.group(3))
    dmy = re.fullmatch(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s*(\d{4})", text)
    if dmy:
        month = _MONTHS.get(dmy.group(2)[:3].lower())
        if month:
            return int(dmy.group(3)), month, int(dmy.group(1))
    mdy = re.fullmatch(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s*(\d{4})", text)
    if mdy:
        month = _MONTHS.get(mdy.group(1)[:3].lower())
        if month:
            return int(mdy.group(3)), month, int(mdy.group(2))
    return None


def _extract_date_range(metadata_rows: list[list[str]]) -> tuple[str, int]:
    """Find a date range in the metadata rows above the header.

    Returns ``(display_string, days)`` — defaults to ``("", 30)``.
    """
    import datetime as _dt

    for row in metadata_rows:
        # Commas inside the date text split it across CSV cells — join first.
        text = " ".join(str(cell) for cell in row).strip()
        if not text:
            continue
        for regex in (_TEXT_DATE_RANGE_RE, _ISO_DATE_RANGE_RE):
            match = regex.search(text)
            if not match:
                continue
            start = _parse_loose_date(match.group(1))
            end = _parse_loose_date(match.group(2))
            if start and end:
                try:
                    start_date = _dt.date(*start)
                    end_date = _dt.date(*end)
                    days = (end_date - start_date).days + 1
                    days = max(1, min(days, 3650))
                    display = (
                        f"{start_date:%b} {start_date.day}, {start_date.year} - "
                        f"{end_date:%b} {end_date.day}, {end_date.year}"
                    )
                    return display, days
                except ValueError:
                    continue
    return "", 30
