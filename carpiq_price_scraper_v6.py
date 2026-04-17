#!/usr/bin/env python3
"""
CarPIQ Price Scraper v6
=======================
Améliorations vs v5 :
  - Scrape par modèle × carburant (chaque fuel a son propre pool de 20+ annonces)
  - Âge en années réelles au moment du scrape (pas année d'immatriculation)
  - Enrichissement : chaque scrape ajoute des observations, fenêtre glissante 120 jours
  - Structure JSON : observations horodatées → current_median calculé à la lecture

Usage:
    python3 carpiq_price_scraper_v6.py --country ch --output prices_v6.json
    python3 carpiq_price_scraper_v6.py --country ch --test
    python3 carpiq_price_scraper_v6.py --country ch --brand vw
"""

import json, re, time, random, argparse
from datetime import datetime, date, timedelta
from urllib.parse import urlencode
from statistics import median
from collections import defaultdict

# ── CARBURANTS ────────────────────────────────────────────────────────────────

# ── MODÈLES ───────────────────────────────────────────────────────────────────
# Format: (brand_id, brand_slug, model_slug, model_name, [fuels_à_scraper])
# Déclarer seulement les carburants réellement présents sur le marché CH.
# Ça évite des requêtes inutiles (ex: Tesla diesel, Dacia BEV premium...)

