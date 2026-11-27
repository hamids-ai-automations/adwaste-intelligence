"""Rule-based waste flagging, negative-keyword conflict guard and the
optional Gemini BYOK semantic intent audit.

Waste rules (an n-gram or search term is flagged when any rule matches and
it is NOT protected by the brand whitelist):

1. Zero-Conv Bleeder  : Conversions == 0 AND Cost >= zero-conv threshold
                        AND Clicks >= min clicks.
2. High CPA           : Conversions > 0 AND CPA >= Target CPA x multiplier.
                        Wasted spend is the portion above the acceptable
                        Target-CPA budget (cost - target_cpa x conversions).
3. Preset Intent      : matches an enabled preset waste dictionary AND
                        Conversions == 0 (full cost counted as waste).

Efficiency / Waste Priority Score (0-100) ranks flagged rows by wasted-spend
impact so the biggest budget leaks surface at the top.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
import pandas as pd

from src.constants import (
    GEMINI_BATCH_SIZE,
    GEMINI_INTENT_CATEGORIES,
    GEMINI_MODEL_DEFAULT,
    PRESET_REASON_LABELS,
)
from src.ngram_engine import normalize_term


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass
class WasteConfig:
    """Sidebar-driven waste detection configuration."""

    target_cpa: float = 100.0
    cpa_multiplier: float = 2.0
    zero_conv_threshold: float = 100.0
    min_clicks: int = 3
    brand_terms: tuple[str, ...] = ()
    presets: dict[str, tuple[str, ...]] = field(default_factory=dict)


@lru_cache(maxsize=256)
def _phrase_pattern(tokens: tuple[str, ...]):
    parts = sorted(
        (re.escape(t.strip().lower()) for t in tokens if t and t.strip()),
        key=len,
        reverse=True,
    )
    if not parts:
        return None
    return re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)


def _contains_any(series: pd.Series, tokens: tuple[str, ...]) -> np.ndarray:
    pattern = _phrase_pattern(tokens)
    if pattern is None:
        return np.zeros(len(series), dtype=bool)
    return series.str.contains(pattern).to_numpy(dtype=bool)


# ---------------------------------------------------------------------------
# Waste flagging
# ---------------------------------------------------------------------------
def apply_waste_rules(
    table: pd.DataFrame, config: WasteConfig, term_column: str = "N-Gram"
) -> pd.DataFrame:
    """Return a copy of ``table`` with waste columns appended.

    Added columns: Protected, Waste Flag, Waste Reason, Wasted Spend,
    Priority Score.
    """
    out = table.copy()
    terms = out[term_column].astype(str)
    normalized = terms.map(normalize_term)

    cost = pd.to_numeric(out["Cost"], errors="coerce").fillna(0.0).to_numpy(float)
    clicks = pd.to_numeric(out["Clicks"], errors="coerce").fillna(0.0).to_numpy(float)
    conv = pd.to_numeric(out["Conversions"], errors="coerce").fillna(0.0).to_numpy(float)
    has_conv = conv > 0

    # Row-level search-term tables do not carry a CPA column — derive it so
    # downstream UI/exports can rely on a uniform schema.
    if "CPA" not in out.columns:
        out["CPA"] = np.where(conv > 0, cost / np.maximum(conv, 1e-9), 0.0)

    # --- brand whitelist protection ---------------------------------------
    protected = _contains_any(normalized, tuple(t.lower() for t in config.brand_terms))

    # --- rule 3: preset intent dictionaries --------------------------------
    reasons: list[list[str]] = [[] for _ in range(len(out))]
    preset_mask = np.zeros(len(out), dtype=bool)
    for name, tokens in config.presets.items():
        if not tokens:
            continue
        mask = _contains_any(normalized, tuple(tokens)) & (~has_conv)
        if not mask.any():
            continue
        preset_mask |= mask
        label = PRESET_REASON_LABELS.get(name, name)
        for idx in np.nonzero(mask)[0]:
            reasons[idx].append(label)

    # --- rule 1: zero-conversion bleeder ------------------------------------
    zero_mask = (~has_conv) & (cost >= config.zero_conv_threshold) & (clicks >= config.min_clicks)
    for idx in np.nonzero(zero_mask)[0]:
        reasons[idx].append("Zero-Conv Bleeder")

    # --- rule 2: high CPA ----------------------------------------------------
    cpa = np.where(conv > 0, cost / np.maximum(conv, 1e-9), np.inf)
    high_mask = has_conv & (cpa >= config.target_cpa * max(config.cpa_multiplier, 0.1))
    for idx in np.nonzero(high_mask)[0]:
        reasons[idx].append("High CPA")

    rule_hit = preset_mask | zero_mask | high_mask
    flagged = rule_hit & (~protected)

    # --- wasted spend ---------------------------------------------------------
    wasted = np.zeros(len(out), dtype=float)
    zero_waste = flagged & (~has_conv)
    wasted[zero_waste] = cost[zero_waste]
    high_waste = flagged & has_conv
    wasted[high_waste] = np.maximum(
        cost[high_waste] - config.target_cpa * conv[high_waste], 0.0
    )

    # --- priority score (0-100 by wasted-spend impact) -----------------------
    priority = np.zeros(len(out), dtype=float)
    if flagged.any():
        max_wasted = float(wasted[flagged].max())
        if max_wasted > 0:
            priority[flagged] = 100.0 * wasted[flagged] / max_wasted

    reason_text = []
    for idx in range(len(out)):
        if flagged[idx]:
            reason_text.append(" + ".join(reasons[idx]) if reasons[idx] else "Flagged")
        elif protected[idx] and rule_hit[idx]:
            reason_text.append("Protected (brand term)")
        else:
            reason_text.append("")

    out["Protected"] = protected
    out["Waste Flag"] = flagged
    out["Waste Reason"] = reason_text
    out["Wasted Spend"] = np.round(wasted, 2)
    out["Priority Score"] = np.round(priority, 1)
    return out


def flag_search_terms(df: pd.DataFrame, config: WasteConfig) -> pd.DataFrame:
    """Row-level waste flags for every raw search term (Tab 3)."""
    return apply_waste_rules(df, config, term_column="Search term")


# ---------------------------------------------------------------------------
# Negative keyword conflict guard (critical differentiator)
# ---------------------------------------------------------------------------
def keyword_blocks_term(negative_keyword: str, match_type: str, term: str) -> bool:
    """Would the negative keyword block the search term under Google Ads
    negative match-type semantics?

    * Exact  : blocks only identical queries.
    * Phrase : blocks queries containing the phrase as a substring.
    * Broad  : blocks queries containing ALL of the negative's words.
    """
    neg = normalize_term(negative_keyword)
    target = normalize_term(term)
    if not neg or not target:
        return False
    if match_type == "Exact":
        return neg == target
    if match_type == "Phrase":
        return neg in target
    if match_type == "Broad":
        return set(neg.split()).issubset(set(target.split()))
    return False


CONFLICT_COLUMNS = (
    "Negative Keyword", "Match Type", "Converting Query", "Campaign",
    "Conversions", "Conv. Value",
)


def find_conflicts(
    keywords: list[str], match_type: str, terms_df: pd.DataFrame
) -> pd.DataFrame:
    """Cross-check staged negatives against every converting search term.

    Returns a warning table listing converting queries (and their
    conversions / revenue) that the staged negatives would block.
    """
    conversions = pd.to_numeric(terms_df.get("Conversions"), errors="coerce").fillna(0.0)
    converting = terms_df[conversions.to_numpy(float) > 0]
    if not keywords or converting.empty:
        return pd.DataFrame(columns=CONFLICT_COLUMNS)

    rows = []
    term_values = converting["Search term"].astype(str).tolist()
    campaign_values = converting.get("Campaign", pd.Series(["All"] * len(converting))).tolist()
    conv_values = pd.to_numeric(converting["Conversions"], errors="coerce").fillna(0.0).tolist()
    value_values = pd.to_numeric(converting.get("Conv. value", 0), errors="coerce").fillna(0.0).tolist()

    for keyword in keywords:
        for i, term in enumerate(term_values):
            if keyword_blocks_term(keyword, match_type, term):
                rows.append(
                    {
                        "Negative Keyword": keyword,
                        "Match Type": match_type,
                        "Converting Query": term,
                        "Campaign": campaign_values[i],
                        "Conversions": conv_values[i],
                        "Conv. Value": value_values[i],
                    }
                )
    return pd.DataFrame(rows, columns=list(CONFLICT_COLUMNS))


# ---------------------------------------------------------------------------
# Optional Gemini BYOK semantic intent audit
# ---------------------------------------------------------------------------
class GeminiAuditError(RuntimeError):
    """User-friendly error raised when the Gemini audit cannot run."""


def run_gemini_audit(
    search_terms: list[str],
    api_key: str,
    model: str = GEMINI_MODEL_DEFAULT,
    batch_size: int = GEMINI_BATCH_SIZE,
    progress=None,
) -> pd.DataFrame:
    """Classify search terms into commercial-intent categories with Gemini.

    Batches terms in chunks of ``batch_size`` (default 50). Returns a
    DataFrame with columns: Search term, AI Intent, Justification.

    Raises:
        GeminiAuditError: missing key, missing package, or API failure —
            always with an actionable message for the UI.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise GeminiAuditError(
            "The google-genai package is not installed. Run "
            "`pip install google-genai` (it is already listed in "
            "requirements.txt on Streamlit Cloud)."
        ) from exc

    if not api_key:
        raise GeminiAuditError("A Gemini API key is required for the AI intent audit.")
    if not search_terms:
        raise GeminiAuditError("No search terms to classify.")

    client = genai.Client(api_key=api_key)
    results: list[dict] = []
    total_batches = math.ceil(len(search_terms) / max(batch_size, 1))

    for batch_no, start in enumerate(range(0, len(search_terms), batch_size), start=1):
        batch = [str(t) for t in search_terms[start : start + batch_size]]
        prompt = _audit_prompt(batch)
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            payload = _parse_gemini_payload(response.text)
        except GeminiAuditError:
            raise
        except Exception as exc:  # network / auth / quota errors
            raise GeminiAuditError(f"Gemini request failed: {exc}") from exc

        by_term = {str(item.get("term", "")).strip().lower(): item for item in payload}
        for term in batch:
            item = by_term.get(term.strip().lower())
            intent = str(item.get("intent", "")).strip() if item else ""
            if intent not in GEMINI_INTENT_CATEGORIES:
                intent = "Informational/Research" if item else ""
            reason = str(item.get("reason", "")).strip() if item else "Not classified"
            results.append(
                {"Search term": term, "AI Intent": intent, "Justification": reason}
            )
        if progress:
            progress(batch_no / total_batches, f"Classified {len(results)} terms...")

    return pd.DataFrame(results, columns=["Search term", "AI Intent", "Justification"])


