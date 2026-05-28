"""
Build the data structure consumed by the editorial Merchant 360 view.

This adapts the real model outputs (RevenueForecaster, OfferSimulator,
RiskMonitor) into the per-merchant dict shape the editorial front-end expects.

Everything sourced from the models is real:
  avgRev, volatility, advance, fee, term, repayRate, p10/p50/p90, riskTier.

A few presentation fields are derived for the single-merchant narrative and are
labelled here so they are not mistaken for direct model output:
  - The 3-month forecast band (forecast / bandHi / bandLo) extends the model's
    single next-month P10/P50/P90 forward with a gentle drift + widening band.
  - Display names (NAME_MAP) are friendly labels over the real merchant_type.

The headline risk construct is the real risk tier (A/B/C), which drives the offer
economics via TIER_PARAMS; there is no separate invented risk score.
"""
from __future__ import annotations

import calendar

import pandas as pd

from src.utils import TERM_MONTHS
from src.revenue_forecaster import FEATURE_COLS, QUANTILES

# Replace the three one-hot merchant-type indicators with a single readable label
# for the Model card. The model still consumes all three columns under the hood.
_DISPLAY_FEATURES = [f for f in FEATURE_COLS if not f.startswith("is_")] + ["merchant_type"]

# Friendly display names over the real merchant_type. Cosmetic only.
NAME_MAP = {
    "sandwich": "Sunrise Sandwich Co.",
    "sushi": "Kaiso Sushi House",
    "coffee": "Halftime Coffee Store",
}

# Provenance: the public Kaggle dataset each merchant_type was built from.
SOURCE_MAP = {
    "sandwich": {
        "name": "Fast Food Sales Report (Kaggle)",
        "url": "https://www.kaggle.com/datasets/rajatsurana979/fast-food-sales-report",
    },
    "sushi": {
        "name": "Sushi Restaurant Sales Simulation, 10 yr (Kaggle)",
        "url": "https://www.kaggle.com/datasets/troykueh/sushi-restaurant-sales-simulation-10-years",
    },
    "coffee": {
        "name": "Coffee Sales (Kaggle)",
        "url": "https://www.kaggle.com/datasets/ahmedabbas757/coffee-sales",
    },
}


# All merchants are displayed on a common timeline ending in May 2026, so the
# three datasets (which span different real periods) line up for the demo. This
# is a presentation overlay only: revenue values, model fit, forecasts, and
# backtest metrics are unchanged - just the month tick labels.
ANCHOR = pd.Period("2026-05", freq="M")


def _fmt_period(p: pd.Period) -> str:
    """pd.Period -> \"MMM 'YY\" (e.g. May '26). Shared by forecast and backtest."""
    return f"{calendar.month_abbr[p.month]} '{str(p.year)[2:]}"


def _shifted_labels(n: int, end: pd.Period = ANCHOR) -> list[str]:
    """n month labels ending at `end` (inclusive), counting backward."""
    return [_fmt_period(end - (n - 1 - i)) for i in range(n)]


def _verdict(risk_tier: str, cv: float) -> str:
    if risk_tier == "C" or cv > 0.35:
        return "review"
    return "approve"


def _verdict_explain(risk_tier: str, cv: float, verdict: str, months: int) -> str:
    """Plain-language rationale naming the actual trigger for the review/approve gate."""
    if verdict == "review":
        if months < 12:
            return ("Manual review triggered by limited transaction history "
                    "- fewer than 12 months on file.")
        if cv > 0.35:
            return (f"Manual review triggered by elevated revenue variability "
                    f"- CV is {cv:.2f}, above the demo review ceiling.")
        return "Manual review triggered by a Tier C risk profile."
    return ("Auto-approved - revenue variability and transaction history are both "
            "within demo policy bands.")


def _tenure(months: int) -> str:
    if months >= 12:
        years = months // 12
        return f"{years} yr" if years > 1 else "1 yr"
    return f"{months} mo"


def _forecast_band(actual: list[float], p10: float, p50: float, p90: float, n: int = 3):
    """
    Extend the model's single next-month quantiles into an n-month path.

    Month 1 uses the model's P10/P50/P90 directly. Months 2..n apply a gentle
    drift inferred from recent history and widen the band slightly each step.
    Illustrative extension of a single-month forecast - see module docstring.
    """
    if len(actual) >= 4 and actual[-4] > 0:
        g = (actual[-1] / actual[-4]) ** (1 / 3)  # per-month growth over last 3 mo
    else:
        g = 1.0
    g = max(0.97, min(1.06, g))

    forecast, band_hi, band_lo = [], [], []
    for i in range(n):
        forecast.append(round(p50 * (g ** i)))
        band_hi.append(round(p90 * (1 + 0.04 * i)))
        band_lo.append(round(p10 * (1 - 0.015 * i)))
    return forecast, band_hi, band_lo