MODELS = [
    # Format: (brand_id, brand_slug, model_prefix, model_slug, model_name, [fuels])
    # Préfixe: "mo" = model standard, "mg" = model group (BMW séries confirmé)
    # Slugs confirmés: rav-4 (Toyota), 3-series/mg- (BMW)
    # Mercedes classes: à vérifier (probablement mg- aussi)

    # ── VOLKSWAGEN ────────────────────────────────────────────────────────────
    ("vw", "vw", "mo", "golf",      "Golf",      ["ice","die","hybrid"]),
    ("vw", "vw", "mo", "polo",      "Polo",      ["ice","hybrid"]),
    ("vw", "vw", "mo", "tiguan",    "Tiguan",    ["ice","die","hybrid"]),
    ("vw", "vw", "mo", "t-roc",     "T-Roc",     ["ice","die","hybrid"]),
    ("vw", "vw", "mo", "t-cross",   "T-Cross",   ["ice"]),
    ("vw", "vw", "mo", "passat",    "Passat",     ["ice","die","hybrid"]),
    ("vw", "vw", "mo", "id3",      "ID.3",       ["bev"]),
    ("vw", "vw", "mo", "id4",      "ID.4",       ["bev"]),
    ("vw", "vw", "mo", "id5",      "ID.5",       ["bev"]),
    ("vw", "vw", "mo", "touareg",   "Touareg",    ["ice","die","hybrid"]),
    ("vw", "vw", "mo", "touran",    "Touran",     ["ice","die"]),
    ("vw", "vw", "mo", "arteon",    "Arteon",     ["ice","die","hybrid"]),
    ("vw", "vw", "mo", "taigo",     "Taigo",      ["ice"]),
    # ── AUDI ──────────────────────────────────────────────────────────────────
    ("audi", "audi", "mo", "a1",        "A1",         ["ice"]),
    ("audi", "audi", "mo", "a3",        "A3",         ["ice","die","hybrid"]),
    ("audi", "audi", "mo", "a4",        "A4",         ["ice","die","hybrid"]),
    ("audi", "audi", "mo", "a5",        "A5",         ["ice","die","hybrid"]),
    ("audi", "audi", "mo", "a6",        "A6",         ["ice","die","hybrid"]),
    ("audi", "audi", "mo", "a7",        "A7",         ["ice","die","hybrid"]),
    ("audi", "audi", "mo", "a8",        "A8",         ["ice","hybrid"]),
    ("audi", "audi", "mo", "q2",        "Q2",         ["ice","die"]),
    ("audi", "audi", "mo", "q3",        "Q3",         ["ice","die","hybrid"]),
    ("audi", "audi", "mo", "q4-e-tron", "Q4 e-tron",  ["bev"]),
    ("audi", "audi", "mo", "q5",        "Q5",         ["ice","die","hybrid"]),
    ("audi", "audi", "mo", "q7",        "Q7",         ["ice","die","hybrid"]),
    ("audi", "audi", "mo", "q8",        "Q8",         ["ice","die","hybrid"]),
    ("audi", "audi", "mo", "e-tron",    "e-tron",     ["bev"]),
    ("audi", "audi", "mo", "tt",        "TT",         ["ice"]),
    # ── BMW — préfixe "mg" confirmé pour les séries numérotées ───────────────
    ("bmw", "bmw", "mg", "1-series",  "Série 1",  ["ice","die","hybrid"]),
    ("bmw", "bmw", "mg", "2-series",  "Série 2",  ["ice","die","hybrid"]),
    ("bmw", "bmw", "mg", "3-series",  "Série 3",  ["ice","die","hybrid"]),
    ("bmw", "bmw", "mg", "4-series",  "Série 4",  ["ice","die","hybrid"]),
    ("bmw", "bmw", "mg", "5-series",  "Série 5",  ["ice","die","hybrid"]),
    ("bmw", "bmw", "mg", "7-series",  "Série 7",  ["ice","hybrid"]),
    ("bmw", "bmw", "mg", "8-series",  "Série 8",  ["ice","die","hybrid"]),
    ("bmw", "bmw", "mo", "x1",    "X1",   ["ice","die","hybrid","bev"]),
    ("bmw", "bmw", "mo", "x2",    "X2",   ["ice","die","hybrid","bev"]),
    ("bmw", "bmw", "mo", "x3",    "X3",   ["ice","die","hybrid"]),
    ("bmw", "bmw", "mo", "x4",    "X4",   ["ice","die","hybrid"]),
    ("bmw", "bmw", "mo", "x5",    "X5",   ["ice","die","hybrid"]),
    ("bmw", "bmw", "mo", "x6",    "X6",   ["ice","die","hybrid"]),
    ("bmw", "bmw", "mo", "x7",    "X7",   ["ice","die","hybrid"]),
    ("bmw", "bmw", "mo", "ix",    "iX",   ["bev"]),
    ("bmw", "bmw", "mo", "ix1",   "iX1",  ["bev"]),
    ("bmw", "bmw", "mo", "i4",    "i4",   ["bev"]),
    ("bmw", "bmw", "mo", "i5",    "i5",   ["bev"]),
    ("bmw", "bmw", "mo", "m3",    "M3",   ["ice"]),
    ("bmw", "bmw", "mo", "m4",    "M4",   ["ice"]),
    # ── MERCEDES — slugs à vérifier (probablement mg- pour les classes) ───────
    ("mercedes", "mercedes-benz", "mg", "a-class", "Classe A",  ["ice","die","hybrid"]),
    ("mercedes", "mercedes-benz", "mg", "b-class", "Classe B",  ["ice","die","hybrid"]),
    ("mercedes", "mercedes-benz", "mg", "c-class", "Classe C",  ["ice","die","hybrid"]),
    ("mercedes", "mercedes-benz", "mg", "e-class", "Classe E",  ["ice","die","hybrid"]),
    ("mercedes", "mercedes-benz", "mg", "s-class", "Classe S",  ["ice","hybrid"]),
    ("mercedes", "mercedes-benz", "mg", "cla-class",      "CLA",       ["ice","hybrid"]),
    ("mercedes", "mercedes-benz", "mg", "gla-class",      "GLA",       ["ice","die","hybrid"]),
    ("mercedes", "mercedes-benz", "mg", "glb-class",      "GLB",       ["ice","die","hybrid"]),
    ("mercedes", "mercedes-benz", "mg", "glc-class",      "GLC",       ["ice","die","hybrid"]),
    ("mercedes", "mercedes-benz", "mg", "gle-class",      "GLE",       ["ice","die","hybrid"]),
    ("mercedes", "mercedes-benz", "mg", "gls-class",      "GLS",       ["ice","hybrid"]),
    ("mercedes", "mercedes-benz", "mg", "eqa",      "EQA",       ["bev"]),
    ("mercedes", "mercedes-benz", "mg", "eqb",      "EQB",       ["bev"]),
    ("mercedes", "mercedes-benz", "mg", "eqc",      "EQC",       ["bev"]),
    ("mercedes", "mercedes-benz", "mg", "eqe",      "EQE",       ["bev"]),
    ("mercedes", "mercedes-benz", "mg", "eqs",      "EQS",       ["bev"]),
    # ── SKODA ─────────────────────────────────────────────────────────────────
    ("skoda", "skoda", "mo", "fabia",    "Fabia",    ["ice"]),
    ("skoda", "skoda", "mo", "octavia",  "Octavia",  ["ice","die","hybrid"]),
    ("skoda", "skoda", "mo", "superb",   "Superb",   ["ice","die","hybrid"]),
    ("skoda", "skoda", "mo", "karoq",    "Karoq",    ["ice","die"]),
    ("skoda", "skoda", "mo", "kodiaq",   "Kodiaq",   ["ice","die","hybrid"]),
    ("skoda", "skoda", "mo", "kamiq",    "Kamiq",    ["ice"]),
    ("skoda", "skoda", "mo", "enyaq-iv", "Enyaq iV", ["bev"]),
    ("skoda", "skoda", "mo", "scala",    "Scala",    ["ice"]),
    # ── SEAT / CUPRA ──────────────────────────────────────────────────────────
    ("seat",  "seat",  "mo", "ibiza",    "Ibiza",     ["ice"]),
    ("seat",  "seat",  "mo", "leon",     "Leon",      ["ice","die","hybrid"]),
    ("seat",  "seat",  "mo", "arona",    "Arona",     ["ice"]),
    ("seat",  "seat",  "mo", "ateca",    "Ateca",     ["ice","die"]),
    ("cupra", "cupra", "mo", "formentor","Formentor", ["ice","hybrid"]),
    ("cupra", "cupra", "mo", "born",     "Born",      ["bev"]),
    ("cupra", "cupra", "mo", "ateca",    "Ateca",     ["ice","hybrid"]),
    # ── PEUGEOT ───────────────────────────────────────────────────────────────
    ("peugeot", "peugeot", "mo", "208",    "208",    ["ice","die"]),
    ("peugeot", "peugeot", "mo", "308",    "308",    ["ice","die","hybrid"]),
    ("peugeot", "peugeot", "mo", "2008",   "2008",   ["ice","die"]),
    ("peugeot", "peugeot", "mo", "3008",   "3008",   ["ice","die","hybrid"]),
    ("peugeot", "peugeot", "mo", "5008",   "5008",   ["ice","die","hybrid"]),
    ("peugeot", "peugeot", "mo", "408",    "408",    ["ice","hybrid"]),
    ("peugeot", "peugeot", "mo", "208",   "e-208",  ["bev"]),
    ("peugeot", "peugeot", "mo", "2008",  "e-2008", ["bev"]),
    ("peugeot", "peugeot", "mo", "308",   "e-308",  ["bev"]),
    # ── RENAULT ───────────────────────────────────────────────────────────────
    ("renault", "renault", "mo", "clio",    "Clio",    ["ice","hybrid"]),
    ("renault", "renault", "mo", "megane",  "Megane",  ["ice","die","hybrid","bev"]),
    ("renault", "renault", "mo", "captur",  "Captur",  ["ice","hybrid"]),
    ("renault", "renault", "mo", "austral", "Austral", ["ice","hybrid"]),
    ("renault", "renault", "mo", "arkana",  "Arkana",  ["ice","hybrid"]),
    ("renault", "renault", "mo", "scenic",  "Scenic",  ["bev"]),
    ("renault", "renault", "mo", "zoe",     "Zoe",     ["bev"]),
    # ── TOYOTA — slug confirmé: rav-4 ─────────────────────────────────────────
    ("toyota", "toyota", "mo", "yaris",       "Yaris",       ["ice","hybrid"]),
    ("toyota", "toyota", "mo", "yaris-cross", "Yaris Cross", ["hybrid"]),
    ("toyota", "toyota", "mo", "corolla",     "Corolla",     ["ice","hybrid"]),
    ("toyota", "toyota", "mo", "rav-4",       "RAV4",        ["ice","hybrid"]),
    ("toyota", "toyota", "mo", "c-hr",         "C-HR",        ["ice","hybrid"]),
    ("toyota", "toyota", "mo", "camry",       "Camry",       ["hybrid"]),
    ("toyota", "toyota", "mo", "highlander",  "Highlander",  ["hybrid"]),
    ("toyota", "toyota", "mo", "bz4x",        "bZ4X",        ["bev"]),
    ("toyota", "toyota", "mo", "supra",       "Supra",       ["ice"]),
    # ── HYUNDAI ───────────────────────────────────────────────────────────────
    ("hyundai", "hyundai", "mo", "i20",      "i20",      ["ice"]),
    ("hyundai", "hyundai", "mo", "i30",      "i30",      ["ice","die","hybrid"]),
    ("hyundai", "hyundai", "mo", "tucson",   "Tucson",   ["ice","die","hybrid"]),
    ("hyundai", "hyundai", "mo", "santa-fe", "Santa Fe", ["die","hybrid"]),
    ("hyundai", "hyundai", "mo", "ioniq-5",  "IONIQ 5",  ["bev"]),
    ("hyundai", "hyundai", "mo", "ioniq-6",  "IONIQ 6",  ["bev"]),
    ("hyundai", "hyundai", "mo", "kona",     "Kona",     ["ice","bev"]),
    # ── KIA ───────────────────────────────────────────────────────────────────
    ("kia", "kia", "mo", "picanto",  "Picanto",  ["ice"]),
    ("kia", "kia", "mo", "stonic",   "Stonic",   ["ice"]),
    ("kia", "kia", "mo", "sportage", "Sportage", ["ice","die","hybrid"]),
    ("kia", "kia", "mo", "sorento",  "Sorento",  ["die","hybrid"]),
    ("kia", "kia", "mo", "ev6",      "EV6",      ["bev"]),
    ("kia", "kia", "mo", "niro",     "Niro",     ["hybrid","bev"]),
    # ── FORD ──────────────────────────────────────────────────────────────────
    ("ford", "ford", "mo", "fiesta",         "Fiesta",        ["ice"]),
    ("ford", "ford", "mo", "focus",          "Focus",         ["ice","die","hybrid"]),
    ("ford", "ford", "mo", "puma",           "Puma",          ["ice","hybrid"]),
    ("ford", "ford", "mo", "kuga",           "Kuga",          ["ice","die","hybrid"]),
    ("ford", "ford", "mo", "mustang",        "Mustang",       ["ice"]),
    ("ford", "ford", "mo", "mustang-mach-e", "Mustang Mach-E",["bev"]),
    # ── OPEL ──────────────────────────────────────────────────────────────────
    ("opel", "opel", "mo", "corsa",    "Corsa",    ["ice","bev"]),
    ("opel", "opel", "mo", "astra",    "Astra",    ["ice","hybrid"]),
    ("opel", "opel", "mo", "mokka",    "Mokka",    ["ice","bev"]),
    ("opel", "opel", "mo", "grandland","Grandland",["ice","hybrid"]),
    # ── TESLA ─────────────────────────────────────────────────────────────────
    ("tesla", "tesla", "mo", "model-3", "Model 3", ["bev"]),
    ("tesla", "tesla", "mo", "model-y", "Model Y", ["bev"]),
    ("tesla", "tesla", "mo", "model-s", "Model S", ["bev"]),
    ("tesla", "tesla", "mo", "model-x", "Model X", ["bev"]),
    # ── VOLVO ─────────────────────────────────────────────────────────────────
    ("volvo", "volvo", "mo", "xc40", "XC40", ["ice","die","hybrid","bev"]),
    ("volvo", "volvo", "mo", "xc60", "XC60", ["ice","die","hybrid"]),
    ("volvo", "volvo", "mo", "xc90", "XC90", ["ice","hybrid"]),
    ("volvo", "volvo", "mo", "v60",  "V60",  ["ice","die","hybrid"]),
    ("volvo", "volvo", "mo", "v90",  "V90",  ["ice","die","hybrid"]),
    ("volvo", "volvo", "mo", "ex30", "EX30", ["bev"]),
    ("volvo", "volvo", "mo", "ex40", "EX40", ["bev"]),
    ("volvo", "volvo", "mo", "ec40", "EC40", ["bev"]),
    # ── MINI ──────────────────────────────────────────────────────────────────
    ("mini", "mini", "mo", "mini",       "Mini",       ["ice","bev"]),
    ("mini", "mini", "mo", "countryman", "Countryman", ["ice","hybrid","bev"]),
    # ── CITROEN ───────────────────────────────────────────────────────────────
    ("citroen", "citroen", "mo", "c3",          "C3",          ["ice"]),
    ("citroen", "citroen", "mo", "c4",          "C4",          ["ice","bev"]),
    ("citroen", "citroen", "mo", "c5-aircross", "C5 Aircross", ["ice","die","hybrid"]),
    ("citroen", "citroen", "mo", "berlingo",    "Berlingo",    ["ice","die","bev"]),
    # ── DACIA ─────────────────────────────────────────────────────────────────
    ("dacia", "dacia", "mo", "sandero", "Sandero", ["ice"]),
    ("dacia", "dacia", "mo", "duster",  "Duster",  ["ice","hybrid"]),
    ("dacia", "dacia", "mo", "jogger",  "Jogger",  ["ice"]),
    ("dacia", "dacia", "mo", "spring",  "Spring",  ["bev"]),
    # ── HONDA ─────────────────────────────────────────────────────────────────
    ("honda", "honda", "mo", "civic", "Civic", ["ice","hybrid"]),
    ("honda", "honda", "mo", "cr-v",  "CR-V",  ["ice","hybrid"]),
    ("honda", "honda", "mo", "hr-v",  "HR-V",  ["hybrid"]),
    ("honda", "honda", "mo", "jazz",  "Jazz",  ["hybrid"]),
    ("honda", "honda", "mo", "zr-v",  "ZR-V",  ["hybrid"]),
    # ── MAZDA ─────────────────────────────────────────────────────────────────
    ("mazda", "mazda", "mo", "2", "Mazda2", ["ice"]),
    ("mazda", "mazda", "mo", "3", "Mazda3", ["ice","hybrid"]),
    ("mazda", "mazda", "mo", "cx-30",  "CX-30",  ["ice","hybrid"]),
    ("mazda", "mazda", "mo", "cx-5",   "CX-5",   ["ice","die"]),
    ("mazda", "mazda", "mo", "mx-30",  "MX-30",  ["bev"]),
    # ── NISSAN ────────────────────────────────────────────────────────────────
    ("nissan", "nissan", "mo", "juke",    "Juke",    ["ice","hybrid"]),
    ("nissan", "nissan", "mo", "qashqai", "Qashqai", ["ice","hybrid"]),
    ("nissan", "nissan", "mo", "x-trail", "X-Trail", ["ice","hybrid"]),
    ("nissan", "nissan", "mo", "leaf",    "Leaf",    ["bev"]),
    ("nissan", "nissan", "mo", "ariya",   "Ariya",   ["bev"]),
    # ── PORSCHE ───────────────────────────────────────────────────────────────
    ("porsche", "porsche", "mo", "cayenne",  "Cayenne",  ["ice","hybrid"]),
    ("porsche", "porsche", "mo", "macan",    "Macan",    ["ice","hybrid","bev"]),
    ("porsche", "porsche", "mo", "panamera", "Panamera", ["ice","hybrid"]),
    ("porsche", "porsche", "mo", "taycan",   "Taycan",   ["bev"]),
    ("porsche", "porsche", "mo", "911",      "911",      ["ice"]),
    # ── LAND ROVER ────────────────────────────────────────────────────────────
    ("landrover", "land-rover", "mo", "defender",           "Defender",          ["ice","die","hybrid"]),
    ("landrover", "land-rover", "mo", "discovery",          "Discovery",         ["die","hybrid"]),
    ("landrover", "land-rover", "mo", "range-rover",        "Range Rover",       ["ice","die","hybrid"]),
    ("landrover", "land-rover", "mo", "range-rover-sport",  "Range Rover Sport", ["ice","die","hybrid"]),
    ("landrover", "land-rover", "mo", "range-rover-evoque", "Range Rover Evoque",["ice","die","hybrid"]),
    ("landrover", "land-rover", "mo", "range-rover-velar",  "Range Rover Velar", ["ice","die","hybrid"]),
    # ── LEXUS ─────────────────────────────────────────────────────────────────
    ("lexus", "lexus", "mo", "ux", "UX", ["hybrid"]),
    ("lexus", "lexus", "mo", "nx", "NX", ["hybrid"]),
    ("lexus", "lexus", "mo", "rx", "RX", ["hybrid"]),
    # ── FIAT ──────────────────────────────────────────────────────────────────
    ("fiat", "fiat", "mo", "500",  "500",  ["ice"]),
    ("fiat", "fiat", "mo", "500e", "500e", ["bev"]),
    ("fiat", "fiat", "mo", "500x", "500X", ["ice"]),
    ("fiat", "fiat", "mo", "tipo", "Tipo", ["ice"]),
    # ── DS ────────────────────────────────────────────────────────────────────
    ("ds", "ds-automobiles", "mo", "ds3", "DS 3", ["ice","hybrid","bev"]),
    ("ds", "ds-automobiles", "mo", "ds4", "DS 4", ["ice","hybrid"]),
    ("ds", "ds-automobiles", "mo", "ds7", "DS 7", ["ice","hybrid"]),
    # ── ALFA ROMEO ────────────────────────────────────────────────────────────
    ("alfa", "alfa-romeo", "mo", "giulia",  "Giulia",  ["ice","die"]),
    ("alfa", "alfa-romeo", "mo", "stelvio", "Stelvio", ["ice","die"]),
    ("alfa", "alfa-romeo", "mo", "tonale",  "Tonale",  ["ice","hybrid"]),
    # ── SUZUKI ────────────────────────────────────────────────────────────────
    ("suzuki", "suzuki", "mo", "swift",  "Swift",  ["ice","hybrid"]),
    ("suzuki", "suzuki", "mo", "vitara", "Vitara", ["ice","hybrid"]),
    ("suzuki", "suzuki", "mo", "sx4",    "SX4",    ["ice","hybrid"]),
    # ── MG ────────────────────────────────────────────────────────────────────
    ("mg", "mg", "mo", "mg3", "MG3", ["ice"]),
    ("mg", "mg", "mo", "mg4", "MG4", ["bev"]),
    ("mg", "mg", "mo", "mg-zs",  "ZS",  ["ice","bev"]),
    ("mg", "mg", "mo", "mg-hs",  "HS",  ["ice","hybrid"]),
    # ── BYD ───────────────────────────────────────────────────────────────────
    ("byd", "byd", "mo", "atto-3", "Atto 3", ["bev"]),
    ("byd", "byd", "mo", "seal",   "Seal",   ["bev"]),
    # ── POLESTAR ──────────────────────────────────────────────────────────────
    ("polestar", "polestar", "mo", "2", "Polestar 2", ["bev"]),
    ("polestar", "polestar", "mo", "4", "Polestar 4", ["bev"]),
    # ── JEEP ──────────────────────────────────────────────────────────────────
    ("jeep", "jeep", "mo", "renegade", "Renegade", ["ice","hybrid"]),
    ("jeep", "jeep", "mo", "compass",  "Compass",  ["ice","hybrid"]),
    ("jeep", "jeep", "mo", "avenger",  "Avenger",  ["ice","bev"]),
    # ── GENESIS ───────────────────────────────────────────────────────────────
    ("genesis", "genesis", "mo", "gv60", "GV60", ["bev"]),
    ("genesis", "genesis", "mo", "gv70", "GV70", ["ice","hybrid"]),
    ("genesis", "genesis", "mo", "gv80", "GV80", ["ice"]),
]
YEAR_FROM       = datetime.now().year - 5    # 2021
WINDOW_DAYS     = 120                         # Fenêtre d'enrichissement
MIN_N           = 2                           # Observations min pour une médiane
MAX_PAGES       = 4

