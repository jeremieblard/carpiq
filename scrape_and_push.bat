@echo off
:: ============================================================
:: CarPIQ — Scrape & Push automatique
:: Lance le scraper v6, commit et push sur GitHub
:: A planifier via Windows Task Scheduler
:: ============================================================

SET CARPIQ_DIR=C:\Users\XPS\Documents\carpiq
SET PYTHON=python3
SET LOG=%CARPIQ_DIR%\scrape_log.txt

echo. >> %LOG%
echo ============================================================ >> %LOG%
echo CarPIQ Scrape started: %date% %time% >> %LOG%
echo ============================================================ >> %LOG%

cd /d %CARPIQ_DIR%

:: ── GIT PULL avant de commencer ──────────────────────────────
echo [GIT] Pulling latest... >> %LOG%
git pull origin main --rebase >> %LOG% 2>&1

:: ============================================================
:: OCCASION CH — rotation par session
:: Décommente la session du jour et commente les autres
:: ============================================================

:: SESSION 1 — VAG (~2h)
:: echo [SCRAPE] Session 1 — VAG >> %LOG%
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand vw --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand audi --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand skoda --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand seat --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand cupra --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand porsche --output prices_v6.json >> %LOG% 2>&1

:: SESSION 2 — Premium (~1h)
:: echo [SCRAPE] Session 2 — Premium >> %LOG%
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand bmw --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand mercedes --output prices_v6.json >> %LOG% 2>&1

:: SESSION 3 — FR + JP (~2h)
:: echo [SCRAPE] Session 3 — FR+JP >> %LOG%
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand peugeot --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand renault --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand citroen --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand dacia --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand toyota --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand lexus --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand honda --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand mazda --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand suzuki --output prices_v6.json >> %LOG% 2>&1

:: SESSION 4 — Coréens + Divers (~2h)
:: echo [SCRAPE] Session 4 — Reste >> %LOG%
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand hyundai --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand kia --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand genesis --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand ford --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand opel --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand volvo --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand mini --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand tesla --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand nissan --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand mg --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand byd --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand polestar --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand landrover --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand alfa --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand fiat --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand ds --output prices_v6.json >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --brand jeep --output prices_v6.json >> %LOG% 2>&1

:: SESSION 5 — Neuf CH (~2h)
:: echo [SCRAPE] Session 5 — Neuf CH >> %LOG%
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --new --brand vw >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --new --brand bmw >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --new --brand mercedes >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --new --brand toyota >> %LOG% 2>&1
:: %PYTHON% carpiq_price_scraper_v6.py --country ch --new --brand tesla >> %LOG% 2>&1

:: ── GIT COMMIT + PUSH ─────────────────────────────────────────
echo [GIT] Committing results... >> %LOG%
git add prices_v6.json prices_new_v6.json 2>> %LOG%
git diff --staged --quiet
if errorlevel 1 (
    git commit -m "auto: scrape CH %date%" >> %LOG% 2>&1
    git push >> %LOG% 2>&1
    echo [GIT] Pushed successfully >> %LOG%
) else (
    echo [GIT] No changes to commit >> %LOG%
)

echo CarPIQ Scrape finished: %date% %time% >> %LOG%
echo. >> %LOG%
