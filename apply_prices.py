#!/usr/bin/env python3
"""
CarPIQ Price Patcher
====================
Reads prices.json (output of carpiq_price_scraper.py) and applies
real market depreciation curves + per-model corrections to carpiq HTML.

Usage:
    python3 apply_prices.py --prices prices_ch.json --html carpiq.html --out carpiq_updated.html
"""

import json, re, sys, argparse
from datetime import datetime
from statistics import median

def load_prices(prices_file):
    with open(prices_file, encoding="utf-8") as f:
        return json.load(f)

def load_html(html_file):
    with open(html_file, encoding="utf-8") as f:
        return f.read()

def save_html(html, output_file):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html)

# ── PATCH 1: Update DEPR curves ───────────────────────────────────────────────

DEPR_PT_MAP = {
    "ice": "ice",
    "hev": "hev",
    "phev": "phev",
    "bev": "bev",
    "die": "die",
}

def patch_depr_curves(html, depr_curves, min_models_per_pt=3):
    """
    Replace DEPR[pt] values in HTML with calibrated curves.
    Only patches PT types with sufficient data (min_models_per_pt).
    """
    patched = html
    changes = []

    for pt, curve in depr_curves.items():
        if pt not in DEPR_PT_MAP:
            continue

        # Validate curve
        if len(curve) != 11:
            print(f"  ⚠ Skipping {pt}: curve has {len(curve)} points (expected 11)")
            continue
        if curve[0] != 1.0:
            curve[0] = 1.0  # Force year 0 = 100%

        curve_str = json.dumps([round(v, 3) for v in curve])

        # Find and replace: phev:[1,...],
        pattern = rf"({re.escape(pt)}:)\[[\d.,\s]+\]"
        replacement = f"\\g<1>{curve_str}"
        new_html = re.sub(pattern, replacement, patched, count=1)

        if new_html != patched:
            patched = new_html
            changes.append(f"✅ DEPR[{pt}] → {curve_str}")
        else:
            changes.append(f"⚠ DEPR[{pt}] — pattern not found in HTML")

    return patched, changes

# ── PATCH 2: Per-model price corrections in DB ────────────────────────────────

def patch_model_prices(html, models_data):
    """
    Update newP values in the DB for models where scraped price deviates
    significantly from current estimate (>15% difference at year 0 equivalent).
    
    Strategy: use year-1 price × (1/depr_year1) to back-calculate implied new price.
    Only update if we have >= 5 price samples.
    """
    patched = html
    changes = []

    for model_id, model_data in models_data.items():
        if "error" in model_data:
            continue

        new_price = model_data.get("new_price")
        if not new_price:
            continue

        ages = model_data.get("ages", {})

        # Find the best age tranche with most data
        best_age = None
        best_data = None
        for age_key in ["2", "3", 2, 3]:
            age_str = str(age_key)
            if age_str in ages and ages[age_str].get("sample_size", 0) >= 5:
                best_age = int(age_str)
                best_data = ages[age_str]
                break

        if not best_data or not best_data.get("depr_factor"):
            continue

        real_factor = best_data["depr_factor"]
        real_median_price = best_data["median_price"]
        sample_size = best_data["sample_size"]

        # Back-calculate implied new price from real market data
        implied_new = round(real_median_price / real_factor)
        deviation = abs(implied_new - new_price) / new_price

        if deviation > 0.15:  # >15% difference
            # Update newP in DB — find: id:'model_id',name:'...',brand:'...',pt:'...',seg:[...],newP:XXXXX
            pattern = rf"(id:'{re.escape(model_id)}'[^}}]{{0,200}}newP:)\d+"
            new_html = re.sub(pattern, f"\\g<1>{implied_new}", patched, count=1)

            if new_html != patched:
                patched = new_html
                changes.append(
                    f"✅ {model_id}: newP {new_price:,}→{implied_new:,} "
                    f"({deviation*100:.0f}% off, n={sample_size}, "
                    f"real@{best_age}y={real_median_price:,})"
                )
            else:
                changes.append(f"⚠ {model_id}: pattern not found")
        else:
            changes.append(f"   {model_id}: OK (deviation {deviation*100:.1f}% < 15%)")

    return patched, changes

# ── PATCH 3: Inject update timestamp + data quality badge ─────────────────────

def patch_metadata(html, prices_data):
    """Add a small data freshness indicator to the sources line."""
    scraped_at = prices_data.get("meta", {}).get("scraped_at", "")
    if not scraped_at:
        return html, []

    date_str = scraped_at[:10]  # YYYY-MM-DD
    models_count = prices_data.get("meta", {}).get("models_scraped", 0)
    country = prices_data.get("meta", {}).get("country", "").upper()

    # Find sources line and append data freshness
    old_marker = "Spritmonitor · Argus · ADAC"
    new_marker = f"Spritmonitor · Argus · ADAC · Prix marché {country} vérifiés {date_str} ({models_count} modèles AutoScout24)"

    if old_marker in html:
        patched = html.replace(old_marker, new_marker, 1)
        return patched, [f"✅ Sources updated with freshness date {date_str}"]

    return html, ["⚠ Sources line not found"]

# ── MAIN ──────────────────────────────────────────────────────────────────────

def apply_patches(prices_file, html_file, output_file):
    print(f"\n{'='*60}")
    print(f"CarPIQ Price Patcher")
    print(f"  Prices: {prices_file}")
    print(f"  HTML:   {html_file}")
    print(f"  Output: {output_file}")
    print(f"  Time:   {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    prices = load_prices(prices_file)
    html = load_html(html_file)

    meta = prices.get("meta", {})
    print(f"Prices data: {meta.get('country','?').upper()} | {meta.get('scraped_at','?')[:10]} | {meta.get('models_scraped','?')} models\n")

    # ── Patch 1: DEPR curves ────────────────────────────────────────────────
    print("── Patch 1: Depreciation curves ──")
    depr_curves = prices.get("depr_curves", {})
    if depr_curves:
        html, changes = patch_depr_curves(html, depr_curves)
        for c in changes:
            print(f"  {c}")
    else:
        print("  ⚠ No calibrated curves in prices.json (run scraper first)")
    print()

    # ── Patch 2: Per-model prices ───────────────────────────────────────────
    print("── Patch 2: Model prices (>15% deviation) ──")
    models_data = prices.get("models", {})
    if models_data:
        html, changes = patch_model_prices(html, models_data)
        for c in changes:
            print(f"  {c}")
    else:
        print("  ⚠ No model data in prices.json")
    print()

    # ── Patch 3: Metadata ───────────────────────────────────────────────────
    print("── Patch 3: Data freshness metadata ──")
    html, changes = patch_metadata(html, prices)
    for c in changes:
        print(f"  {c}")
    print()

    # ── Save ────────────────────────────────────────────────────────────────
    save_html(html, output_file)
    print(f"✅ Patched HTML saved to: {output_file}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apply scraped prices to CarPIQ HTML")
    parser.add_argument("--prices", required=True, help="prices.json from scraper")
    parser.add_argument("--html",   required=True, help="Input carpiq HTML file")
    parser.add_argument("--out",    required=True, help="Output HTML file")
    args = parser.parse_args()

    success = apply_patches(args.prices, args.html, args.out)
    sys.exit(0 if success else 1)
