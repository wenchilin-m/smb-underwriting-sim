import pandas as pd

from src.utils import TIER_PARAMS, TERM_MONTHS, assign_risk_tier


def _est_conversion(factor_rate: float, tier_base_rate: float, base_conv: float = 0.70) -> float:
    delta_pct = (factor_rate - tier_base_rate) * 100
    return max(0.10, base_conv - delta_pct * 0.05)


def _est_default_prob(advance_amount: float, p10_monthly: float, base_default: float = 0.04) -> float:
    months_covered = advance_amount / p10_monthly if p10_monthly > 0 else TERM_MONTHS
    return min(0.40, base_default * (1 + max(0, months_covered - TERM_MONTHS) * 0.15))


class OfferSimulator:
    """Computes base offers and runs an advance-rate × factor-rate grid per merchant-store."""

    def __init__(self, df_forecasts: pd.DataFrame):
        self.df_forecasts = df_forecasts
        self._df_offers: pd.DataFrame | None = None
        self._df_grid:   pd.DataFrame | None = None

    def compute_base_offers(self) -> pd.DataFrame:
        if self._df_offers is not None:
            return self._df_offers

        rows = []
        for _, row in self.df_forecasts.iterrows():
            params = TIER_PARAMS[row.risk_tier]
            adv    = row.p10 * TERM_MONTHS * params['advance_rate']
            fee    = adv * params['factor_rate']
            pback  = adv + fee
            mpay   = row.p50 * params['repayment_rate']
            iterm  = adv / mpay if mpay > 0 else None
            eff_apr = (fee / adv) * (12 / TERM_MONTHS) if adv > 0 else None
            rows.append({
                'merchant_id'    : row.merchant_id,
                'merchant_type'  : row.merchant_type,
                'store_id'       : row.store_id,
                'risk_tier'      : row.risk_tier,
                'factor_rate'    : params['factor_rate'],
                'advance_rate'   : params['advance_rate'],
                'repayment_rate' : params['repayment_rate'],
                'advance_amount' : round(adv, 2),
                'fixed_fee'      : round(fee, 2),
                'total_payback'  : round(pback, 2),
                'monthly_payment': round(mpay, 2),
                'implied_term_mo': round(iterm, 1) if iterm else None,
                'eff_apr'        : round(eff_apr, 3) if eff_apr else None,
                'p10_monthly'    : row.p10,
                'p50_monthly'    : row.p50,
            })
        self._df_offers = pd.DataFrame(rows)
        return self._df_offers

    def simulate_grid(
        self,
        advance_rates: list[float] | None = None,
        factor_rates:  list[float] | None = None,
    ) -> pd.DataFrame:
        if self._df_grid is not None:
            return self._df_grid

        advance_rates = advance_rates or [0.05, 0.10, 0.15, 0.20, 0.25]
        factor_rates  = factor_rates  or [0.08, 0.10, 0.12, 0.14, 0.16, 0.18, 0.20]

        rows = []
        for _, row in self.df_forecasts.iterrows():
            tier_base = TIER_PARAMS[row.risk_tier]['factor_rate']
            for ar in advance_rates:
                for fr in factor_rates:
                    adv  = row.p10 * TERM_MONTHS * ar
                    fee  = adv * fr
                    conv = _est_conversion(fr, tier_base)
                    defp = _est_default_prob(adv, row.p10)
                    rows.append({
                        'merchant_id'   : row.merchant_id,
                        'merchant_type' : row.merchant_type,
                        'store_id'      : row.store_id,
                        'risk_tier'     : row.risk_tier,
                        'advance_rate'  : ar,
                        'factor_rate'   : fr,
                        'advance_amount': round(adv, 0),
                        'fixed_fee'     : round(fee, 0),
                        'total_payback' : round(adv + fee, 0),
                        'conv_prob'     : round(conv, 3),
                        'default_prob'  : round(defp, 3),
                        'exp_profit'    : round(conv * (fee - adv * defp), 0),
                    })
        self._df_grid = pd.DataFrame(rows)
        return self._df_grid

    def optimal_offers(self) -> pd.DataFrame:
        grid = self.simulate_grid()
        idx  = grid.groupby(['merchant_id', 'store_id'])['exp_profit'].idxmax()
        return grid.loc[idx].reset_index(drop=True)
