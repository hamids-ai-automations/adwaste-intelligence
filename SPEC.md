# AdWaste Intelligence: AI Coding Agent Master Prompt & Development Roadmap

**Target Platform:** Streamlit Community Cloud (`streamlit.io`)  
**Product Role:** Full web SaaS companion to the *Google Ads Waste Detector* Chrome extension and a lead-magnet audit tool for paid-ads agencies and PPC clients.

---

## Part 1: Copy-Paste Master Prompt for Your AI Coding Agent

Copy everything inside the prompt section below and paste it as your initial instruction (or save it as `SPEC.md` in your project root and tell your AI agent to follow it phase by phase).

> **System Role & Mission**
>
> Act as a Senior Full-Stack Python/Streamlit Engineer and Performance Marketing Data Scientist. Build **AdWaste Intelligence**, a production-ready, privacy-first Streamlit web application deployed on **Streamlit Community Cloud (`streamlit.io`)**.
>
> **Core Problem Solved:** Paid-search agencies and PPC managers upload Google Ads Search Terms reports (`.csv` or `.xlsx`) to automatically run 1-gram through 4-gram waste analysis, detect irrelevant or underperforming ad spend, prevent negative-keyword conflicts against converting queries, and export ready-to-paste negative keyword lists and client-ready Excel audit reports.
>
> **Portfolio Context:** This app serves as the web SaaS companion to Muhammad Hamid's *Google Ads Waste Detector* Chrome extension and acts as a high-converting lead magnet for paid-ads consulting. All processing must run 100% in-memory per session (zero server-side persistence of client CSVs).

### 1. Technical Stack & Streamlit Cloud Constraints

| Layer | Choice | Engineering Constraint |
| :--- | :--- | :--- |
| **Runtime** | Python 3.11+ | Must deploy cleanly on `streamlit.io` with only `requirements.txt` (no `packages.txt` OS binaries). |
| **UI Framework** | `streamlit>=1.38.0` | Use `st.set_page_config(layout="wide")`, `st.tabs`, `st.data_editor`, and `@st.cache_data` for fast filtering. |
| **Data & Math** | `pandas`, `numpy` | Vectorized aggregations; zero-division safe helpers (`np.where`); never mutate cached DataFrames in place. |
| **Visualizations** | `plotly` | Interactive charts with clean dark/light theme compatibility and formatted currency/percentage hover tooltips. |
| **NLP / N-Grams** | Pure Python (`re`, `collections`) | **Do NOT use `nltk.download()` at runtime.** Bundle a clean English stopword `frozenset` inside `src/constants.py` so Streamlit Cloud never fails on missing corpora. |
| **Excel Export** | `openpyxl` | Generate formatted multi-tab client audit workbooks in-memory via `io.BytesIO`. |
| **Optional AI Layer** | `google-genai` (optional BYOK) | Optional Gemini API semantic intent classifier (user pastes API key or uses `st.secrets`), batched in chunks of 50 terms. App must work 100% offline/free without an API key. |
| **Testing** | `pytest` | Unit tests covering messy Google Ads CSVs, n-gram math, conflict detection, and match-type formatting. |

### 2. Required Project Structure

```text
adwaste-intelligence/
├── app.py                        # Main Streamlit entry point, layout, tabs, session state
├── requirements.txt              # Pinned lightweight dependencies for streamlit.io
├── README.md                     # Portfolio-grade documentation, screenshots, live link
├── .streamlit/
│   └── config.toml               # Clean SaaS theme (primary accent, background, font)
├── src/
│   ├── __init__.py
│   ├── constants.py              # Bundled English stopwords & preset negative intent dictionaries
│   ├── ingestion.py              # Google Ads CSV/XLSX parser, encoding/header/currency cleaner
│   ├── sample_data.py            # Synthetic 1,500-row realistic Google Ads Search Terms generator
│   ├── ngram_engine.py           # Vectorized 1-gram to 4-gram aggregation & waste scoring
│   ├── waste_detector.py         # Rule-based waste flagging, conflict checker & optional Gemini audit
│   ├── exporter.py               # Google Ads Editor CSV, copy-paste formatter & Excel audit builder
│   └── ui_components.py          # Reusable KPI cards, Plotly charts, CTA/lead-magnet banners
└── tests/
    ├── test_ingestion.py
    ├── test_ngram_engine.py
    └── test_exporter.py
```

