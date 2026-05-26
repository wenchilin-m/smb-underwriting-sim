import pandas as pd


def classify_alert(actual_rev: float, p10: float, p50: float) -> str:
    if actual_rev >= p50 * 0.90:
        return 'GREEN'
    elif actual_rev >= p10:
        return 'YELLOW'
    else:
        return 'RED'


class RiskMonitor:
    """Post-issuance revenue monitoring and repricing logic."""

    def __init__(self, monthly_rev_df: pd.DataFrame, df_offers: pd.DataFrame):
        self.monthly_rev = monthly_rev_df
        self.df_offers   = df_offers

    def get_seasonal_bands(
        self,
        merchant_id: str,
        store_id: str,
        train_end_period: str,
    ) -> pd.DataFrame:
        """P10 / P50 / P90 per calendar month derived from training history."""
        mask = (
            (self.monthly_rev.merchant_id == merchant_id)
            & (self.monthly_rev.store_id == store_id)
            & (self.monthly_rev.year_month <= train_end_period)
        )
        train = self.monthly_rev[mask].copy()
        train['month_num'] = train['year_month'].dt.month
        return (
            train.groupby('month_num')['monthly_revenue']
            .agg(
                p10=lambda x: x.quantile(0.10),
                p50=lambda x: x.quantile(0.50),
                p90=lambda x: x.quantile(0.90),
            )
            .reset_index()
        )

    def get_offer_rate(self, merchant_id: str, store_id: str) -> float:
        mask = (
            (self.df_offers.merchant_id == merchant_id)
            & (self.df_offers.store_id == store_id)
        )
        matched = self.df_offers[mask]
        if matched.empty:
            return 0.14
        return float(matched.iloc[0]['factor_rate'])

    def reprice(self, current_rate: float, alert_history: list[str]) -> dict:
        """
        Returns suggested factor rate and reason.
        alert_history: list of recent alert strings, most recent last.
        """
        rate    = current_rate
        reasons = []
        consec_yellow = 0

        for alert in alert_history:
            if alert == 'RED':
                rate = min(0.24, rate + 0.02)
                reasons.append('RED month (+2pp)')
                consec_yellow = 0
            elif alert == 'YELLOW':
                consec_yellow += 1
                if consec_yellow >= 2:
                    rate = min(0.24, rate + 0.01)
                    reasons.append('2 consecutive YELLOW months (+1pp)')
            else:
                consec_yellow = 0

        return {
            'suggested_rate': round(rate, 3),
            'adjustment'    : round(rate - current_rate, 3),
            'reasons'       : reasons if reasons else ['No adjustment needed'],
        }

    def build_monitoring_table(
        self,
        merchant_id: str,
        store_id: str,
        current_revenue: float,
        p10: float,
        p50: float,
        history_window: int = 12,
    ) -> pd.DataFrame:
        """Return a DataFrame of historical months + current month with alert status."""
        mask = (
            (self.monthly_rev.merchant_id == merchant_id)
            & (self.monthly_rev.store_id == store_id)
        )
        hist = (
            self.monthly_rev[mask]
            .sort_values('year_month')
            .tail(history_window)
            .copy()
        )
        hist['alert'] = hist['monthly_revenue'].apply(
            lambda r: classify_alert(r, p10, p50)
        )
        current_row = pd.DataFrame([{
            'year_month'    : 'Forecast month',
            'monthly_revenue': current_revenue,
            'alert'         : classify_alert(current_revenue, p10, p50),
        }])
        return pd.concat([hist[['year_month', 'monthly_revenue', 'alert']], current_row],
                         ignore_index=True)