COUNTRY_CONFIGS = {
    "fr": {"as24_domain": "autoscout24.fr",  "currency": "EUR"},
    "ch": {"as24_domain": "autoscout24.ch",  "currency": "CHF"},
    "de": {"as24_domain": "autoscout24.de",  "currency": "EUR"},
    "be": {"as24_domain": "autoscout24.be",  "currency": "EUR"},
}

# ── URL ───────────────────────────────────────────────────────────────────────
# Formats AS24 confirmés :
#   Occasion : firstRegistrationYearFrom=2021
#   Neuf     : conditionTypeGroups[0]=new (pas de yearFrom)
#   Hybrid   : fuelTypeGroups[0]=hybrid (query param, pas dans le path)
#   Pagination (1-indexé): pagination[page]=1 → page 2

FUEL_PATH = {
    "ice": "petrol",
    "die": "diesel",
    "bev": "electric",
}

def build_url(domain, model_prefix, model_slug, brand_slug, fuel_pt, page=1, new_mode=False):
    if new_mode:
        params = {"conditionTypeGroups[0]": "new"}
    else:
        params = {"firstRegistrationYearFrom": YEAR_FROM}

    if page > 1:
        params["pagination[page]"] = page - 1

    if fuel_pt == "hybrid":
        base = f"https://www.{domain}/fr/s/{model_prefix}-{model_slug}/mk-{brand_slug}"
        params["fuelTypeGroups[0]"] = "hybrid"
    else:
        ft = FUEL_PATH[fuel_pt]
        base = f"https://www.{domain}/fr/s/{model_prefix}-{model_slug}/mk-{brand_slug}/ft-{ft}"

    return f"{base}?{urlencode(params)}"

    return f"{base}?{urlencode(params)}"

