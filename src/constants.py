"""Shared constants: bundled stopwords, preset waste dictionaries, branding config.

Everything ships inside the app (no nltk.download / external corpora) so a
Streamlit Community Cloud deployment can never fail on missing data.
"""

import os

# ---------------------------------------------------------------------------
# Branding / lead-magnet configuration
# ---------------------------------------------------------------------------
APP_NAME = "AdWaste Intelligence"
APP_TAGLINE = "Google Ads Waste Detector — N-Gram Audit Engine"
APP_VERSION = "1.1.0"
AUTHOR_NAME = "Muhammad Hamid"
WHATSAPP_URL = "https://wa.me/923167417135"
GITHUB_URL = "https://github.com/hamids-ai-automations"
# Configure the live Chrome Web Store URL here (or via the CHROME_EXTENSION_URL
# env var / Streamlit secret). Empty string renders a "coming soon" placeholder.
CHROME_EXTENSION_URL = os.environ.get("CHROME_EXTENSION_URL", "")

# ---------------------------------------------------------------------------
# Default waste-detection thresholds
# ---------------------------------------------------------------------------
DEFAULT_CPA_MULTIPLIER = 2.0
DEFAULT_MIN_CLICKS = 3
DEFAULT_ZERO_CONV_FALLBACK = 50.0  # used when the account has zero conversions
DEFAULT_DAYS = 30  # assumed reporting window when the file has no date range
DEFAULT_EDITOR_ROW_CAP = 1000  # max rows rendered inside st.data_editor

# ---------------------------------------------------------------------------
# Bundled English stopwords
# Excluded from 1-grams only; they are preserved inside 2-4 gram phrases where
# they carry intent (e.g. "how to", "near me", "for free").
# Deliberately excludes PPC-intent words such as free / cheap / near / jobs.
# ---------------------------------------------------------------------------
STOPWORDS = frozenset(
    {
        "a", "about", "above", "after", "again", "against", "all", "am", "an",
        "and", "any", "are", "as", "at", "be", "because", "been", "before",
        "being", "below", "between", "both", "but", "by", "can", "could",
        "did", "do", "does", "doing", "down", "during", "each", "few", "for",
        "from", "further", "had", "has", "have", "having", "he", "her", "here",
        "hers", "herself", "him", "himself", "his", "how", "i", "if", "in",
        "into", "is", "it", "its", "itself", "just", "ll", "me", "more",
        "most", "my", "myself", "now", "of", "off", "on", "once", "only", "or",
        "other", "our", "ours", "ourselves", "out", "over", "own", "re", "s",
        "same", "she", "should", "so", "some", "such", "t", "than", "that",
        "the", "their", "theirs", "them", "themselves", "then", "there",
        "these", "they", "this", "those", "through", "to", "too", "under",
        "until", "up", "ve", "very", "was", "we", "were", "what", "when",
        "where", "which", "while", "who", "whom", "why", "will", "with", "you",
        "your", "yours", "yourself", "yourselves",
    }
)

# ---------------------------------------------------------------------------
# Preset negative-intent dictionaries (multi-select in the sidebar)
# ---------------------------------------------------------------------------
PRESET_WASTE_DICTIONARIES = {
    "Job Seekers": (
        "job", "jobs", "career", "careers", "salary", "hiring", "internship",
        "resume", "glassdoor", "indeed",
    ),
    "Free / Cheap / Piracy": (
        "free", "cheap", "torrent", "crack", "nulled", "open source",
        "discount code", "coupon",
    ),
    "DIY / Academic / Info": (
        "diy", "tutorial", "pdf", "definition", "wikipedia", "youtube",
        "template", "reddit", "course",
    ),
    "Existing Customer / Support": (
        "login", "sign in", "customer service", "support number", "cancel",
        "refund",
    ),
}

# Human-readable waste-reason badge labels for each preset dictionary
PRESET_REASON_LABELS = {
    "Job Seekers": "Job Intent",
    "Free / Cheap / Piracy": "Free/Cheap Intent",
    "DIY / Academic / Info": "Free/DIY Intent",
    "Existing Customer / Support": "Support Intent",
}

# ---------------------------------------------------------------------------
# Currency handling for messy Google Ads exports
# Longest tokens first so "CA$" is consumed before "$".
# ---------------------------------------------------------------------------
CURRENCY_TOKENS = (
    "CA$", "US$", "A$", "AED", "PKR", "INR", "USD", "EUR", "GBP", "SAR",
    "Rs", "$", "€", "£", "¥", "₹",
)

# Google Ads placeholder values that must coerce safely to 0.0
NUMERIC_PLACEHOLDERS = frozenset(
    {"--", "-", "–", "—", "n/a", "na", "nan", "none", "<10%", "< 10%", "<1", "< 1"}
)

# ---------------------------------------------------------------------------
# Canonical schema of the cleaned search-terms DataFrame
# ---------------------------------------------------------------------------
CANONICAL_COLUMNS = (
    "Search term", "Cost", "Clicks", "Impr.", "Conversions", "Conv. value",
    "Campaign", "Ad group", "Match type", "Added/Excluded",
)
REQUIRED_COLUMNS = ("Search term", "Cost", "Clicks", "Conversions")
NUMERIC_COLUMNS = ("Cost", "Clicks", "Impr.", "Conversions", "Conv. value")

# ---------------------------------------------------------------------------
# Optional Gemini AI intent-audit layer (BYOK)
# ---------------------------------------------------------------------------
GEMINI_MODEL_DEFAULT = "gemini-2.5-flash"
GEMINI_MODELS = ("gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash")
GEMINI_BATCH_SIZE = 50
GEMINI_INTENT_CATEGORIES = (
    "High Commercial Intent",
    "Informational/Research",
    "Competitor",
    "Job/Career",
    "Irrelevant",
)