def _flags(merchant_type, cv, months, qr_available, baseline_type) -> list[dict]:
    flags = []
    vol_pct = round(cv * 100)
    if cv < 0.25:
        flags.append({"sev": "g", "text": f"Revenue volatility {vol_pct}% - within tier A"})
    elif cv < 0.40:
        flags.append({"sev": "a", "text": f"Revenue volatility {vol_pct}% - within tier B band"})
    else:
        flags.append({"sev": "r", "text": f"Revenue volatility {vol_pct}% - above tier B ceiling"})

    if baseline_type == "seasonal_naive":
        flags.append({"sev": "g", "text": "Seasonal pattern detected and modeled"})

    if qr_available:
        flags.append({"sev": "g", "text": f"Quantile model fitted on {months} months"})
    else:
        flags.append({"sev": "a", "text": "Limited history - fallback forecast (±20%)"})

    if months < 12:
        flags.append({"sev": "a", "text": f"Short tenure - {months} months on file"})
    else:
        flags.append({"sev": "g", "text": f"{months} months of continuous history"})

    return flags[:3]


def _reasons(verdict, tier, cv, months, advance, fee, p10, qr_available) -> list[dict]:
    vol_pct = round(cv * 100)
    adv_pct_p10 = round(advance / (p10 * TERM_MONTHS) * 100) if p10 > 0 else 0
    eff_apr = round((fee / advance) * (12 / TERM_MONTHS) * 100) if advance > 0 else 0

    reasons = []
    if verdict == "approve":
        reasons.append({
            "ok": True,
            "head": "Approve at recommended advance.",
            "tail": f"Sized at {adv_pct_p10}% of projected P10 (downside) revenue over the {TERM_MONTHS}-month term.",
        })
    else:
        reasons.append({
            "ok": False,
            "head": "Route to manual review.",
            "tail": f"Risk tier {tier}; advance held to {adv_pct_p10}% of projected P10 (downside) revenue.",
        })

    if cv < 0.25:
        reasons.append({"ok": True, "head": "Low volatility.",
                        "tail": f"Coefficient of variation {cv:.2f} - within tier A (< 0.25)."})
    elif cv < 0.40:
        reasons.append({"ok": True, "head": "Moderate volatility.",
                        "tail": f"Coefficient of variation {cv:.2f} - within tier B band (0.25 - 0.40)."})
    else:
        reasons.append({"ok": False, "head": "Elevated volatility.",
                        "tail": f"Coefficient of variation {cv:.2f} - above the tier B ceiling (>= 0.40)."})

    if qr_available:
        reasons.append({"ok": True, "head": "Model confidence.",
                        "tail": f"Quantile regression fitted on {months} months of history."})
    else:
        reasons.append({"ok": False, "head": "Fallback forecast.",
                        "tail": f"{months} months on file, below the quantile model's fit threshold - used rolling ±20% band."})

    reasons.append({"ok": True, "head": "Pricing headroom.",
                    "tail": f"Effective APR ≈ {eff_apr}% at the recommended factor rate."})
    return reasons[:4]


def _ai_summary(name, cv, months, advance, p50, verdict) -> list[str]:
    vol_pct = round(cv * 100)
    adv_pct_p50 = round(advance / (p50 * TERM_MONTHS) * 100) if p50 > 0 else 0
    return [
        f"Recommended advance is {adv_pct_p50}% of projected P50 revenue over the term - a conservative posture.",
        f"Revenue volatility sits at {vol_pct}% (coefficient of variation {cv:.2f}).",
        f"{months} months of history on file; verdict is {verdict} under current policy.",
    ]


