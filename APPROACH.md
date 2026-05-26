# Technical Approach

This document explains the modeling choices in the SMB Underwriting Simulator — not just what the code does, but why each decision was made and what it would take to run this in production.

---

## 1. Problem Framing: Why Point Estimates Fail

A typical revenue forecast produces one number: "next month, this merchant will earn ~$77K." A lender who sizes a loan off that number will be right on average — but average is the wrong target.

Lending is an asymmetric problem:
- If the merchant earns more than expected: no problem, they repay early.
- If the merchant earns less than expected: repayment stress, potential default.

The lender cares about the **left tail of the revenue distribution**, not the center. That means the right question is not "what will this merchant earn?" but "what is the worst-case revenue we should plan around?"

Quantile regression answers this directly by fitting separate models for P10, P50, and P90 — the 10th, 50th, and 90th percentiles of the outcome distribution. The P10 estimate becomes the underwriting anchor.

---

## 2. Revenue Forecasting

### Step 1: Seasonality Diagnosis

Before choosing a model, each merchant-store is characterized along two dimensions:

**Lag-12 autocorrelation:** `corr(revenue[t], revenue[t-12])`. A high value (> 0.50) signals that the same calendar month reliably repeats year-over-year — the merchant has a seasonal pattern worth exploiting.

**Month-of-year coefficient of variation:** The standard deviation of monthly averages divided by the grand mean. A high value (> 0.15) signals that some months are structurally different from others, even when history is too short to compute a lag-12 correlation.

If either condition triggers (and the merchant has ≥ 18 months of history), the baseline model is **seasonal naive** (same month last year). Otherwise, it defaults to a **rolling 3-month average**.

This two-signal approach handles the real heterogeneity in the data:
- Sushi (120 months): strong seasonal pattern → seasonal naive
- Sandwich (12 months) and coffee (6 months): too short for seasonal → rolling 3-month

### Step 2: Model Ladder

Three tiers of increasing complexity:

| Model | When used | How |
|-------|-----------|-----|
| Naive | Baseline only | Last observed month |
| Seasonal naive / rolling 3-month | Baseline | Diagnosed above |
| Quantile regression | ≥ 13 months of history | Fitted on all rows except last; last row is the "next month" prediction |

The quantile regression requires at least `min_train + 1 = 13` rows so there is at least one row left for prediction after the training window. Merchants with fewer months fall back to the ±20% heuristic around the rolling baseline.

### Feature Engineering

Features fed to the quantile regressors:

| Feature | Rationale |
|---------|-----------|
| `lag1`, `lag2`, `lag3` | Recent revenue level |
| `roll3`, `roll6` | Short- and medium-term trend |
| `vol3` | Recent revenue volatility (informs spread between P10/P90) |
| `month` | Residual seasonality not captured by lags |
| `tx_count_lag1`, `active_days_lag1`, `avg_order_value_lag1` | Leading operational signals |
| `is_sushi`, `is_coffee`, `is_sandwich` | Merchant-type fixed effects |

### Why `solver='highs'`?

scikit-learn's `QuantileRegressor` defaults to the interior-point solver, which can be slow and numerically unstable on small datasets. `highs` is the LP solver from HiGHS, substantially faster and more numerically robust for the dataset sizes here (6–120 rows of training data).

### Sushi Structural Break

Sushi revenue dropped ~40% during COVID (March 2020 – June 2021) and took 18 months to recover. Including the pre-COVID years as training data anchors the P10 estimate too conservatively — the model "remembers" the COVID floor even for 2024 forecasts. Notebook 03 shows this explicitly in the backtest. In production, a rolling training window (e.g., 48 most recent months) would avoid this.

---

## 3. Offer Sizing

### Why P10, Not P50?

P50 sizing is the expected case. P10 sizing ensures the merchant can repay from their worst realistic month — not just their average month. The trade-off: P10 produces smaller advances (lower revenue for the lender) but lower default risk.

**Formula:**
```
advance_amount = P10_monthly × TERM_MONTHS × advance_rate
fixed_fee      = advance_amount × factor_rate
total_payback  = advance_amount + fixed_fee
```

`TERM_MONTHS = 6` means we look at 6 months of downside-scenario revenue as the repayment capacity window. `advance_rate` controls what fraction of that capacity we lend against.