# ── BROWSER ───────────────────────────────────────────────────────────────────

_driver = None

def get_driver():
    global _driver
    if _driver:
        return _driver
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
    except Exception:
        service = Service()
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_argument(f"--window-size={random.randint(1200,1920)},{random.randint(800,1080)}")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    _driver = webdriver.Chrome(service=service, options=opts)
    return _driver

def close_driver():
    global _driver
    if _driver:
        try: _driver.quit()
        except: pass
        _driver = None

def fetch_page(url, wait=5):
    driver = get_driver()
    try:
        time.sleep(random.uniform(2, 4))
        driver.get(url)
        time.sleep(wait + random.uniform(1, 2))
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight / 2);")
        time.sleep(random.uniform(1, 2))
        return driver.page_source
    except Exception as e:
        print(f" ⚠{e}")
        return None

# ── PARSER ────────────────────────────────────────────────────────────────────

def parse_listings(html, new_mode=False):
    if not html:
        return []
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    data_script = next((s for s in scripts if 'prefetchedListings' in s), None)
    if not data_script:
        return []
    unescaped = data_script.replace('\\"', '"').replace('\\\\', '\\')
    chunks = re.split(r'"conditionType"\s*:\s*"(?:used|new)"', unescaped)
    listings = []
    for chunk in chunks[1:]:
        price_m = (re.search(r'"price"\s*:\s*\{\s*"value"\s*:\s*(\d+)', chunk) or
                   re.search(r'"price"\s*:\s*(\d+)', chunk))
        year_m  = re.search(r'"firstRegistrationYear"\s*:\s*(\d{4})', chunk)
        km_m    = re.search(r'"mileage"\s*:\s*(\d+)', chunk)
        fuel_m  = re.search(r'"fuelType"\s*:\s*"([^"]+)"', chunk)
        price = int(price_m.group(1)) if price_m else None
        if not price or not (1000 < price < 600_000):
            continue
        year = int(year_m.group(1)) if year_m else None
        km   = int(km_m.group(1))   if km_m   else None
        if new_mode:
            # Filtrer les fausses annonces neuves : km > 500 ou année < 2025
            if km and km > 500:
                continue
            if year and year < 2025:
                continue
        else:
            if year and year < YEAR_FROM:
                continue
        listings.append({
            "price": price,
            "year":  year,
            "km":    km,
            "fuel":  fuel_m.group(1) if fuel_m else None,
        })
    return listings

