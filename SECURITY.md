# Security Policy

## Privacy & Data-Handling Guarantees

**AdWaste Intelligence** is engineered as a privacy-first, stateless application:

- **100% In-Memory Processing:** Uploaded Google Ads Search Terms reports (`.csv` / `.xlsx`) are parsed and analyzed inside browser session memory (`st.session_state`) and are never written to disk, logged, or stored in a database.
- **BYOK AI Isolation:** The optional Gemini semantic intent audit runs strictly when an API key is provided via environment variable, `st.secrets`, or password-masked runtime input. Keys are kept in memory only, never persisted, and never rendered in exports or logs. Only search-term strings (up to the top 100 non-converting candidates) are sent to Gemini when the user explicitly clicks **Run AI Intent Audit**.
- **Safe File Ingestion:** Uploaded files are processed strictly as tabular data (`csv.reader` / `openpyxl` via `pandas.read_excel`); no uploaded file content is evaluated or executed.

## Supported Versions

| Version | Supported |
|---|---|
| `1.1.x` (current `main`) | Yes |
| `< 1.1.0` | Upgrade to latest `main` |

## Reporting a Vulnerability

If you discover a security vulnerability (for example, secret leakage, unsafe deserialization, formula injection in exports, or dependency vulnerabilities), please **do not open a public issue**.

Instead, report it privately via:

- **GitHub Security Advisories:** Use the **Security → Advisories → Report a vulnerability** workflow on `hamids-ai-automations/adwaste-intelligence`.
- **Direct Contact:** Reach out to Muhammad Hamid via GitHub (`@hamids-ai-automations`) with reproduction steps and impact assessment.

Reports are reviewed promptly and patched in a coordinated release.
