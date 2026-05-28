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

    @staticmethod
    def _fallback_value(rev_hist, moy_hist, target_month, seasonal_only: bool = False):
        """Serving-style fallback using only past data.

        Returns the same-calendar-month prior value if available (seasonal naive),
        otherwise the rolling 3-month mean. With seasonal_only=True returns the
        seasonal value or None (used to score a pure seasonal-naive baseline).
        """
        if len(rev_hist) == 0:
            return None
        same = rev_hist[moy_hist == target_month]
        if len(same) >= 1:
            return float(same[-1])
        if seasonal_only:
            return None
        return float(np.mean(rev_hist[-3:]))

    def backtest(self, merchant_id: str, store_id: str, min_history: int = 4) -> dict:
        """Rolling-origin (walk-forward) out-of-sample evaluation for one merchant-store.

        For each origin t in [min_history, N): train only on months [0:t] and predict
        month t. Uses the quantile-regression model where it can fit, otherwise the same
        serving fallback (seasonal-naive / rolling-3mo) production would use. Scores P50
        point accuracy, P10-P90 band coverage, pinball loss, and skill vs naive and
        seasonal-naive baselines. No look-ahead: each prediction sees only its past.
        """
        mask = (
            (self.monthly_rev.merchant_id == merchant_id)
            & (self.monthly_rev.store_id == store_id)
        )
        data = self.monthly_rev[mask].sort_values('year_month').reset_index(drop=True)
        n = len(data)
        rev = data['monthly_revenue'].to_numpy(dtype=float)
        moy = data['year_month'].dt.month.to_numpy()
        labels = data['year_month'].astype(str).tolist()

        if n <= min_history:
            return {
                'n_holdout': 0,
                'series': [],
                'note': (f'Only {n} months on file; need more than {min_history} '
                         'for a walk-forward backtest.'),
            }

        series, naive_preds, seas_preds = [], [], []
        qr_pts = fb_pts = 0
        for t in range(min_history, n):
            upto = data.iloc[0:t + 1]              # train on [0:t], predict month t
            qr = _quantile_forecast(upto)
            if qr is not None:
                p10, p50, p90 = max(qr['p10'], 0.0), max(qr['p50'], 0.0), max(qr['p90'], 0.0)
                method = 'QR'
                qr_pts += 1
            else:
                base = self._fallback_value(rev[:t], moy[:t], moy[t])
                if base is None:
                    continue
                p10, p50, p90 = base * 0.80, base, base * 1.20
                method = 'fallback'
                fb_pts += 1

            p10, p50, p90 = sorted([p10, p50, p90])
            naive = rev[t - 1]
            seas = self._fallback_value(rev[:t], moy[:t], moy[t], seasonal_only=True)
            naive_preds.append(naive)
            seas_preds.append(seas if seas is not None else naive)
            series.append({
                'month': labels[t],
                'actual': round(float(rev[t])),
                'p10': round(float(p10)),
                'p50': round(float(p50)),
                'p90': round(float(p90)),
                'method': method,
            })

        if not series:
            return {
                'n_holdout': 0,
                'series': [],
                'note': 'No scorable out-of-sample months after feature construction.',
            }

        actual = np.array([s['actual'] for s in series], dtype=float)
        p10 = np.array([s['p10'] for s in series], dtype=float)
        p50 = np.array([s['p50'] for s in series], dtype=float)
        p90 = np.array([s['p90'] for s in series], dtype=float)
        naive = np.array(naive_preds, dtype=float)
        seas = np.array(seas_preds, dtype=float)

        def _mae(a, b):
            return float(np.mean(np.abs(a - b)))

        def _pinball(y, pred, q):
            d = y - pred
            return float(np.mean(np.maximum(q * d, (q - 1) * d)))

        mae_p50 = _mae(actual, p50)
        mape_p50 = float(np.mean(np.abs(actual - p50) / actual))
        coverage = float(np.mean((actual >= p10) & (actual <= p90)))
        pinball = float(np.mean([
            _pinball(actual, p10, 0.10),
            _pinball(actual, p50, 0.50),
            _pinball(actual, p90, 0.90),
        ]))
        mae_naive = _mae(actual, naive)
        mae_seas = _mae(actual, seas)

        if qr_pts == 0:
            note = ('Fallback-only: history too short to fit the quantile model; '
                    'metrics reflect the rolling/seasonal baseline.')
        elif fb_pts > 0:
            note = (f'{qr_pts} quantile-model + {fb_pts} fallback months '
                    f'(= {len(series)} holdout; earliest months use the fallback).')
        else:
            note = None

        return {
            'n_holdout': len(series),
            'qr_points': qr_pts,
            'fallback_points': fb_pts,
            'mae_p50': round(mae_p50, 0),
            'mape_p50': round(mape_p50, 4),
            'coverage': round(coverage, 3),
            'pinball': round(pinball, 1),
            'mae_naive': round(mae_naive, 0),
            'mae_seasonal': round(mae_seas, 0),
            'skill_vs_naive': round(1 - mae_p50 / mae_naive, 3) if mae_naive > 0 else None,
            'skill_vs_seasonal': round(1 - mae_p50 / mae_seas, 3) if mae_seas > 0 else None,
            'series': series,
            'note': note,
        }
