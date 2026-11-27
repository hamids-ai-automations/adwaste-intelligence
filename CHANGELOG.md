# Changelog

All notable changes to **AdWaste Intelligence** are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-11-27

### Added
- Project tooling configuration (`pyproject.toml`, `requirements-dev.txt`, `.gitattributes`).
- GitHub repository standards: `.github/workflows/ci.yml` (Python 3.11 & 3.12 lint, pytest coverage, AppTest smoke check, pip-audit, gitleaks, and committed-secrets guard), `.github/dependabot.yml`, `.github/CODEOWNERS`, issue templates, and PR template.
- Community & engineering documentation: `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `docs/ARCHITECTURE.md`, `DEPLOYMENT_STATUS.md`, and `.streamlit/secrets.toml.example`.
- Headless Streamlit `AppTest` smoke check (`scripts/smoke_pages.py`) and additional unit/integration tests (`tests/test_waste_and_ui.py`).
- Real application screenshots in `assets/screenshots/` embedded in `README.md`.

### Changed
- Migrated deprecated `use_container_width=True` widget calls in `app.py` to `width="stretch"` (`streamlit>=1.67,<2.0`).
- Resolved `GEMINI_API_KEY` and `CHROME_EXTENSION_URL` consistently in `os.environ` → `st.secrets` order without bare `Exception` catches.
- Cleared `staging_editor` widget state when staging new negatives or removing conflicting keywords so row indices never misalign.
- Formatted integer columns cleanly in Excel audit workbooks (`src/exporter.py`).
- Resolved all 24 `ruff` lint findings across `app.py`, `src/`, and `tests/`.

## [1.0.0] - 2026-11-26

### Added
- Initial release of **AdWaste Intelligence** (`app.py`, 8 `src/` modules, 35 unit/performance tests).
- Bulletproof Google Ads CSV/XLSX ingestion (2-row metadata headers, `Total:` row stripping, UTF-16/UTF-8-SIG/Latin-1, multi-currency parsing, manual column-mapping fallback).
- Deterministic 1,500-row demo dataset (`src/sample_data.py`).
- Vectorized 1–4 gram aggregation engine (`src/ngram_engine.py`) with zero intra-query double-counting.
- Rule-based waste detector, brand whitelist protection, converting-query conflict guard, and optional BYOK Gemini AI intent audit (`src/waste_detector.py`).
- Copy-paste negative list, Google Ads Editor CSV, and multi-tab Excel audit workbook exporters (`src/exporter.py`).
