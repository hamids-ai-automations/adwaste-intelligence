# DEPLOYMENT STATUS — AdWaste Intelligence

**Version:** 1.1.0 · **Assessed:** 2026-11-27

Summary: **Repository hardened, tested, and published to GitHub with automated CI; Streamlit Community Cloud hosting requires interactive OAuth sign-in at `share.streamlit.io`.**

---

## 1. Status Board

| Dimension | Status | Detail |
|---|---|---|
| Local Streamlit server | ✅ Verified | `streamlit run app.py` served `/_stcore/health` (`200 OK`); all 5 UI states captured cleanly |
| Static lint (`ruff`) | ✅ Passing | `ruff check .` passes with zero errors (`pyproject.toml` configured for `py311+`) |
| Automated test suite (`pytest`) | ✅ Passing | `pytest --cov=src` passes all tests including 50k-row performance benchmark and AppTest flow |
| Headless UI smoke (`AppTest`) | ✅ Passing | `python scripts/smoke_pages.py` verifies landing, Demo Account load, 4 tabs, and negative staging |
| Secrets & privacy posture | ✅ Hardened | `.streamlit/secrets.toml` git-ignored; `.streamlit/secrets.toml.example` provided; 100% in-memory processing |
| GitHub repository | ✅ Published | `https://github.com/hamids-ai-automations/adwaste-intelligence` (public, MIT, topics & templates configured) |
| GitHub Actions CI | ✅ Configured | `.github/workflows/ci.yml` runs Python 3.11 & 3.12 lint, pytest coverage, AppTest smoke, `pip-audit`, `gitleaks`, and secrets guard |
| Screenshots in README | ✅ Captured | 5 real Chromium screenshots stored under `assets/screenshots/` and embedded in `README.md` |
| Hosted instance (Streamlit Cloud) | ⏳ Pending manual link | Target URL `https://adwaste-intelligence.streamlit.app` awaits interactive GitHub OAuth app creation at `share.streamlit.io` |

---

## 2. Environment Matrix

| Item | Value |
|---|---|
| Target Python | `3.11+` (verified locally on `3.12.10`; CI matrix runs `3.11` and `3.12`) |
| Runtime packages | `streamlit>=1.67,<2.0`, `pandas>=2.2,<4.0`, `numpy>=1.26,<3.0`, `plotly>=5.18,<8.0`, `openpyxl>=3.1.2,<4.0`, `google-genai>=1.0,<4.0` |
| OS packages (`packages.txt`) | None required (pure Python + bundled `STOPWORDS`) |
| Dev/CI packages | `pytest>=8.0`, `pytest-cov>=5.0`, `ruff>=0.6` |
| Streamlit config | `.streamlit/config.toml` — light theme (`#059669` primary), `maxUploadSize = 100`, `gatherUsageStats = false` |

---

## 3. Streamlit Community Cloud Deployment Runbook

1. Visit [share.streamlit.io](https://share.streamlit.io) and sign in with `@hamids-ai-automations`.
2. Select **Create app** → **Deploy a public app from GitHub**.
3. Configure:
   - **Repository:** `hamids-ai-automations/adwaste-intelligence`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL (optional):** `adwaste-intelligence`
   - **Python version:** `3.12` (or `3.11`)
4. Optional — in **Advanced settings → Secrets**, add:
   ```toml
   GEMINI_API_KEY = "your-key"
   CHROME_EXTENSION_URL = "https://chromewebstore.google.com/..."
   ```
5. Click **Deploy**, wait for build completion, and verify:
   - `https://adwaste-intelligence.streamlit.app/_stcore/health` returns `ok`
   - Clicking **Load Demo Account (1,500 Search Terms)** renders `$37,297.43` spend and 4 interactive tabs
   - Tab 4 exports Copy-Paste Block, Google Ads Editor CSV, and `.xlsx` Client Audit Report cleanly.
