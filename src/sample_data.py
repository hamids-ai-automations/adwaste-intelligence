"""Synthetic demo account: 1,500 realistic Google Ads search terms.

A deterministic (seeded) B2B SaaS + Home Services hybrid account with
roughly $25k-$40k of spend, realistic converting queries, and deliberate
waste clusters (job seekers, free/cheap/piracy, DIY/academic info, support
and competitor queries) so visitors can experience the full value of the
app in two seconds without uploading a file.

The demo brand is "flowtrack" — it is pre-filled into the Brand &
Protected Terms whitelist so the conflict-guard demo works out of the box.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEMO_ROWS = 1500
DEMO_DATE_RANGE = "Oct 1, 2025 - Oct 31, 2025"
DEMO_DAYS = 31
DEMO_CURRENCY = "$"
DEMO_BRAND_TERMS = "flowtrack"

# ---------------------------------------------------------------------------
# Template pools
# ---------------------------------------------------------------------------
BRAND_TEMPLATES = [
    "flowtrack", "flowtrack crm", "flowtrack pricing", "flowtrack cost",
    "flowtrack demo", "flowtrack reviews", "flowtrack login",
    "flowtrack sign in", "flowtrack support", "flowtrack customer service",
    "flowtrack app", "flowtrack dashboard", "flowtrack account",
    "flowtrack help", "flowtrack contact number", "flowtrack crm pricing",
    "flowtrack crm demo", "flowtrack sales software", "flowtrack status",
    "flowtrack vs hubspot",
]

SAAS_HIGH_INTENT = [
    "crm software", "crm system", "best crm software", "crm for small business",
    "crm pricing", "crm cost per user", "crm for agencies",
    "crm for real estate agents", "crm for recruitment agencies",
    "crm with whatsapp integration", "crm with outlook integration",
    "lead management software", "sales pipeline software",
    "lead tracking software", "crm for sales teams",
    "contact management software", "crm with email automation",
    "crm for consulting firms", "crm for ecommerce", "best crm for startups",
    "crm for solopreneurs", "crm quote management", "crm for law firms",
    "crm for clinics",
]

SAAS_LONG_TAIL = [
    "crm for solo consultants", "crm google workspace integration",
    "crm lead scoring tools", "crm pipeline management features",
    "crm mobile app android", "crm api access pricing",
    "crm with sms automation", "crm for field sales teams",
    "crm deal stage automation", "crm for b2b sales teams",
    "crm customer onboarding software", "crm reporting dashboards",
    "crm for franchise operations", "crm with quickbooks integration",
    "crm for mortgage brokers", "crm duplicate merge tool",
    "crm trial without credit card", "crm user permissions setup",
    "crm data import from excel", "crm for insurance agents",
]

PEST_TEMPLATES = [
    "pest control near me", "exterminator near me", "termite treatment cost",
    "bed bug exterminator", "ant control service", "wasp nest removal",
    "rodent control service", "mosquito control service",
    "cockroach exterminator cost", "flea treatment service",
]

PLUMBING_TEMPLATES = [
    "emergency plumber near me", "plumber near me", "water heater repair",
    "water heater installation cost", "drain cleaning service",
    "leak repair plumber", "tankless water heater install",
    "garbage disposal replacement", "sewer line inspection",
    "burst pipe repair cost",
]

HVAC_TEMPLATES = [
    "ac repair near me", "hvac repair service", "ac installation cost",
    "furnace repair near me", "ac tune up service", "24 hour hvac service",
    "heat pump installation", "duct cleaning service",
    "thermostat installation cost", "ac not cooling service call",
]

ELECTRICAL_TEMPLATES = [
    "electrician near me", "electrical panel upgrade cost",
    "ceiling fan installation", "ev charger installation home",
    "light fixture installation", "generator installation cost",
    "outlet repair electrician", "rewiring cost estimate",
]

JOB_SAAS_TEMPLATES = [
    "crm software jobs", "crm manager jobs", "crm administrator job description",
    "crm analyst salary", "sales jobs near me", "digital marketing jobs",
    "digital marketing internship", "sales rep resume sample",
    "crm consultant career path", "glassdoor flowtrack salaries",
    "crm careers", "how to become a crm administrator",
]

JOB_HOME_TEMPLATES = [
    "plumber jobs near me", "hvac technician jobs", "pest control jobs",
    "electrician apprenticeship", "hvac technician salary",
    "plumber salary in texas", "pest control salary",
    "indeed pest control jobs", "how to become a pest control technician",
    "electrician trade school cost",
]

FREE_TEMPLATES = [
    "free crm", "free crm software", "free crm download",
    "cheap crm for startups", "cheapest crm software", "crm crack version",
    "crm crack download", "crm torrent download", "nulled crm script",
    "open source crm github", "crm license key free", "crm discount code",
    "crm coupon code", "crm black friday discount",
    "free pest control inspection", "free plumbing quote",
    "cheap plumber near me", "discount pest control near me",
    "free hvac inspection", "cheap ac repair",
]

DIY_TEMPLATES = [
    "how to build a crm", "crm tutorial for beginners", "crm tutorial pdf",
    "what is a crm", "crm definition", "crm wikipedia",
    "crm comparison youtube", "crm requirements template",
    "crm implementation guide pdf", "reddit best crm",
    "crm certification course", "crm course syllabus",
    "diy pest control products", "how to get rid of ants yourself",
    "diy drain unclogging", "how to fix a leaky faucet",
    "garbage disposal repair youtube", "diy ac maintenance",
    "what does hvac stand for", "electrical wiring basics pdf",
    "how to install a ceiling fan yourself", "diy termite treatment",
]

COMPETITOR_TEMPLATES = [
    "hubspot crm pricing", "salesforce crm login", "zoho crm pricing",
    "pipedrive vs hubspot", "monday crm cost", "freshsales reviews",
    "bitrix24 pricing", "zendesk sell demo", "terminix vs orkin",
    "orkin pest control prices", "trusted plumber reviews",
    "best pest control near me reviews", "angi plumbing reviews",
    "homeadvisor electricians", "thumbtack hvac quotes",
    "angi electrician reviews",
]

SUPPORT_TEMPLATES = [
    "crm customer service number", "crm support number",
    "crm refund policy", "cancel crm subscription", "crm billing support",
    "crm live chat support", "pest control reschedule appointment",
    "plumber warranty claim", "hvac service call status",
    "cancel pest control contract", "crm account recovery",
    "crm password reset", "flowtrack billing", "flowtrack account settings",
    "crm subscription refund",
]

NOISE_TEMPLATES = [
    "crm vs spreadsheet", "is pest control worth it monthly",
    "how often should drain cleaning be done", "ac not blowing cold air",
    "water heater making noise", "weird smell from ac vent",
    "crm training videos", "pest control spray schedule",
    "plumbing permit requirements", "what size water heater do i need",
    "crm data migration tips", "crm adoption strategies",
    "pest control chemicals list", "how do plumbers find leaks",
    "ac compressor replacement cost", "crm meaning in business",
    "crm examples for small teams",
    "how much does pest control cost per month", "best time to service ac",
    "crm vs marketing automation", "signs you need a new water heater",
    "crm implementation timeline", "do i need a permit for electrical work",
    "crm trial length", "plumbing inspection checklist",
    "hvac maintenance plan worth it", "crm onboarding process",
    "termite inspection cost", "crm for nonprofits pricing",
    "tankless vs tank water heater",
]

# Safe modifiers used to uniquify duplicate templates (no intent words that
# would accidentally trigger the preset waste dictionaries).
_MODIFIERS = [
    "", " 2025", " guide", " reviews", " comparison", " checklist",
    " explained", " online", " for teams", " usa", " today",
    " for beginners", " step by step", " calculator", " estimator",
    " ideas", " options", " tips", " examples", " for contractors",
]


def generate_sample_data(n_rows: int = DEMO_ROWS, seed: int = 42) -> pd.DataFrame:
    """Return a deterministic synthetic search-terms DataFrame."""
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    seen: set[str] = set()

    scale = n_rows / DEMO_ROWS

    def add(
        templates: list[str],
        count: int,
        campaigns: list[str],
        ad_group: str,
        cpc_range: tuple[float, float],
        clicks_range: tuple[int, int],
        conv_rate: float,
        conv_value_range: tuple[float, float],
        match_weights: tuple[float, float, float],
    ) -> None:
        count = max(1, int(round(count * scale)))
        made = 0
        attempts = 0
        while made < count and attempts < count * 15:
            attempts += 1
            base = str(templates[int(rng.integers(len(templates)))])
            term = base
            if term in seen:
                modifier = _MODIFIERS[int(rng.integers(len(_MODIFIERS)))]
                term = f"{base}{modifier}"
            if term in seen:
                continue
            seen.add(term)

            clicks = int(rng.integers(clicks_range[0], clicks_range[1] + 1))
            cpc = float(rng.uniform(cpc_range[0], cpc_range[1]))
            cost = round(clicks * cpc, 2)
            conversions = int(rng.binomial(clicks, conv_rate)) if conv_rate > 0 else 0
            conversions = min(conversions, 6)
            conv_value = round(
                conversions * float(rng.uniform(conv_value_range[0], conv_value_range[1])), 2
            )
            impressions = int(clicks * int(rng.integers(6, 25)))
            match_type = str(
                rng.choice(("Exact", "Phrase", "Broad"), p=match_weights)
            )
            roll = rng.random()
            added_excluded = "--" if roll < 0.8 else ("Excluded" if roll < 0.9 else "Added")
            campaign = campaigns[int(rng.integers(len(campaigns)))]

            rows.append(
                {
                    "Search term": term,
                    "Match type": match_type,
                    "Campaign": campaign,
                    "Ad group": ad_group,
                    "Impr.": impressions,
                    "Clicks": clicks,
                    "Cost": cost,
                    "Conversions": conversions,
                    "Conv. value": conv_value,
                    "Added/Excluded": added_excluded,
                }
            )
            made += 1

    saas_brand = ["SaaS | Search - Brand"]
    saas_nonbrand = ["SaaS | Search - NonBrand"]
    pest = ["Home Services | Pest Control"]
    plumbing = ["Home Services | Plumbing"]
    hvac = ["Home Services | HVAC"]
    electrical = ["Home Services | Electrical"]
    home_all = pest + plumbing + hvac + electrical

    # --- converting traffic -------------------------------------------------
    add(BRAND_TEMPLATES, 80, saas_brand, "AG - Brand",
        (2.4, 3.8), (5, 22), 0.18, (420.0, 620.0), (0.55, 0.35, 0.10))
    add(SAAS_HIGH_INTENT, 170, saas_nonbrand, "AG - SaaS Core",
        (4.0, 6.5), (4, 18), 0.06, (450.0, 700.0), (0.35, 0.45, 0.20))
    add(SAAS_LONG_TAIL, 180, saas_nonbrand, "AG - SaaS Long Tail",
        (2.5, 4.5), (3, 12), 0.05, (400.0, 650.0), (0.25, 0.45, 0.30))
    add(PEST_TEMPLATES, 40, pest, "AG - Pest Core",
        (4.5, 8.5), (5, 14), 0.04, (280.0, 480.0), (0.30, 0.45, 0.25))
    add(PLUMBING_TEMPLATES, 40, plumbing, "AG - Plumbing Core",
        (4.5, 8.5), (5, 14), 0.04, (300.0, 520.0), (0.30, 0.45, 0.25))
    add(HVAC_TEMPLATES, 40, hvac, "AG - HVAC Core",
        (4.5, 8.5), (5, 14), 0.04, (320.0, 560.0), (0.30, 0.45, 0.25))
    add(ELECTRICAL_TEMPLATES, 30, electrical, "AG - Electrical Core",
        (4.0, 7.5), (4, 12), 0.04, (300.0, 520.0), (0.30, 0.45, 0.25))

    # --- deliberate waste clusters ------------------------------------------
    add(JOB_SAAS_TEMPLATES, 75, saas_nonbrand, "AG - Jobs",
        (1.2, 2.8), (3, 12), 0.0, (0.0, 0.0), (0.15, 0.35, 0.50))
    add(JOB_HOME_TEMPLATES, 75, home_all, "AG - Jobs",
        (1.2, 2.8), (3, 12), 0.0, (0.0, 0.0), (0.15, 0.35, 0.50))
    add(FREE_TEMPLATES, 120, saas_nonbrand + home_all, "AG - Unsorted",
        (0.9, 2.2), (4, 12), 0.0, (0.0, 0.0), (0.10, 0.30, 0.60))
    add(DIY_TEMPLATES, 150, saas_nonbrand + home_all, "AG - Unsorted",
        (1.0, 2.6), (2, 9), 0.0, (0.0, 0.0), (0.10, 0.30, 0.60))
    add(COMPETITOR_TEMPLATES, 120, saas_nonbrand + home_all, "AG - Competitors",
        (2.5, 4.8), (4, 14), 0.008, (300.0, 500.0), (0.20, 0.40, 0.40))
    add(SUPPORT_TEMPLATES, 90, saas_nonbrand + home_all, "AG - Support",
        (0.8, 1.9), (2, 7), 0.03, (350.0, 500.0), (0.40, 0.40, 0.20))

    # --- low-volume unproven noise -------------------------------------------
    add(NOISE_TEMPLATES, n_rows - len(rows), saas_nonbrand + home_all,
        "AG - Long Tail", (0.7, 2.0), (1, 3), 0.0, (0.0, 0.0),
        (0.20, 0.35, 0.45))

    columns = [
        "Search term", "Match type", "Campaign", "Ad group", "Impr.",
        "Clicks", "Cost", "Conversions", "Conv. value", "Added/Excluded",
    ]
    df = pd.DataFrame(rows, columns=columns)
    for col in ("Impr.", "Clicks"):
        df[col] = df[col].astype(int)
    return df


if __name__ == "__main__":  # quick sanity print when run directly
    demo = generate_sample_data()
    total = demo["Cost"].sum()
    conv = demo["Conversions"].sum()
    print(f"rows={len(demo)}  spend=${total:,.2f}  conversions={conv}  "
          f"account CPA=${total / max(conv, 1):,.2f}")
