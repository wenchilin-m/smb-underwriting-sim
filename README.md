# SMB Underwriting Simulator

Quantile revenue forecasting → P10-anchored loan sizing → post-issuance risk monitoring.

Built as a demonstration of how SMB lenders can move beyond point-estimate revenue forecasts and model the *distribution* of outcomes — using the downside (P10) to size offers conservatively and the full P10/P50/P90 range to monitor portfolio risk post-issuance.

---

## Live Demo

> Deploy to Streamlit Community Cloud and paste the URL here.

---

## Quick Start

```bash
git clone https://github.com/<your-username>/smb-underwriting-sim
cd smb-underwriting-sim
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`.

---

## What It Does

**Tab 1 — Revenue Forecast**
Runs a two-step model per merchant-store: seasonality diagnosis (lag-12 autocorrelation + month-of-year CV) followed by a model ladder that escalates from naive → seasonal/rolling baseline → quantile regression. Produces P10, P50, and P90 next-month revenue estimates.

**Tab 2 — Offer Simulation**
Sizes the advance amount from P10 (so the merchant can repay even in a bad month), applies a risk-tiered factor rate, and sweeps an advance-rate × factor-rate grid to find the profit-maximizing configuration given estimated conversion and default probabilities.

**Tab 3 — Risk Monitoring**
Drag the revenue slider to simulate any post-issuance month. The alert system classifies the result as GREEN / YELLOW / RED against the P10 floor and P50 forecast, and the repricing engine adjusts the factor rate accordingly.

---

## Approach

SMB revenue is lumpy and seasonal. A lender who sizes a loan off the mean forecast will be right on average — and catastrophically wrong in bad months. P10 anchoring ensures the offer is serviceable at the 10th-percentile revenue scenario, not just the median.

See [APPROACH.md](APPROACH.md) for the full methodology: seasonality diagnosis, model ladder design, offer sizing logic, risk-tier thresholds, and what would be required to put this in production.

---

## Data

Three real merchant datasets combined into a single `merchant_transactions.csv` (~1.15M transaction rows):

| Merchant | Type | History | Source |
|----------|------|---------|--------|
| M001 | Sandwich shop | 12 months (Apr 2022 – Mar 2023) | Balaji Fast Food Sales |
| M002 | Sushi restaurant | 120 months (Jan 2015 – Dec 2024) | Kaggle sushi order dataset |
| M003 stores 3, 5, 8 | Coffee shops | 6 months (Jan – Jun 2023) | NYC Coffee Shop Sales |

The raw files are in `data/`. Notebook 01 combines and normalizes them; the export cell writes `data/merchant_transactions.csv` which `app.py` reads directly.

---

## Notebooks

Reproduce the full analysis step by step:

| Notebook | Description |
|----------|-------------|
| [01_revenue_forecasting.ipynb](notebooks/01_revenue_forecasting.ipynb) | EDA, seasonality diagnosis, model ladder → P10/P50/P90 per merchant-store |
| [02_offer_simulation.ipynb](notebooks/02_offer_simulation.ipynb) | P10-anchored loan sizing, risk tiers, offer grid simulation |
| [03_risk_monitoring.ipynb](notebooks/03_risk_monitoring.ipynb) | Sushi out-of-sample backtest (2015–2022 train, 2023–2024 monitor) + simulated alert system |

---

## Architecture

```
smb-underwriting-sim/
├── app.py                      # Streamlit app — 3-tab UI
├── requirements.txt
├── data/
│   └── merchant_transactions.csv
├── src/
│   ├── utils.py                # Shared constants: TIER_PARAMS, ALERT_COLORS, load_monthly_rev()
│   ├── revenue_forecaster.py   # RevenueForecaster: seasonality diagnosis + quantile regression
│   ├── offer_simulator.py      # OfferSimulator: base offers + advance×factor-rate grid
│   └── risk_monitor.py         # RiskMonitor: GREEN/YELLOW/RED classification + repricing
└── notebooks/
    ├── 01_revenue_forecasting.ipynb
    ├── 02_offer_simulation.ipynb
    └── 03_risk_monitoring.ipynb
```

`app.py` imports from `src/` and calls `streamlit run` at the repo root (required by Streamlit Cloud). Each `src/` module is a thin wrapper around the notebook logic — same math, callable interface.
