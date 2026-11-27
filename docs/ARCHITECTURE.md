# Architecture — AdWaste Intelligence

**Version:** 1.1.0 · **Maintainer:** Muhammad Hamid (`@hamids-ai-automations`)

---

## 1. Design Principles

1. **100% In-Memory & Stateless:** Client Search Terms exports are parsed from uploaded bytes (`io.BytesIO` / `io.StringIO`) and kept solely inside Streamlit's per-session `st.session_state`. No files, database rows, or API keys are written to server disk.
2. **Streamlit-Free Core Modules:** All parsing, n-gram math, waste scoring, conflict checking, and exporting live under `src/` with zero dependency on `streamlit` (except UI helpers in `src/ui_components.py`), keeping the core engine fast and directly unit-testable.
3. **Zero External Corpora:** English stopwords (`STOPWORDS`) and preset PPC negative dictionaries (`PRESET_WASTE_DICTIONARIES`) ship inside `src/constants.py`, avoiding runtime `nltk.download()` failures on Streamlit Community Cloud.
4. **Offline-First with Optional BYOK AI:** The core 1–4 gram waste engine, conflict guard, and all 3 export channels work with zero API keys. Gemini intent classification (`google-genai`) is strictly optional and Bring-Your-Own-Key.

---

## 2. Module Map

```text
adwaste-intelligence/
├── app.py                      # Entry point: page config, sidebar controls, 4-tab UI, session state
├── src/
│   ├── constants.py            # Branding config, default thresholds, STOPWORDS, preset dictionaries
│   ├── ingestion.py            # CSV/XLSX parser, encoding/delimiter detection, currency/placeholder cleaner
│   ├── sample_data.py          # Deterministic 1,500-row B2B SaaS + Home Services demo account
│   ├── ngram_engine.py         # Vectorized 1-4 gram normalization, deduplication, groupby roll-ups
│   ├── waste_detector.py       # WasteConfig, rule engine, conflict guard, optional Gemini BYOK audit
│   ├── exporter.py             # Copy-paste negative block, Google Ads Editor CSV, Excel workbook builder
│   └── ui_components.py        # CSS tokens, KaTeX-safe KPI cards, Plotly charts, CTA/privacy banners
├── scripts/
│   └── smoke_pages.py          # Headless AppTest boot + demo + staging verification
└── tests/
    ├── test_ingestion.py       # Metadata headers, Total rows, UTF-16, currencies, column mapping, XLSX
    ├── test_ngram_engine.py    # Normalization, intra-query dedup, stopwords, waste rules, conflicts, 50k stress
    ├── test_exporter.py        # Match formatting, copy-paste block, Editor CSV, multi-tab Excel workbook
    └── test_waste_and_ui.py    # Mocked Gemini audit, UI helpers/charts, AppTest end-to-end check
```

---

## 3. Data Flow

```text
CSV / XLSX bytes (or generate_sample_data())
   │
   ▼  src.ingestion.load_report()
      ├─ Auto-detect encoding (UTF-16 / UTF-8-SIG / Latin-1) & delimiter (, / \t / ;)
      ├─ Scan first 10 rows for "Search term" header; extract date range -> days
      ├─ Strip trailing "Total: ..." summary rows & sanitize currencies / placeholders
      └─ Canonical DataFrame (or MissingColumnsError -> manual column-mapping UI)
   │
   ▼  src.ngram_engine.build_ngram_table(df, n ∈ {1,2,3,4})
      ├─ Normalize text & extract unique n-grams per search term (zero double-counting)
      ├─ Exclude STOPWORDS from 1-grams only (preserved in 2-4 gram phrases)
      └─ Groupby sum + zero-division safe CTR / CPC / Conv. Rate / CPA / ROAS
   │
   ▼  src.waste_detector.apply_waste_rules(table, WasteConfig)
      ├─ Brand whitelist word-boundary protection (Protected == True -> never flagged)
      ├─ Rule 1: Zero-Conv Bleeder (Conv == 0 & Cost >= threshold & Clicks >= min_clicks)
      ├─ Rule 2: High CPA (Conv > 0 & CPA >= Target CPA * multiplier)
      ├─ Rule 3: Preset Intent Dictionary match (Conv == 0)
      └─ Wasted Spend ($) + Priority Score (0-100 scaled by wasted spend)
   │
   ▼  Tab 2 & Tab 3 Checkbox Staging ──► st.session_state["staged_negatives"]
   │
   ▼  src.waste_detector.find_conflicts(keywords, match_type, df)
      ├─ Exact:  normalized negative == normalized converting query
      ├─ Phrase: normalized negative in normalized converting query
      └─ Broad:  all negative tokens ⊆ converting query tokens
   │
   ▼  src.exporter
      ├─ Copy-Paste Block (st.code)
      ├─ Google Ads Editor CSV (Campaign, Ad group, Keyword, Criterion Type)
      └─ Multi-tab Excel Audit Workbook (.xlsx via io.BytesIO)
```

---

## 4. Secret Resolution & Privacy Controls

1. `GEMINI_API_KEY` and `CHROME_EXTENSION_URL` resolve in order: `os.environ` → `st.secrets` → empty string.
2. `.streamlit/secrets.toml` is excluded in `.gitignore` and guarded in `.github/workflows/ci.yml`.
3. `ui_components._escape_math()` escapes `$` as `&#36;` inside HTML KPI blocks so Streamlit's Markdown/KaTeX renderer never treats two currency amounts in one grid as LaTeX math delimiters.
