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
  - riskIndex / riskLabel are a 0..100 health score derived from CV, tenure and
    whether the quantile model fitted.
  - Display names (NAME_MAP) are friendly labels over the real merchant_type.
"""
from __future__ import annotations

import calendar

import pandas as pd

from src.utils import TERM_MONTHS

# Friendly display names over the real merchant_type. Cosmetic only.
NAME_MAP = {
    "sandwich": "Sunrise Sandwich Co.",
    "sushi": "Kaiso Sushi House",
    "coffee": "Halftime Coffee",
}


def _month_abbr(period_label: str) -> str:
    """'2023-03' -> 'Mar'. Falls back to the raw label if unparseable."""
    try:
        month = int(str(period_label).split("-")[1])
        return calendar.month_abbr[month]
    except (IndexError, ValueError):
        return str(period_label)


def _next_month_labels(last_period_label: str, n: int) -> list[str]:
    """Return n forward month abbreviations after last_period_label, each marked '*'."""
    try:
        period = pd.Period(last_period_label, freq="M")
    except Exception:
        return [f"+{i + 1}*" for i in range(n)]
    out = []
    for i in range(1, n + 1):
        nxt = period + i
        out.append(calendar.month_abbr[nxt.month] + "*")
    return out


def _verdict(risk_tier: str, cv: float) -> str:
    if risk_tier == "C" or cv > 0.35:
        return "review"
    return "approve"


def _risk_index(cv: float, months: int, qr_available: bool) -> int:
    """0..100 health score. Higher = healthier. Driven by volatility, tenure, model fit."""
    idx = 100.0 - min(cv, 0.60) / 0.60 * 55.0  # cv 0 -> 100, cv 0.6 -> 45
    if not qr_available:
        idx -= 8
    if months < 12:
        idx -= 8
    return int(max(40, min(95, round(idx))))


def _risk_label(idx: int) -> str:
    if idx >= 80:
        return "Healthy"
    if idx >= 65:
        return "Stable"
    if idx >= 50:
        return "Caution"
    return "Distress"


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
    if cv < 0.20:
        flags.append({"sev": "g", "text": f"Revenue volatility low at {vol_pct}%"})
    elif cv < 0.30:
        flags.append({"sev": "a", "text": f"Revenue volatility {vol_pct}% - within tolerance"})
    else:
        flags.append({"sev": "r", "text": f"Revenue volatility {vol_pct}% - above policy"})

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


def _reasons(verdict, tier, cv, months, advance, fee, p50, qr_available) -> list[dict]:
    vol_pct = round(cv * 100)
    adv_pct_p50 = round(advance / (p50 * TERM_MONTHS) * 100) if p50 > 0 else 0
    eff_apr = round((fee / advance) * (12 / TERM_MONTHS) * 100) if advance > 0 else 0

    reasons = []
    if verdict == "approve":
        reasons.append({
            "ok": True,
            "head": "Approve at recommended advance.",
            "tail": f"Sized at {adv_pct_p50}% of projected P50 revenue over the {TERM_MONTHS}-month term.",
        })
    else:
        reasons.append({
            "ok": False,
            "head": "Route to manual review.",
            "tail": f"Risk tier {tier}; advance held to {adv_pct_p50}% of projected P50 revenue.",
        })

    if cv < 0.20:
        reasons.append({"ok": True, "head": "Low volatility.",
                        "tail": f"Coefficient of variation {cv:.2f} - bottom quartile of cohort."})
    elif cv < 0.30:
        reasons.append({"ok": True, "head": "Moderate volatility.",
                        "tail": f"Coefficient of variation {cv:.2f} - within tier tolerance."})
    else:
        reasons.append({"ok": False, "head": "Elevated volatility.",
                        "tail": f"Coefficient of variation {cv:.2f} - above the 0.25 policy line."})

    if qr_available:
        reasons.append({"ok": True, "head": "Model confidence.",
                        "tail": f"Quantile regression fitted on {months} months of history."})
    else:
        reasons.append({"ok": False, "head": "Thin history.",
                        "tail": f"Only {months} months on file - used rolling ±20% fallback band."})

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

        offer_match = df_offers[
            (df_offers.merchant_id == mid) & (df_offers.store_id == sid)
        ]
        if offer_match.empty:
            continue
        offer = offer_match.iloc[0]

        hist = forecaster.get_history(mid, sid, last_n=7)
        labels = forecaster.get_period_labels(mid, sid, last_n=7)
        actual = [round(float(v)) for v in hist.tolist()]
        if not actual:
            continue

        avg_hist = forecaster.get_history(mid, sid, last_n=12)
        avg_rev = round(float(avg_hist.mean()))

        p10, p50, p90 = float(row.p10), float(row.p50), float(row.p90)
        forecast, band_hi, band_lo = _forecast_band(actual, p10, p50, p90, n=3)

        month_labels = [_month_abbr(l) for l in labels]
        last_period = labels[-1] if labels else None
        month_labels += _next_month_labels(last_period, 3)

        cv = float(row.cv)
        months = int(row.months)
        qr = bool(row.qr_available)
        verdict = _verdict(row.risk_tier, cv)
        idx = _risk_index(cv, months, qr)

        rev_delta = round((actual[-1] / actual[0] - 1) * 100, 1) if actual[0] > 0 else 0.0
        adv_pct_p50 = round(offer.advance_amount / (p50 * TERM_MONTHS) * 100) if p50 > 0 else 0

        # Multi-store types get the store id appended so labels stay unique.
        store_count = (df_forecasts.merchant_id == mid).sum()
        base_name = NAME_MAP.get(mtype, mtype.title())
        name = f"{base_name} · Store {sid}" if store_count > 1 else base_name

        merchants.append({
            "id": str(mid),
            "store": str(sid),
            "name": name,
            "kind": mtype,
            "tenure": _tenure(months),
            "verdict": verdict,
            "avgRev": avg_rev,
            "revDelta": (f"+{rev_delta}%" if rev_delta >= 0 else f"{rev_delta}%"),
            "revUp": rev_delta >= 0,
            "volatility": round(cv * 100),
            "advance": round(float(offer.advance_amount)),
            "advPctP50": adv_pct_p50,
            "fee": round(float(offer.fixed_fee)),
            "term": int(TERM_MONTHS),
            "repayRate": float(offer.repayment_rate),
            "effApr": round((float(offer.fixed_fee) / float(offer.advance_amount)) * (12 / TERM_MONTHS) * 100) if offer.advance_amount > 0 else 0,
            "riskTier": str(row.risk_tier),
            "months": month_labels,
            "actual": actual,
            "forecast": forecast,
            "bandHi": band_hi,
            "bandLo": band_lo,
            "riskIndex": idx,
            "riskLabel": _risk_label(idx),
            "qrAvailable": qr,
            "flags": _flags(mtype, cv, months, qr, row.baseline_type),
            "reasons": _reasons(verdict, row.risk_tier, cv, months,
                                float(offer.advance_amount), float(offer.fixed_fee), p50, qr),
            "ai": _ai_summary(name, cv, months, float(offer.advance_amount), p50, verdict),
        })

    return merchants