### 3. Functional Requirements & Exact Business Logic

#### Module A: Bulletproof Google Ads Data Ingestion (`src/ingestion.py`)
Google Ads Search Terms exports have notorious formatting quirks. Your parser must automatically handle:
1. **Metadata Header Skipping:** Standard Google Ads CSVs include 2 leading metadata rows (e.g., `Search terms report` and `Oct 1, 2026 - Oct 31, 2026`) before the real column header row. Automatically scan the first 10 lines to find the header row containing `Search term` (case-insensitive).
2. **Summary / Total Row Removal:** Automatically strip trailing `Total: Search terms`, `Total: Account`, or `Total: Filtered` rows so spend is never double-counted.
3. **Encoding & Delimiter Resilience:** Auto-detect UTF-8, UTF-8-SIG (BOM), UTF-16 (common in Google Ads Editor exports), and Latin-1, plus comma or tab delimiters.
4. **Numeric & Currency Sanitization:** Strip currency symbols (`$`, `€`, `£`, `AED`, `PKR`, `INR`, `CA$`, `A$`), thousands commas, and percentage signs (`%`); coerce Google Ads placeholders (`--`, `< 10%`, `N/A`) safely to `0.0`. Detect and store the currency symbol for UI formatting.
5. **Flexible Column Auto-Mapping + Fallback UI:** Map standard and variant column names automatically:
   - `Search term` (required)
   - `Cost` / `Spend` (required)
   - `Clicks` (required)
   - `Impr.` / `Impressions` (optional, default `0`)
   - `Conversions` / `Conv.` (required)
   - `Conv. value` / `Conversion value` (optional, default `0.0`)
   - `Campaign`, `Ad group`, `Match type`, `Added/Excluded` (optional, default `"All"`)
   - If any required column is missing, render a clean column-mapping selectbox UI before running analysis.
6. **One-Click Demo Mode (`src/sample_data.py`):** Provide a prominent **"Load Demo Account (1,500 Search Terms)"** button on the landing state using a deterministic synthetic dataset (e.g., a B2B SaaS / Home Services account with $25k–$40k spend, realistic converting queries, and deliberate waste clusters like `free`, `jobs`, `salary`, `login`, `diy`, `pdf`, and competitor names) so visitors can experience full value in 2 seconds without uploading a file.

#### Module B: Configurable Waste Controls (Sidebar)
Expose clean, reactive controls in `st.sidebar`:
- **Target CPA** (auto-initialized to account average CPA, editable by user) and **CPA Bleeder Multiplier** (default `2.0x` Target CPA).
- **Zero-Conversion Spend Threshold** (default: `1.0x` Target CPA or `$50` if no conversions exist).
- **Minimum Clicks Threshold** (default `3` clicks) to avoid prematurely flagging 1-click noise.
- **Brand & Protected Terms Whitelist** (comma-separated text input; any search term or n-gram containing these tokens is protected from automatic waste flagging).
- **Stopwords Toggle** (default `On`: excludes common stopwords from 1-grams while preserving them inside 2–4 gram phrases where they carry intent, e.g., `"how to"`, `"near me"`, `"for free"`).
- **Preset Waste Dictionaries (Multi-Select):**
  - *Job Seekers:* `job`, `jobs`, `career`, `careers`, `salary`, `hiring`, `internship`, `resume`, `glassdoor`, `indeed`
  - *Free / Cheap / Piracy:* `free`, `cheap`, `torrent`, `crack`, `nulled`, `open source`, `discount code`, `coupon`
  - *DIY / Academic / Info:* `diy`, `tutorial`, `pdf`, `definition`, `wikipedia`, `youtube`, `template`, `reddit`, `course`
  - *Existing Customer / Support:* `login`, `sign in`, `customer service`, `support number`, `cancel`, `refund`

