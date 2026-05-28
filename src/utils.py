import pandas as pd

fmt_dollar = lambda x: f'${x:,.0f}'
fmt_pct    = lambda x: f'{x:.1%}'

ALERT_COLORS = {
    'GREEN':  '#2ca02c',
    'YELLOW': '#ff7f0e',
    'RED':    '#d62728',
}

TIER_PARAMS = {
    'A': {'factor_rate': 0.10, 'advance_rate': 0.20, 'repayment_rate': 0.10},
    'B': {'factor_rate': 0.14, 'advance_rate': 0.15, 'repayment_rate': 0.12},
    'C': {'factor_rate': 0.18, 'advance_rate': 0.10, 'repayment_rate': 0.15},
}

TERM_MONTHS = 6


def load_monthly_rev(csv_path: str = 'data/merchant_transactions.csv') -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'], format='mixed', dayfirst=False)
    df['year_month'] = df['date'].dt.to_period('M')
    monthly_rev = (
        df
        .groupby(['merchant_id', 'merchant_type', 'store_id', 'year_month'])
        .agg(
            monthly_revenue = ('transaction_amount', 'sum'),
            tx_count        = ('transaction_id',     'nunique'),
            active_days     = ('date',               lambda x: x.dt.date.nunique()),
            avg_order_value = ('transaction_amount', 'mean'),
        )
        .reset_index()
        .sort_values(['merchant_id', 'store_id', 'year_month'])
        .reset_index(drop=True)
    )
    return monthly_rev


def assign_risk_tier(months: int, cv: float, qr_available: bool) -> str:
    if qr_available and months >= 24 and cv < 0.25:
        return 'A'
    elif qr_available or (months >= 12 and cv < 0.40):
        return 'B'
    else:
        return 'C'