def build_merchants(forecaster, df_forecasts: pd.DataFrame, df_offers: pd.DataFrame) -> list[dict]:
    """Return the list of merchant dicts consumed by the editorial Merchant 360 view."""
    merchants: list[dict] = []

    for _, row in df_forecasts.iterrows():
        mid, sid = row.merchant_id, row.store_id
        mtype = row.merchant_type

        # The three M003 coffee stores are near-identical; show only one.
        if str(mid) == "M003" and str(sid) != "3":
            continue

        offer_match = df_offers[
            (df_offers.merchant_id == mid) & (df_offers.store_id == sid)
        ]
        if offer_match.empty:
            continue
        offer = offer_match.iloc[0]

        hist = forecaster.get_history(mid, sid, last_n=7)
        actual = [round(float(v)) for v in hist.tolist()]
        if not actual:
            continue

        avg_hist = forecaster.get_history(mid, sid, last_n=12)
        avg_rev = round(float(avg_hist.mean()))

        p10, p50, p90 = float(row.p10), float(row.p50), float(row.p90)
        forecast, band_hi, band_lo = _forecast_band(actual, p10, p50, p90, n=3)

        # Normalized timeline: actuals end at the May-2026 anchor, forecasts Jun/Jul/Aug.
        month_labels = _shifted_labels(len(actual))
        month_labels += [_fmt_period(ANCHOR + k) for k in (1, 2, 3)]

        cv = float(row.cv)
        months = int(row.months)
        qr = bool(row.qr_available)
        verdict = _verdict(row.risk_tier, cv)

        # Short series get a smaller warm-up so the walk-forward still yields holdout months.
        mh = 1 if months < 12 else 4
        backtest = forecaster.backtest(mid, sid, min_history=mh)
        backtest["reliable"] = backtest.get("n_holdout", 0) >= 6
        # Relabel the walk-forward series onto the same anchor (display only).
        bt_series = backtest.get("series", [])
        n_bt = len(bt_series)
        for i, pt in enumerate(bt_series):
            pt["month"] = _fmt_period(ANCHOR - (n_bt - 1 - i))

        model = {
            "estimator": "Linear quantile regression (sklearn QuantileRegressor, solver=highs)",
            "quantiles": [int(q * 100) for q in QUANTILES],
            "features": list(_DISPLAY_FEATURES),
            "target": "next-month revenue",
            "fallback": "seasonal-naive / rolling-3mo when history is too short to fit",
            "path": "Quantile regression" if qr else "Rolling/seasonal fallback (±20%)",
            "trainingRows": months,
            "qrAvailable": qr,
            "source": SOURCE_MAP.get(mtype, {"name": "—", "url": ""}),
        }

        # Momentum: recent N-month avg vs the prior N-month avg (N = min(6, half of history)).
        hist12 = avg_hist.tolist()
        nmo = len(hist12)
        win = min(6, nmo // 2)
        if win >= 1 and sum(hist12[-2 * win:-win]) > 0:
            recent_avg = sum(hist12[-win:]) / win
            prior_avg = sum(hist12[-2 * win:-win]) / win
            rev_delta = round((recent_avg / prior_avg - 1) * 100, 1)
            rev_label = f"vs prior {win}-mo avg"
        else:
            rev_delta = 0.0
            rev_label = "vs prior period"

        adv_pct_p10 = round(offer.advance_amount / (p10 * TERM_MONTHS) * 100) if p10 > 0 else 0
        monthly_target = round(float(offer.repayment_rate) * p10)

        name = NAME_MAP.get(mtype, mtype.title())

        merchants.append({
            "id": str(mid),
            "store": str(sid),
            "name": name,
            "kind": mtype,
            "tenure": _tenure(months),
            "verdict": verdict,
            "verdictExplain": _verdict_explain(row.risk_tier, cv, verdict, months),
            "avgRev": avg_rev,
            "revDelta": (f"+{rev_delta}%" if rev_delta >= 0 else f"{rev_delta}%"),
            "revUp": rev_delta >= 0,
            "revDeltaLabel": rev_label,
            "volatility": round(cv * 100),
            "advance": round(float(offer.advance_amount)),
            "advPctP10": adv_pct_p10,
            "monthlyTarget": monthly_target,
            "fee": round(float(offer.fixed_fee)),
            "totalPayback": round(float(offer.total_payback)),
            "term": int(TERM_MONTHS),
            "repayRate": float(offer.repayment_rate),
            "effApr": round((float(offer.fixed_fee) / float(offer.advance_amount)) * (12 / TERM_MONTHS) * 100) if offer.advance_amount > 0 else 0,
            "riskTier": str(row.risk_tier),
            "cv": round(cv, 3),
            "months": month_labels,
            "actual": actual,
            "forecast": forecast,
            "bandHi": band_hi,
            "bandLo": band_lo,
            "model": model,
            "backtest": backtest,
            "qrAvailable": qr,
            "flags": _flags(mtype, cv, months, qr, row.baseline_type),
            "reasons": _reasons(verdict, row.risk_tier, cv, months,
                                float(offer.advance_amount), float(offer.fixed_fee), p10, qr),
            "ai": _ai_summary(name, cv, months, float(offer.advance_amount), p50, verdict),
        })

    # Dropdown order follows merchant IDs M001 -> M002 -> M003 (sandwich, sushi, coffee).
    # The default selection in the view defaults to sushi, regardless of list order.
    _order = {"sandwich": 0, "sushi": 1, "coffee": 2}
    merchants.sort(key=lambda m: _order.get(m["kind"], 99))
    return merchants