# ── ÂGE ───────────────────────────────────────────────────────────────────────

def year_to_age(year):
    """Convertit une année d'immatriculation en âge entier au moment du scrape."""
    if not year:
        return None
    age = datetime.now().year - year
    return age if 0 <= age <= 10 else None

# ── ENRICHISSEMENT ────────────────────────────────────────────────────────────

def enrich_observations(existing_obs, new_prices_by_age, scrape_date_str):
    """
    Ajoute les nouvelles observations à la liste existante.
    Supprime les observations de plus de WINDOW_DAYS jours.
    Retourne la liste enrichie.

    existing_obs: {age_str: [{date, median, n}, ...]}
    new_prices_by_age: {age: [price, ...]}
    """
    cutoff = (date.today() - timedelta(days=WINDOW_DAYS)).isoformat()
    result = {}

    # Collecter tous les âges (existants + nouveaux)
    all_ages = set(existing_obs.keys()) | {str(a) for a in new_prices_by_age}

    for age_str in all_ages:
        # Garder observations existantes dans la fenêtre
        prev = [o for o in existing_obs.get(age_str, []) if o["date"] >= cutoff]

        # Ajouter nouvelle observation si assez de données
        age = int(age_str) if age_str != "new" else "new"
        if age in new_prices_by_age and len(new_prices_by_age[age]) >= MIN_N:
            prices = new_prices_by_age[age]
            prev.append({
                "date":   scrape_date_str,
                "median": int(median(prices)),
                "n":      len(prices),
                "min":    min(prices),
                "max":    max(prices),
            })

        if prev:
            result[age_str] = prev

    return result

