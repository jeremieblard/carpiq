#!/usr/bin/env python3
"""
CarPIQ Price Scraper
====================
Scrapes AutoScout24 (FR/CH/DE/BE) + La Centrale (FR) for real market prices.
Outputs JSON correction factors for the CarPIQ DB depreciation curves.

Usage:
    python3 carpiq_price_scraper.py [--country fr|ch|de|be] [--output prices.json]

Run weekly via cron:
    0 8 * * 1 cd /path/to/carpiq && python3 carpiq_price_scraper.py >> scraper.log 2>&1
"""

import json, time, re, random, sys, os, argparse
from datetime import datetime
from urllib.parse import urlencode
from statistics import median, mean

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("pip install requests beautifulsoup4")
    sys.exit(1)

# ── CONFIG ────────────────────────────────────────────────────────────────────

# 30 representative models covering 80%+ of CarPIQ recommendations
MODELS = [
    # ── MINI / SUV_URBAN (citadines) ─────────────────────────────────────────
    ("aygo",         "Toyota Aygo X",          "toyota",       "Aygo X",              "ice",  16990),
    ("spring",       "Dacia Spring",            "dacia",        "Spring",              "bev",  16990),
    ("fiat500e",     "Fiat 500e",               "fiat",         "500e",                "bev",  26990),
    ("jazz_hev",     "Honda Jazz e:HEV",        "honda",        "Jazz eHEV",           "hev",  23900),

    # ── SMALL (citadines supérieures) ────────────────────────────────────────
    ("polo",         "Volkswagen Polo",         "volkswagen",   "Polo",                "ice",  21490),
    ("clio_ice",     "Renault Clio",            "renault",      "Clio",                "ice",  18300),
    ("208",          "Peugeot 208",             "peugeot",      "208",                 "ice",  19900),
    ("ibiza",        "SEAT Ibiza",              "seat",         "Ibiza",               "ice",  19490),
    ("sandero",      "Dacia Sandero",           "dacia",        "Sandero",             "ice",  11390),
    ("clio_hev",     "Renault Clio E-Tech",     "renault",      "Clio E-Tech Hybrid",  "hev",  22900),
    ("yaris_hev",    "Toyota Yaris Hybrid",     "toyota",       "Yaris Hybrid",        "hev",  23500),
    ("e208_bev",     "Peugeot e-208",           "peugeot",      "e-208",               "bev",  33900),
    ("ds3_bev",      "DS 3 E-Tense",            "ds",           "DS3 E-Tense",         "bev",  39900),

    # ── COMPACT / COMPACT_BREAK ───────────────────────────────────────────────
    ("golf",         "Volkswagen Golf",         "volkswagen",   "Golf",                "ice",  28500),
    ("octavia_ice",  "Skoda Octavia",           "skoda",        "Octavia",             "ice",  27800),
    ("308_ice",      "Peugeot 308",             "peugeot",      "308",                 "ice",  27900),
    ("a3_ice",       "Audi A3",                 "audi",         "A3",                  "ice",  32900),
    ("leon_ice",     "SEAT León",               "seat",         "Leon",                "ice",  24900),
    ("corolla_hev",  "Toyota Corolla Hybrid",   "toyota",       "Corolla Hybrid",      "hev",  30900),
    ("308_phev",     "Peugeot 308 PHEV",        "peugeot",      "308 PHEV",            "phev", 42900),
    ("octavia_phev", "Skoda Octavia iV PHEV",   "skoda",        "Octavia iV",          "phev", 41900),
    ("megane_bev",   "Renault Mégane E-Tech",   "renault",      "Megane E-Tech",       "bev",  35000),
    ("id3_bev",      "VW ID.3",                 "volkswagen",   "ID.3",                "bev",  35995),

    # ── SALOON (berlines familiales — allemandes vs françaises) ──────────────
    ("3series_ice",  "BMW Série 3",             "bmw",          "Serie 3 320",         "ice",  48900),
    ("c_class_ice",  "Mercedes Classe C",       "mercedes-benz","C 200",               "ice",  47900),
    ("passat_ice",   "VW Passat",               "volkswagen",   "Passat",              "ice",  39900),
    ("a4_ice",       "Audi A4",                 "audi",         "A4",                  "ice",  44900),
    ("a4_die",       "Audi A4 TDI",             "audi",         "A4 TDI",              "die",  46900),
    ("3series_phev", "BMW 330e PHEV",           "bmw",          "330e",                "phev", 58900),
    ("eclass_phev",  "Mercedes E 300 e PHEV",   "mercedes-benz","E 300 e",             "phev", 71900),
    ("408_hev",      "Peugeot 408 Hybrid",      "peugeot",      "408 Hybrid",          "hev",  37900),
    ("ioniq6_bev",   "Hyundai Ioniq 6",         "hyundai",      "Ioniq 6",             "bev",  54900),
    ("tesla_m3",     "Tesla Model 3",           "tesla",        "Model 3",             "bev",  42990),

    # ── SUV_URBAN (petits SUV) ────────────────────────────────────────────────
    ("yaris_cross",  "Toyota Yaris Cross HEV",  "toyota",       "Yaris Cross Hybrid",  "hev",  29500),
    ("captur_hev",   "Renault Captur E-Tech",   "renault",      "Captur E-Tech",       "hev",  29500),
    ("2008_ice",     "Peugeot 2008",            "peugeot",      "2008",                "ice",  24900),
    ("duster_ice",   "Dacia Duster",            "dacia",        "Duster",              "ice",  19900),
    ("kamiq_ice",    "Skoda Kamiq",             "skoda",        "Kamiq",               "ice",  24900),
    ("r5_bev",       "Renault 5 E-Tech",        "renault",      "R5 E-Tech",           "bev",  25000),

    # ── SUV_COMPACT ───────────────────────────────────────────────────────────
    ("tucson_hev",   "Hyundai Tucson HEV",      "hyundai",      "Tucson Hybrid",       "hev",  39900),
    ("niro_hev",     "Kia Niro Hybrid",         "kia",          "Niro Hybrid",         "hev",  30900),
    ("chr_hev",      "Toyota C-HR Hybrid",      "toyota",       "C-HR Hybrid",         "hev",  31900),
    ("3008_ice",     "Peugeot 3008",            "peugeot",      "3008",                "ice",  30900),
    ("karoq_ice",    "Skoda Karoq",             "skoda",        "Karoq",               "ice",  30900),
    ("tiguan_ice",   "Volkswagen Tiguan",       "volkswagen",   "Tiguan",              "ice",  35500),
    ("kuga_phev",    "Ford Kuga PHEV",          "ford",         "Kuga PHEV",           "phev", 43900),
    ("3008_phev",    "Peugeot 3008 Hybrid",     "peugeot",      "3008 PHEV Hybrid",    "phev", 46900),
    ("tucson_phev",  "Hyundai Tucson PHEV",     "hyundai",      "Tucson PHEV",         "phev", 47900),
    ("id4_bev",      "VW ID.4",                 "volkswagen",   "ID.4",                "bev",  44995),
    ("ioniq5_bev",   "Hyundai Ioniq 5",         "hyundai",      "Ioniq 5",             "bev",  54900),

    # ── SUV_FAMILY / SUV_LARGE ────────────────────────────────────────────────
    ("rav4_hev",     "Toyota RAV4 HEV",         "toyota",       "RAV4 Hybrid",         "hev",  44900),
    ("kodiaq_ice",   "Skoda Kodiaq",            "skoda",        "Kodiaq",              "ice",  39900),
    ("kodiaq_die",   "Skoda Kodiaq TDI",        "skoda",        "Kodiaq TDI",          "die",  44900),
    ("cx5_ice",      "Mazda CX-5",              "mazda",        "CX-5",                "ice",  35900),
    ("x5_phev",      "BMW X5 xDrive45e PHEV",   "bmw",          "X5 45e",              "phev", 89900),
    ("rav4_phev",    "Toyota RAV4 PHEV",        "toyota",       "RAV4 PHEV",           "phev", 55900),
    ("tesla_my",     "Tesla Model Y",           "tesla",        "Model Y",             "bev",  44990),

    # ── PREMIUM / EXECUTIVE (décote différente!) ──────────────────────────────
    ("a6_ice",       "Audi A6",                 "audi",         "A6",                  "ice",  62900),
    ("5series_ice",  "BMW Série 5",             "bmw",          "Serie 5 520",         "ice",  64900),
    ("eclass_ice",   "Mercedes Classe E",       "mercedes-benz","E 200",               "ice",  62900),
    ("superb_phev",  "Skoda Superb iV PHEV",    "skoda",        "Superb iV",           "phev", 51900),
    ("lexus_ux",     "Lexus UX 250h HEV",       "lexus",        "UX 250h",             "hev",  44900),
]