def _audit_prompt(batch: list[str]) -> str:
    numbered = "\n".join(f"{i + 1}. {term}" for i, term in enumerate(batch))
    categories = "\n".join(f"- {c}" for c in GEMINI_INTENT_CATEGORIES)
    return (
        "You are a senior Google Ads search-intent auditor. Classify each of "
        "the following search terms into exactly ONE category:\n"
        f"{categories}\n\n"
        "Definitions: 'High Commercial Intent' = ready to buy or compare "
        "prices/vendors; 'Informational/Research' = learning, definitions, "
        "how-to, research; 'Competitor' = mentions a competitor brand or "
        "review aggregator; 'Job/Career' = employment intent; 'Irrelevant' "
        "= off-topic for a B2B SaaS CRM / home-services advertiser.\n\n"
        "Return ONLY strict JSON of the form "
        '{"results": [{"term": "<exact term>", "intent": "<category>", '
        '"reason": "<one short sentence>"}]} with one entry per input term.\n\n'
        f"Search terms:\n{numbered}"
    )


def _parse_gemini_payload(text: str) -> list[dict]:
    if not text:
        raise GeminiAuditError("Gemini returned an empty response.")
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", cleaned).strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise GeminiAuditError(
            "Could not parse the Gemini response as JSON. Try again or "
            "switch to a different model."
        ) from exc
    if isinstance(payload, dict):
        payload = payload.get("results", [])
    if not isinstance(payload, list):
        raise GeminiAuditError("Unexpected Gemini response shape.")
    return [item for item in payload if isinstance(item, dict)]