def compute_current_median(observations):
    """
    Médiane de toutes les médianes dans la fenêtre → prix affiché dans CarPIQ.
    observations: [{date, median, n}, ...]
    """
    if not observations:
        return None
    all_medians = [o["median"] for o in observations]
    return int(median(all_medians))

# ── SCRAPE UN FUEL ────────────────────────────────────────────────────────────

def classify_hybrid(fuel_str):
    """Détermine HEV ou PHEV depuis le champ fuelType d'une annonce."""
    if not fuel_str:
        return "hev"
    f = fuel_str.lower()
    if "plug" in f or "rechargeable" in f or "phev" in f:
        return "phev"
    return "hev"

def scrape_model_fuel(model_prefix, model_slug, brand_slug, fuel_pt, domain, new_mode=False):
    """
    Scrape un modèle pour un carburant donné.
    new_mode=True : filtre conditionTypeGroups[0]=new, clé "new" au lieu d'un âge.
    Retourne {actual_fuel_pt: {age_or_"new": [prices]}}
    """
    raw = defaultdict(lambda: defaultdict(list))

    for page in range(1, MAX_PAGES + 1):
        url  = build_url(domain, model_prefix, model_slug, brand_slug, fuel_pt, page, new_mode)
        if page > 1:
            print(f"\n      p{page}", end=" ", flush=True)
        wait = 8 if page == 1 else 12
        html = fetch_page(url, wait=wait)

        if page > 1 and html:
            if 'prefetchedListings' not in html:
                print(f"[⚠ prefetchedListings absent]", end=" ", flush=True)

        page_listings = parse_listings(html, new_mode=new_mode)
        if not page_listings:
            if page > 1:
                print(f"→ 0 listings, stop")
            break
        print(f"p{page}({len(page_listings)})", end=" ", flush=True)
        for l in page_listings:
            if new_mode:
                age_key = "new"
            else:
                age_key = year_to_age(l["year"])
                if age_key is None:
                    continue
            if fuel_pt == "hybrid":
                actual_pt = classify_hybrid(l.get("fuel"))
            else:
                actual_pt = fuel_pt
            raw[actual_pt][age_key].append(l["price"])
        if page < MAX_PAGES:
            pause = random.uniform(25, 35)
            print(f" ⏳{pause:.0f}s", end=" ", flush=True)
            time.sleep(pause)
            close_driver()

    return {pt: dict(ages) for pt, ages in raw.items()}