# Age tranches to scrape (year offsets from current year)
AGE_TRANCHES = [1, 2, 3, 5, 7]
CURRENT_YEAR = datetime.now().year

# Country configs
COUNTRY_CONFIGS = {
    "fr": {
        "as24_domain": "autoscout24.fr",
        "la_centrale": True,
        "currency": "EUR",
        "currency_sym": "€",
    },
    "ch": {
        "as24_domain": "autoscout24.ch",
        "la_centrale": False,
        "currency": "CHF",
        "currency_sym": "CHF",
    },
    "de": {
        "as24_domain": "autoscout24.de",
        "la_centrale": False,
        "currency": "EUR",
        "currency_sym": "€",
    },
    "be": {
        "as24_domain": "autoscout24.be",
        "la_centrale": False,
        "currency": "EUR",
        "currency_sym": "€",
    },
}

# ── HTTP SESSION ──────────────────────────────────────────────────────────────

HEADERS_LIST = [
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"},
]

session = requests.Session()

def get_headers():
    h = random.choice(HEADERS_LIST).copy()
    h["Accept-Language"] = "fr-FR,fr;q=0.9,en;q=0.8"
    h["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    return h

def fetch(url, retries=3, delay=3):
    for i in range(retries):
        try:
            time.sleep(delay + random.uniform(1, 3))
            r = session.get(url, headers=get_headers(), timeout=15)
            if r.status_code == 200:
                return r.text
            elif r.status_code == 429:
                print(f"  ⚠ Rate limited, waiting {delay*4}s...")
                time.sleep(delay * 4)
            else:
                print(f"  ⚠ HTTP {r.status_code} for {url[:80]}")
        except Exception as e:
            print(f"  ⚠ Error: {e}")
        time.sleep(delay * (i + 1))
    return None

# ── AUTOSCOUT24 SCRAPER ───────────────────────────────────────────────────────

def build_as24_url(domain, brand, query, year_from, year_to, max_km=120000):
    """Build AutoScout24 search URL with year and mileage filters."""
    base = f"https://www.{domain}/lst/{brand}"
    params = {
        "atype": "C",           # Cars only
        "fregfrom": year_from,
        "fregto": year_to,
        "kmto": max_km,
        "sort": "age",
        "desc": "0",
        "ustate": "N,U",        # New + used
        "q": query,
    }
    return f"{base}?{urlencode(params)}"

def parse_as24_prices(html):
    """Extract prices from AutoScout24 listing page."""
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    prices = []

    # AutoScout24 price patterns (they change often — multiple selectors)
    selectors = [
        "[data-testid='regular-price']",
        ".Price_price__C_0_r",
        "p[data-qa='price']",
        ".sc-font-xl",
        "[class*='Price_price']",
        "[class*='price']",
    ]

    for sel in selectors:
        elements = soup.select(sel)
        if elements:
            for el in elements:
                text = el.get_text(strip=True)
                # Extract numeric price
                price = extract_price(text)
                if price and 3000 < price < 200000:
                    prices.append(price)
            if prices:
                break

    # Fallback: regex on raw HTML
    if not prices:
        patterns = [
            r'(?:CHF|€|EUR)\s*[\s]?([\d][\'.,\s\d]+)',
            r'"price[^"]*"[^:]*:\s*"?(\d[\d.,]+)"?',
            r'(\d{2,3}[.,\'\s]\d{3})',
        ]
        for pat in patterns:
            matches = re.findall(pat, html)
            for m in matches:
                price = extract_price(m)
                if price and 3000 < price < 200000:
                    prices.append(price)
            if len(prices) >= 5:
                break

    return sorted(prices)

def extract_price(text):
    """Convert price string to integer. Handles CH (37'000), DE (37.000), FR (37 000) formats."""
    if not text:
        return None
    t = str(text).strip()
    # Remove currency symbols
    t = re.sub(r"[CHF€£$\u202f\xa0]", "", t).strip()
    # Remove trailing punctuation like ".-"
    t = re.sub(r"[.\-]+$", "", t.strip())
    # Swiss format: 37'000 or 37.000 (thousands separator = . or ')
    # French format: 37 000 or 37 000
    # Remove known separators keeping only digits
    t = re.sub(r"[\'\s,]", "", t)   # Remove apostrophes, spaces, commas
    # If still has dots: check if it's a thousands sep (37.000) or decimal (37.50)
    if "." in t:
        parts = t.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            # Thousands separator: 37.000 → 37000
            t = t.replace(".", "")
        else:
            # Decimal: 37.5 → 37
            t = parts[0]
    try:
        val = int(t)
        return val if 1000 < val < 500000 else None
    except:
        return None

def scrape_as24(domain, brand, query, year_from, year_to, label=""):
    """Scrape AutoScout24 for a model in a given year range."""
    url = build_as24_url(domain, brand, query, year_from, year_to)
    print(f"    → AS24 {year_from}-{year_to}: {url[:90]}")
    html = fetch(url, delay=4)
    prices = parse_as24_prices(html)
    if prices:
        # Remove extreme outliers (below 10th percentile or above 90th)
        p10 = prices[len(prices)//10] if len(prices) >= 10 else prices[0]
        p90 = prices[-(len(prices)//10)-1] if len(prices) >= 10 else prices[-1]
        filtered = [p for p in prices if p10 <= p <= p90]
        med = int(median(filtered)) if filtered else None
        print(f"      {len(prices)} prices found, median={med}, range=[{prices[0]:,}–{prices[-1]:,}]")
        return {"prices": filtered, "median": med, "count": len(prices), "url": url}
    else:
        print(f"      No prices found")
        return {"prices": [], "median": None, "count": 0, "url": url}

# ── LA CENTRALE SCRAPER (FR ONLY) ────────────────────────────────────────────

def scrape_la_centrale(brand, query, year_from, year_to):
    """Scrape La Centrale for French market prices."""
    # La Centrale search URL format
    clean_query = re.sub(r'[^a-zA-Z0-9 ]', '', query).strip().replace(' ', '+')
    url = f"https://www.lacentrale.fr/listing?makesModelsCommercialNames={clean_query}&yearMin={year_from}&yearMax={year_to}&sortBy=price&sortOrder=asc"
    print(f"    → LaCentrale {year_from}-{year_to}: {url[:80]}")
    html = fetch(url, delay=5)
    if not html:
        return {"prices": [], "median": None, "count": 0}

    soup = BeautifulSoup(html, "html.parser")
    prices = []

    # La Centrale price selectors
    for sel in [".price", "[class*='price']", ".vehicleCard-price", "[data-v-price]"]:
        elements = soup.select(sel)
        for el in elements:
            price = extract_price(el.get_text())
            if price and 3000 < price < 200000:
                prices.append(price)
        if prices:
            break

    # Fallback regex
    if not prices:
        matches = re.findall(r'(\d{2,3}[\s.]\d{3})\s*(?:€|EUR)', html)
        for m in matches:
            price = extract_price(m)
            if price:
                prices.append(price)

    prices = sorted(prices)
    med = int(median(prices)) if prices else None
    print(f"      {len(prices)} prices, median={med}")
    return {"prices": prices, "median": med, "count": len(prices)}

# ── DEPRECIATION CALCULATOR ──────────────────────────────────────────────────

def calc_depr_factor(real_price, new_price):
    """Calculate real depreciation factor (0.0–1.0)."""
    if not real_price or not new_price or new_price == 0:
        return None
    factor = real_price / new_price
    # Sanity check: depreciation factor should be between 10% and 100%
    return round(factor, 3) if 0.10 <= factor <= 1.00 else None

def interpolate_depr_curve(measured_points, new_price):
    """
    Build a full 11-point depreciation curve [year 0..10] from measured points.
    measured_points: {age: factor}
    Returns: list of 11 floats
    """
    # Always start at 1.0 (new = 100%)
    curve = {0: 1.0}
    curve.update(measured_points)

    # Interpolate missing years
    years = sorted(curve.keys())
    result = []
    for y in range(11):
        if y in curve:
            result.append(curve[y])
        else:
            # Linear interpolation between known points
            prev_y = max(k for k in years if k <= y) if any(k <= y for k in years) else 0
            next_y = min(k for k in years if k >= y) if any(k >= y for k in years) else 10
            if prev_y == next_y:
                result.append(curve.get(prev_y, 0.5))
            else:
                alpha = (y - prev_y) / (next_y - prev_y)
                v = curve[prev_y] + alpha * (curve.get(next_y, 0.2) - curve[prev_y])
                result.append(round(v, 3))

    return result

# ── MAIN SCRAPER ──────────────────────────────────────────────────────────────

def scrape_model(model_id, name, brand, query, pt, new_price, country_cfg):
    """Scrape a single model across all age tranches."""
    domain = country_cfg["as24_domain"]
    results = {}

    print(f"\n  [{pt.upper()}] {name} (neuf {country_cfg['currency_sym']}{new_price:,})")

    for age in AGE_TRANCHES:
        year_from = CURRENT_YEAR - age - 1
        year_to   = CURRENT_YEAR - age + 1
        # Adjust km range by age (older = more km expected)
        max_km = {1: 25000, 2: 40000, 3: 60000, 5: 90000, 7: 120000}[age]

        as24_data = scrape_as24(domain, brand, query, year_from, year_to, f"{name} {age}y")
        prices = as24_data["prices"]

        # Supplement with La Centrale if FR and few results
        if country_cfg.get("la_centrale") and len(prices) < 5:
            lc_data = scrape_la_centrale(brand, query, year_from, year_to)
            prices = sorted(prices + lc_data["prices"])

        if prices:
            p_median = int(median(prices))
            factor = calc_depr_factor(p_median, new_price)
            results[age] = {
                "median_price": p_median,
                "depr_factor": factor,
                "sample_size": len(prices),
                "year_range": [year_from, year_to],
            }
        else:
            results[age] = {"median_price": None, "depr_factor": None, "sample_size": 0}

        # Polite delay between tranches
        time.sleep(random.uniform(3, 6))

    return results

def run_scraper(country="fr", output_file="carpiq_prices.json", models_subset=None):
    """Main scraping function."""
    country_cfg = COUNTRY_CONFIGS.get(country, COUNTRY_CONFIGS["fr"])
    models_to_scrape = models_subset or MODELS

    print(f"\n{'='*60}")
    print(f"CarPIQ Price Scraper — {country.upper()} ({country_cfg['as24_domain']})")
    print(f"Models: {len(models_to_scrape)} | Ages: {AGE_TRANCHES}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")

    results = {
        "meta": {
            "scraped_at": datetime.now().isoformat(),
            "country": country,
            "currency": country_cfg["currency"],
            "models_scraped": len(models_to_scrape),
        },
        "models": {},
        "depr_curves": {},   # Calibrated DEPR curves per PT
        "price_corrections": {},  # Per-model price correction vs DB estimate
    }

    pt_factors = {"hev": {}, "phev": {}, "bev": {}, "ice": {}, "die": {}}

    for model_id, name, brand, query, pt, new_price in models_to_scrape:
        try:
            model_results = scrape_model(model_id, name, brand, query, pt, new_price, country_cfg)
            results["models"][model_id] = {
                "name": name,
                "pt": pt,
                "new_price": new_price,
                "ages": model_results,
            }

            # Collect factors by PT for aggregate curve
            for age, data in model_results.items():
                if data["depr_factor"] and data["sample_size"] >= 3:
                    if age not in pt_factors[pt]:
                        pt_factors[pt][age] = []
                    pt_factors[pt][age].append(data["depr_factor"])

            # Per-model correction factor (vs CarPIQ DB estimate)
            corrections = {}
            for age, data in model_results.items():
                if data["depr_factor"]:
                    corrections[age] = data["depr_factor"]
            if corrections:
                results["price_corrections"][model_id] = corrections

        except Exception as e:
            print(f"  ✗ Error scraping {name}: {e}")
            results["models"][model_id] = {"name": name, "pt": pt, "error": str(e)}

        # Save partial results after each model
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    # ── Build calibrated DEPR curves per PT ──────────────────────────────
    print(f"\n{'='*60}")
    print("Building calibrated depreciation curves...")
    for pt, age_data in pt_factors.items():
        if not age_data:
            continue
        measured = {}
        for age, factors in age_data.items():
            med_factor = round(median(factors), 3)
            measured[age] = med_factor
            print(f"  {pt} @ {age}y: {med_factor:.2f} (n={len(factors)}, range=[{min(factors):.2f}–{max(factors):.2f}])")

        curve = interpolate_depr_curve(measured, 1.0)
        results["depr_curves"][pt] = curve
        print(f"  → {pt} curve: {curve}")

    # ── Save final results ────────────────────────────────────────────────
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done! Results saved to: {output_file}")
    print(f"   Models scraped: {len(results['models'])}")
    print(f"   PT curves calibrated: {list(results['depr_curves'].keys())}")

    return results

# ── APPLY CORRECTIONS TO CARPIQ DB ───────────────────────────────────────────

def generate_js_patch(prices_json_file, output_js="carpiq_depr_patch.js"):
    """
    Read scraped prices.json and generate JS patch to apply to carpiq HTML.
    This updates the DEPR[] curves based on real market data.
    """
    with open(prices_json_file) as f:
        data = json.load(f)

    curves = data.get("depr_curves", {})
    corrections = data.get("price_corrections", {})

    js_lines = [
        f"// CarPIQ DEPR patch — generated {data['meta']['scraped_at']}",
        f"// Country: {data['meta']['country']} | Models: {data['meta']['models_scraped']}",
        "",
        "// ── Calibrated DEPR curves (paste into carpiq HTML, replace DEPR constant) ──",
        "const DEPR_CALIBRATED = {",
    ]

    for pt, curve in curves.items():
        js_lines.append(f"  {pt}:{json.dumps(curve)},")

    js_lines += [
        "};",
        "",
        "// ── Per-model price corrections (factor vs generic DEPR curve) ──",
        "// Usage: purchAtAge(car, age) * (PRICE_CORRECTIONS[car.id]?.[age] || 1)",
        "const PRICE_CORRECTIONS = {",
    ]

    for model_id, corrections_by_age in corrections.items():
        js_lines.append(f"  '{model_id}': {json.dumps(corrections_by_age)},")

    js_lines += ["};"]

    patch = "\n".join(js_lines)
    with open(output_js, "w") as f:
        f.write(patch)

    print(f"✅ JS patch written to: {output_js}")
    print("   Paste DEPR_CALIBRATED into carpiq HTML to update depreciation curves.")
    return patch

# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CarPIQ Price Scraper")
    parser.add_argument("--country",  default="fr", choices=["fr","ch","de","be"], help="Country to scrape")
    parser.add_argument("--output",   default="carpiq_prices.json", help="Output JSON file")
    parser.add_argument("--patch",    action="store_true", help="Generate JS patch from existing JSON")
    parser.add_argument("--test",     action="store_true", help="Test mode: scrape 3 models only")
    parser.add_argument("--apply",    default=None, help="Apply prices.json to carpiq HTML file")
    args = parser.parse_args()

    if args.patch:
        generate_js_patch(args.output, args.output.replace(".json", "_patch.js"))
    elif args.test:
        test_models = MODELS[:3]
        print(f"TEST MODE — scraping {len(test_models)} models")
        run_scraper(args.country, args.output, test_models)
    else:
        run_scraper(args.country, args.output)