#### Module C: Vectorized N-Gram Engine (`src/ngram_engine.py`)
1. Normalize each search term (lowercase, strip punctuation except hyphens/apostrophes inside words, collapse whitespace).
2. Generate unique n-grams per search term for `n ∈ {1, 2, 3, 4}` (deduplicate repeated tokens within the same single search term so a query's spend is never double-counted inside the same n-gram).
3. Aggregate per n-gram:
   - `Query Count` (number of unique search terms containing the n-gram)
   - `Impressions`, `Clicks`, `Cost`, `Conversions`, `Conv. Value`
   - Derived metrics: `CTR (%)`, `Avg. CPC`, `Conv. Rate (%)`, `CPA`, `ROAS`
   - **Waste Flag & Wasted Spend ($):** Flag an n-gram if:
     - `Conversions == 0` AND `Cost >= Zero-Conversion Spend Threshold` AND `Clicks >= Min Clicks`, OR
     - `Conversions > 0` AND `CPA >= Target CPA * CPA Multiplier`, OR
     - Matches an enabled Preset Waste Dictionary with `Conversions == 0`.
   - **Efficiency / Waste Priority Score (0–100):** Rank flagged n-grams by wasted spend impact so the biggest budget leaks appear at the top.

#### Module D: Four-Tab Executive Interface (`app.py` & `src/ui_components.py`)
1. **Tab 1 — Executive Waste Overview:**
   - 5 KPI Metric Cards: **Total Spend Analyzed**, **Flagged Wasted Spend ($ & % of Spend)**, **Projected Annualized Savings** (based on uploaded date range or 30-day default), **Wasted Search Terms**, and **Wasted N-Grams**.
   - **Chart 1:** Spend Allocation Donut/Bar (Converting Spend vs. Non-Converting Flagged Waste vs. Low-Volume Unproven Spend).
   - **Chart 2:** Top 15 Wasted N-Grams by Wasted Spend (horizontal Plotly bar chart, color-coded by CPA/Zero-Conv).
   - **Chart 3:** Campaign-Level Waste Breakdown (grouped bar chart showing Total Spend vs. Wasted Spend per Campaign).
2. **Tab 2 — N-Gram Intelligence Explorer:**
   - Radio selector for `1-Gram`, `2-Gram`, `3-Gram`, `4-Gram`.
   - Filters for Campaign, Match Type, "Show Flagged Waste Only" toggle, Min Spend, and text search.
   - Interactive `st.data_editor` with a leading `Add to Negatives` checkbox column (pre-checked for high-confidence waste, user-editable).
   - **N-Gram Drill-Down Panel:** Select any n-gram to inspect every underlying raw search term that triggered it, along with its exact clicks, cost, and conversions.
3. **Tab 3 — Search Term Auditor & Optional AI Intent Classifier:**
   - Row-level table of flagged search terms with explicit `Waste Reason` badges (`Zero-Conv Bleeder`, `High CPA`, `Job Intent`, `Free/DIY Intent`) and `Add to Negatives` checkboxes.
   - **Optional AI Intent Audit (Expander/Action):** If the user supplies a Gemini API key (or `GEMINI_API_KEY` is configured in `st.secrets`), allow running an AI semantic audit on the top 100 highest-spend non-converting search terms, classifying each into `High Commercial Intent`, `Informational/Research`, `Competitor`, `Job/Career`, or `Irrelevant` with a 1-sentence justification.
4. **Tab 4 — Negative Keyword Builder, Conflict Guard & Exports:**
   - Consolidates all selected n-grams (from Tab 2) and exact search terms (from Tab 3) into a unified Negative Keyword Staging List.
   - **Negative Keyword Conflict Checker (Critical Differentiator):** Cross-checks every staged negative keyword (respecting chosen match type: Exact vs. Phrase vs. Broad) against all **converting search terms** (`Conversions > 0`) in the dataset. Displays a clear warning table showing any converting queries and total revenue/conversions that would be blocked, with a 1-click **"Remove Conflicting Negatives"** button.
   - **Match-Type & Level Selector:** Format staged list as `[Exact]`, `"Phrase"`, or `Broad`, and assign target level (`Account Negative List`, `Campaign`, or `Ad Group`).
   - **3 Export Channels:**
     1. **Copy-Paste Block (`st.code`):** Instant copy button for pasting straight into Google Ads Negative Keyword Lists.
     2. **Google Ads Editor CSV Download:** Properly formatted columns (`Campaign`, `Ad group`, `Keyword`, `Criterion Type`) ready for bulk import into Google Ads Editor.
     3. **Client Audit Excel Report (`.xlsx`):** Branded multi-tab workbook (`Executive Summary`, `Top Wasted N-Grams`, `Flagged Search Terms`, `Approved Negative List`) with formatted headers, currency formats, and auto-adjusted column widths.

#### Module E: Lead-Magnet & Portfolio Integration
- **Privacy Trust Strip:** Subtle badge near the file uploader: *"100% In-Memory Processing — Your client CSV data is never saved or logged."*
- **Chrome Extension Companion Callout:** Sidebar card linking back to the *Google Ads Waste Detector* Chrome extension (configure URL via `CHROME_EXTENSION_URL` constant/env var with a clean placeholder until live).
- **High-Converting Agency CTA:** Non-intrusive banner in the sidebar and Tab 4 export footer: *"Found wasted spend? Book a free 15-minute Google Ads Account Waste Audit with Muhammad Hamid"* linking directly to WhatsApp (`https://wa.me/923167417135`) and GitHub (`https://github.com/hamids-ai-automations`).

### 4. Agent Execution Rules
- Work **strictly phase-by-phase** following the roadmap below. Do not dump all code into a single giant `app.py`.
- After completing each phase, run `pytest` (and `streamlit run app.py` smoke check) and verify zero syntax, import, or runtime errors before advancing.
- Never hardcode API keys or secrets in source files; use `st.secrets` or runtime `st.text_input(..., type="password")`.

---

## Part 2: Phased Development Roadmap

| Phase | Milestone | Key Files Created / Updated | Definition of Done (Verification Gate) |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Project Scaffolding & Theme** | `app.py`, `requirements.txt`, `.streamlit/config.toml`, `src/__init__.py`, `src/constants.py` | Repo structure created; `streamlit run app.py` boots cleanly with branded header, wide layout, and empty 4-tab shell. |
| **Phase 2** | **Ingestion Engine & Demo Data** | `src/ingestion.py`, `src/sample_data.py`, `tests/test_ingestion.py` | Parser cleanly loads messy Google Ads CSVs (2-row headers, `Total:` rows, UTF-16, `$`/`AED`/`€` currencies, `--` values); Demo button loads 1,500 realistic rows; `pytest tests/test_ingestion.py` passes. |
| **Phase 3** | **N-Gram Engine & Waste Rules** | `src/ngram_engine.py`, `src/waste_detector.py`, `tests/test_ngram_engine.py` | 1–4 gram metrics match manual sums with zero double-counting; brand whitelist protects brand terms; preset waste dictionaries tag accurately; `pytest` passes. |
| **Phase 4** | **Executive Dashboard & Explorer UI** | `src/ui_components.py`, `app.py` (Tabs 1, 2, 3) | All 5 KPI cards, 3 Plotly charts, sidebar thresholds, `st.data_editor` selection checkboxes, and n-gram raw-query drill-down work smoothly under `@st.cache_data`. |
| **Phase 5** | **Conflict Guard & Export Suite** | `src/exporter.py`, `src/waste_detector.py`, `app.py` (Tab 4), `tests/test_exporter.py` | Conflict checker accurately catches negatives that block converting queries; Copy-Paste block, Google Ads Editor CSV, and multi-tab `.xlsx` workbook download and open cleanly. |
| **Phase 6** | **Optional AI Intent Layer & Lead-Magnet Polish** | `src/waste_detector.py`, `src/ui_components.py`, `app.py` | Optional Gemini BYOK semantic classifier handles batches cleanly with graceful error handling; privacy badge, Chrome extension card, and WhatsApp CTA (`https://wa.me/923167417135`) render cleanly. |
| **Phase 7** | **Performance QA & `streamlit.io` Deployment** | `README.md`, full `tests/` suite, GitHub push | 50,000-row stress test completes in < 3 seconds; full `pytest` suite passes; repo pushed to `@hamids-ai-automations` and deployed live on Streamlit Community Cloud. |

---

## Part 3: Turn-by-Turn Prompts to Steer Your AI Agent

Use these short follow-up prompts one at a time after pasting the Master Prompt so your coding agent stays disciplined and testable:

1. **Kickoff (Phase 1):**  
   `Start with Phase 1 only. Scaffold the directory structure, requirements.txt, .streamlit/config.toml, src/constants.py (with bundled English stopwords and preset PPC waste dictionaries), and a minimal app.py shell. Verify imports and show me the file tree.`

2. **Data Pipeline (Phase 2):**  
   `Proceed to Phase 2. Build src/ingestion.py to handle raw Google Ads Search Terms CSV/XLSX exports (metadata header skipping, Total-row stripping, encoding/currency cleaning, column mapping fallback) and src/sample_data.py with a 1,500-row realistic demo dataset. Write and run tests/test_ingestion.py.`

3. **Core Analytics (Phase 3):**  
   `Proceed to Phase 3. Implement vectorized 1-gram to 4-gram analysis in src/ngram_engine.py and the configurable waste-flagging + converting-query conflict checker in src/waste_detector.py. Ensure zero double-counting of spend per query and protect brand whitelist terms. Write and run tests/test_ngram_engine.py.`

4. **Frontend & Visuals (Phase 4):**  
   `Proceed to Phase 4. Build src/ui_components.py and wire Tabs 1, 2, and 3 in app.py with @st.cache_data, sidebar rule controls, 5 KPI cards, 3 Plotly charts, interactive st.data_editor checkboxes, and an n-gram drill-down expander. Confirm the app launches cleanly with Demo Mode.`

5. **Exports & Safety Guard (Phase 5):**  
   `Proceed to Phase 5. Build src/exporter.py and wire Tab 4 (Negative Keyword Builder). Include the Converting-Query Conflict Checker with a one-click removal button, copy-paste negative list, Google Ads Editor CSV export, and formatted multi-tab .xlsx client report. Run tests/test_exporter.py.`

6. **AI Layer & Conversion Flows (Phase 6):**  
   `Proceed to Phase 6. Add the optional Gemini BYOK semantic intent classifier (batched, gracefully hidden/disabled when no key is provided) plus the Privacy Trust badge, Chrome Extension companion card, and WhatsApp audit CTA banner.`

7. **Stress Test & Deployment Prep (Phase 7):**  
   `Proceed to Phase 7. Run a 50,000-row benchmark test to confirm parsing + n-gram analysis stays under 3 seconds, run the full pytest suite, and write a portfolio-grade README.md with Streamlit Community Cloud deployment steps.`

---

## Part 4: Portfolio & Lead-Magnet Launch Checklist

- **Bridge From Chrome Extension to Web App:** Inside your *Google Ads Waste Detector* Chrome extension popup, add a button labeled **"Run Deep N-Gram Audit & Export Excel"** pointing to your live `adwaste-intelligence.streamlit.app/?utm_source=chrome_ext` URL.
- **Zero-Friction First Impression:** Make the **"Load Demo Account"** button immediately visible above the fold so recruiters, agency founders, and LinkedIn visitors see interactive waste charts within 5 seconds without hunting for a CSV.
- **GitHub Portfolio Polish (`@hamids-ai-automations`):** Include a 20-second screen recording GIF of uploading a CSV → flagging wasted n-grams → running the conflict checker → exporting a negative keyword list right at the top of `README.md`.
- **Client Lead-Gen Hook:** Share a short LinkedIn post showing a real (anonymized) demo audit uncovering 18–25% wasted spend in under 60 seconds, with the live Streamlit app link in the post and your WhatsApp audit CTA inside the app.