# ── RUN ───────────────────────────────────────────────────────────────────────

def run_scraper(country="ch", output_file="prices_v6.json", models_subset=None, brand_filter=None, new_mode=False):
    country_cfg = COUNTRY_CONFIGS.get(country, COUNTRY_CONFIGS["ch"])
    domain = country_cfg["as24_domain"]

    models = models_subset or MODELS
    if brand_filter:
        models = [m for m in models if m[0] == brand_filter]

    today = date.today().isoformat()

    mode_label = "NEUF" if new_mode else f"OCCASION < 5 ans"
    print(f"\n{'='*65}")
    print(f"CarPIQ Price Scraper v6 — {country.upper()} — {mode_label}")
    if not new_mode:
        print(f"yearFrom: {YEAR_FROM} | Fenêtre: {WINDOW_DAYS}j | Modèles: {len(models)}")
    else:
        print(f"conditionTypeGroups=new | Modèles: {len(models)}")
    print(f"Démarré: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*65}")

    # Charger base existante
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            db = json.load(f)
        existing_count = sum(1 for v in db.get("models",{}).values() if v.get("fuels"))
        print(f"  ↻ Base existante: {existing_count} modèles avec données")
    except FileNotFoundError:
        db = {
            "meta": {
                "version":    "6.0",
                "country":    country,
                "currency":   country_cfg["currency"],
                "year_from":  YEAR_FROM,
                "window_days": WINDOW_DAYS,
            },
            "models": {},
        }

    total_requests = sum(len(m[5]) for m in models)
    print(f"  Requêtes prévues: ~{total_requests} ({len(models)} modèles × avg {total_requests//len(models)} fuels)")

    for i, (brand_id, brand_slug, model_prefix, model_slug, model_name, fuels) in enumerate(models):
        key = f"{brand_id}/{model_slug}"
        print(f"\n  [{i+1}/{len(models)}] {brand_id.upper()} {model_name} ({', '.join(fuels)})")

        existing_model = db["models"].get(key, {"brand": brand_id, "model": model_name, "fuels": {}})
        existing_fuels = existing_model.get("fuels", {})
        new_fuels = dict(existing_fuels)

        for fuel_pt in fuels:
            print(f"    {fuel_pt}...", end=" ", flush=True)
            try:
                results_by_fuel = scrape_model_fuel(model_prefix, model_slug, brand_slug, fuel_pt, domain, new_mode)
                n_total = sum(sum(len(p) for p in ages.values()) for ages in results_by_fuel.values())
                print(f"{n_total} annonces", end=" ")

                for actual_pt, by_age in results_by_fuel.items():
                    prev_obs = existing_fuels.get(actual_pt, {}).get("observations", {})
                    new_obs  = enrich_observations(prev_obs, by_age, today)
                    current  = {}
                    for age_str, obs in new_obs.items():
                        cm = compute_current_median(obs)
                        if cm:
                            current[age_str] = cm
                    new_fuels[actual_pt] = {
                        "observations": new_obs,
                        "current":      current,
                    }
                    print(f"→ {actual_pt} âges:{sorted(current.keys())}", end=" ")
                print()

            except Exception as e:
                print(f"✗ {e}")

            # Reset navigateur + pause entre chaque requête fuel
            close_driver()
            if fuel_pt != fuels[-1] or i < len(models) - 1:
                wait = random.uniform(30, 55)
                print(f"    ⏳ {wait:.0f}s...")
                time.sleep(wait)

        db["models"][key] = {
            "brand":  brand_id,
            "model":  model_name,
            "slug":   model_slug,
            "fuels":  new_fuels,
        }
        db["meta"]["last_scrape"] = today

        # Sauvegarde incrémentale
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)

    close_driver()
    print(f"\n{'='*65}")
    print(f"✅ Terminé → {output_file}")
    with_data = sum(1 for v in db["models"].values() if any(
        f.get("current") for f in v.get("fuels", {}).values()
    ))
    print(f"   Modèles avec données: {with_data}/{len(models)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CarPIQ Scraper v6 — Modèle × Carburant")
    parser.add_argument("--country", default="ch", choices=["fr","ch","de","be"])
    parser.add_argument("--output",  default="prices_v6.json")
    parser.add_argument("--test",    action="store_true", help="Golf, Model Y, RAV4, Série 3")
    parser.add_argument("--brand",   help="Une marque seulement (ex: vw, bmw)")
    parser.add_argument("--new",     action="store_true", help="Mode véhicule neuf (conditionTypeGroups=new)")
    args = parser.parse_args()

    if args.new and args.output == "prices_v6.json":
        args.output = "prices_new_v6.json"   # fichier séparé par défaut

    if args.test:
        subset = [
            ("vw",     "vw",     "mo", "golf",     "Golf",    ["ice","hybrid"]),
            ("tesla",  "tesla",  "mo", "model-y",  "Model Y", ["bev"]),
            ("toyota", "toyota", "mo", "rav-4",    "RAV4",    ["hybrid"]),
            ("bmw",    "bmw",    "mg", "3-series", "Série 3", ["ice","hybrid"]),
        ]
    else:
        subset = None

    run_scraper(args.country, args.output, subset, args.brand, new_mode=args.new)