### Factor Rate vs. APR

Parafin uses a factor-rate model, not annual APR. The key difference: the fee is fixed at origination. There is no compounding, no penalty for early repayment, and the total obligation is transparent:

```
Total you owe = advance + (advance × factor_rate)
```

For comparison, effective APR = `(fixed_fee / advance) × (12 / TERM_MONTHS)`. This is disclosed in the app but not used for sizing.

### Risk Tiers

Three tiers based on data quality at the time of underwriting:

| Tier | Criteria | Factor rate | Advance rate |
|------|----------|-------------|-------------|
| A | QR fitted, ≥ 24 months, CV < 0.25 | 10% | 20% |
| B | QR fitted OR ≥ 12 months with CV < 0.40 | 14% | 15% |
| C | Short history (< 12 months), no QR | 18% | 10% |

The tighter advance rate at Tier C compensates for the fact that P10 estimates derived from heuristics (±20% of rolling average) are less reliable than model-fitted P10s. The higher factor rate prices in the additional model uncertainty.

---

## 4. Risk Monitoring

### Alert Thresholds

Post-issuance, each month's actual revenue is classified against the offer-time forecast:

| Status | Condition | Interpretation |
|--------|-----------|---------------|
| GREEN | actual ≥ 90% of P50 | Tracking to forecast |
| YELLOW | P10 ≤ actual < 90% of P50 | Below expected, but above worst case |
| RED | actual < P10 | Worse than the downside scenario |

The 90% buffer on GREEN (rather than exact P50) prevents hair-trigger yellows from normal month-to-month variance.

### Repricing Rule

```
RED month        → factor rate +2pp immediately
2× YELLOW (consecutive) → factor rate +1pp
Cap              → 24%
```

The RED rule is aggressive by design: if a merchant falls below P10 — the level at which we sized the advance — the underwriting assumption has been violated. Waiting to see if it recovers costs the lender more than an immediate reprice.

### Sushi Backtest

Notebook 03 runs a genuine out-of-sample test on sushi (M002):
- Training: Jan 2015 – Dec 2022 (96 months)
- Seasonal P10/P50/P90 bands: per-calendar-month empirical quantiles from training years
- Monitoring: Jan 2023 – Dec 2024 (24 actual months)

This shows whether the P10 band derived from historical seasonality holds up against real post-COVID recovery data.

---

## 5. Limitations and Production Gaps

| Limitation | Impact | Production fix |
|------------|--------|----------------|
| Single-step forecast (next month only) | Cannot size multi-year advances | Recursive multi-step QR or sequence models |
| Synthetic conversion model (70% base, −5pp per 1pp rate increase) | Expected profit numbers are illustrative, not calibrated | A/B test offer variants; fit elasticity from actual acceptance data |
| Synthetic default model (4% base rate + leverage multiplier) | Default probabilities are unvalidated | Calibrate against realized defaults in a holdout window |
| No macro features | Cannot anticipate recession-driven stress | Add industry indices, local economic indicators |
| Rolling 3-month / ±20% heuristic for short-history merchants | P10 estimates for coffee and sandwich are rough | Borrow strength from similar merchants (pooled QR) |
| Static training window for sushi | COVID-era data anchors P10 too conservatively | Rolling 48-month training window |

---

## 6. What Production Would Require

**Data pipeline:** Replace CSV load with a streaming feed from merchant banking integrations. Update `monthly_rev` incrementally each month rather than full recompute.

**Model management:** Version forecasts at issuance. When repricing, compare the current-month actual against the *original* forecast, not a re-fit model (otherwise the comparison baseline shifts).

**Continuous retraining:** Re-fit quantile models monthly with new outcomes. Track model calibration (are actual P10 outcomes below the P10 threshold exactly 10% of the time?).

**Portfolio-level optimization:** The per-merchant offer grid maximizes individual expected profit. A portfolio-level formulation would optimize across all merchants simultaneously, subject to capital constraints and concentration limits.

**Fairness audit:** Factor rates must not vary with protected characteristics. The current tiers (A/B/C) are driven entirely by data quality signals — but any future addition of merchant-type or location features requires a disparate-impact review.
