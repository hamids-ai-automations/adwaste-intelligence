# Contributing to AdWaste Intelligence

Contributions, bug reports, parser edge-case fixtures, and feature improvements are welcome.

## Local Development Setup

Requirements: **Python 3.11+**

```bash
git clone https://github.com/hamids-ai-automations/adwaste-intelligence.git
cd adwaste-intelligence

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements-dev.txt
```

## Quality Gates

Every pull request must pass the same checks enforced by `.github/workflows/ci.yml`:

```bash
ruff check .
pytest --cov=src --cov-report=term-missing
python scripts/smoke_pages.py
```

## Engineering Guidelines

1. **Keep business logic Streamlit-free:** Modules under `src/` (`ingestion.py`, `ngram_engine.py`, `waste_detector.py`, `exporter.py`, `sample_data.py`) must remain importable and testable without running Streamlit.
2. **Zero double-counting invariant:** Within any single search term, repeated tokens must contribute each unique n-gram at most once.
3. **Zero server-side persistence:** Never write uploaded client CSV/XLSX data, search terms, or API keys to disk or logs.
4. **Never commit secrets:** Keep credentials out of Git; copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` locally (already git-ignored).
5. **Add regression tests:** New parser variants, waste rules, or export fixes must include tests under `tests/`.
