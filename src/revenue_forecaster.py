import warnings
import numpy as np
import pandas as pd
from sklearn.linear_model import QuantileRegressor

from src.utils import assign_risk_tier

warnings.filterwarnings('ignore')

QUANTILES = [0.10, 0.50, 0.90]
FEATURE_COLS = [
    'lag1', 'lag2', 'lag3',
    'roll3', 'roll6', 'vol3',
    'month',
    'tx_count_lag1', 'active_days_lag1', 'avg_order_value_lag1',
    'is_sushi', 'is_coffee', 'is_sandwich',
]


def _build_features(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy().reset_index(drop=True)
    rev = df['monthly_revenue']
    df['lag1']  = rev.shift(1)
    df['lag2']  = rev.shift(2)
    df['lag3']  = rev.shift(3)
    df['roll3'] = rev.shift(1).rolling(3).mean()
    df['roll6'] = rev.shift(1).rolling(6).mean()
    df['vol3']  = rev.shift(1).rolling(3).std()
    df['month'] = df['year_month'].dt.month
    for col in ['tx_count', 'active_days', 'avg_order_value']:
        df[f'{col}_lag1'] = df[col].shift(1) if col in df.columns else 0.0
    df['is_sushi']    = (df['merchant_type'] == 'sushi').astype(int)
    df['is_coffee']   = (df['merchant_type'] == 'coffee').astype(int)
    df['is_sandwich'] = (df['merchant_type'] == 'sandwich').astype(int)
    return df


def _quantile_forecast(data: pd.DataFrame, min_train: int = 12):
    df_feat = _build_features(data).dropna(subset=FEATURE_COLS + ['monthly_revenue'])
    if len(df_feat) < min_train + 1:
        return None
    X = df_feat[FEATURE_COLS]
    y = df_feat['monthly_revenue']
    X_tr, y_tr = X.iloc[:-1], y.iloc[:-1]
    X_pred = X.iloc[[-1]]
    preds = {}
    for q in QUANTILES:
        model = QuantileRegressor(quantile=q, alpha=0.01, solver='highs')
        model.fit(X_tr, y_tr)
        preds[f'p{int(q * 100)}'] = float(model.predict(X_pred)[0])
    return preds


def _diagnose_seasonality(df_m: pd.DataFrame, merchant_id: str, store_id: str):
    data = df_m[(df_m.merchant_id == merchant_id) & (df_m.store_id == store_id)].copy()
    data['month_num'] = data['year_month'].dt.month
    n = len(data)
    rev = data['monthly_revenue'].values
    lag12_corr = float(np.corrcoef(rev[:-12], rev[12:])[0, 1]) if n >= 24 else None
    mo_avg = data.groupby('month_num')['monthly_revenue'].mean()
    month_cv = float(mo_avg.std() / mo_avg.mean()) if mo_avg.mean() > 0 else 0.0
    is_seasonal = (
        n >= 18
        and ((lag12_corr is not None and lag12_corr > 0.50) or month_cv > 0.15)
    )
    return 'seasonal_naive' if is_seasonal else 'rolling_3mo', lag12_corr, month_cv


def _naive(series: pd.Series) -> float:
    return float(series.iloc[-1])


def _seasonal_naive(series: pd.Series, month_series: pd.Series) -> float:
    target = int(month_series.iloc[-1])
    same = series[month_series == target]
    if len(same) >= 2:
        return float(same.iloc[-2])
    return _rolling3(series)


def _rolling3(series: pd.Series) -> float:
    return float(series.iloc[-3:].mean())


class RevenueForecaster:
    """Runs the full model ladder for every merchant-store in monthly_rev_df."""

    def __init__(self, monthly_rev_df: pd.DataFrame):
        self.monthly_rev = monthly_rev_df
        self._df_forecasts: pd.DataFrame | None = None

    def fit_all(self) -> pd.DataFrame:
        if self._df_forecasts is not None:
            return self._df_forecasts

        merchant_stores = (
            self.monthly_rev[['merchant_id', 'merchant_type', 'store_id']]
            .drop_duplicates()
            .reset_index(drop=True)
        )
        rows = []
        for _, ms in merchant_stores.iterrows():
            mid, sid = ms['merchant_id'], ms['store_id']
            mask = (self.monthly_rev.merchant_id == mid) & (self.monthly_rev.store_id == sid)
            data = self.monthly_rev[mask].copy().reset_index(drop=True)
            rev  = data['monthly_revenue']
            moy  = data['year_month'].dt.month

            baseline_type, lag12_corr, month_cv = _diagnose_seasonality(
                self.monthly_rev, mid, sid
            )
            naive = _naive(rev)
            base  = (
                _seasonal_naive(rev, moy) if baseline_type == 'seasonal_naive'
                else _rolling3(rev)
            )
            qr = _quantile_forecast(data)
            n  = len(data)
            cv = float(rev.std() / rev.mean()) if rev.mean() > 0 else 0.0

            row = dict(
                merchant_id=mid, merchant_type=ms['merchant_type'], store_id=sid,
                months=n, cv=round(cv, 3),
                lag12_corr=round(lag12_corr, 3) if lag12_corr is not None else None,
                baseline_type=baseline_type,
                naive=round(naive, 2), baseline=round(base, 2),
                qr_available=qr is not None,
            )
            if qr:
                row['p10'] = round(max(qr['p10'], 0), 2)
                row['p50'] = round(max(qr['p50'], 0), 2)
                row['p90'] = round(max(qr['p90'], 0), 2)
            else:
                row['p10'] = round(base * 0.80, 2)
                row['p50'] = round(base,        2)
                row['p90'] = round(base * 1.20, 2)

            row['risk_tier'] = assign_risk_tier(n, cv, row['qr_available'])
            rows.append(row)

        self._df_forecasts = pd.DataFrame(rows)
        return self._df_forecasts

    def get_history(self, merchant_id: str, store_id: str, last_n: int = 12) -> pd.Series:
        mask = (
            (self.monthly_rev.merchant_id == merchant_id)
            & (self.monthly_rev.store_id == store_id)
        )
        return (
            self.monthly_rev[mask]
            .sort_values('year_month')['monthly_revenue']
            .iloc[-last_n:]
            .reset_index(drop=True)
        )

    def get_period_labels(self, merchant_id: str, store_id: str, last_n: int = 12) -> list[str]:
        mask = (
            (self.monthly_rev.merchant_id == merchant_id)
            & (self.monthly_rev.store_id == store_id)
        )
        return (
            self.monthly_rev[mask]
            .sort_values('year_month')['year_month']
            .astype(str)
            .iloc[-last_n:]
            .tolist()
        )
