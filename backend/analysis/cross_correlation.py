"""Multi-source data cross-correlation analysis module."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats, signal


def cross_correlation(series_a, series_b, max_lag=30, method="pearson"):
    combined = pd.concat([series_a, series_b], axis=1).dropna()
    if len(combined) < 10:
        return {"correlation": None, "p_value": None, "lag_at_max": 0}
    a, b = combined.iloc[:, 0].values, combined.iloc[:, 1].values
    r_func = stats.spearmanr if method == "spearman" else stats.pearsonr
    r, p = r_func(a, b)
    ccf = signal.correlate(a - a.mean(), b - b.mean(), method="auto")
    ccf /= (len(a) * a.std() * b.std())
    lags = signal.correlation_lags(len(a), len(b))
    mid = len(lags) // 2
    half = min(max_lag, len(lags) // 2 - 1)
    valid = list(zip(lags[mid-half:mid+half+1], ccf[mid-half:mid+half+1]))
    best = max(valid, key=lambda x: abs(x[1]))
    return {"correlation": round(float(r), 4), "p_value": float(p), "lag_at_max": int(best[0]), "n_samples": len(combined)}


def rainfall_deformation_analysis(displacement, rainfall, max_lag_days=60):
    combined = pd.concat([displacement, rainfall], axis=1).dropna()
    if len(combined) < 15:
        return {"max_correlation": None, "lag_at_max": None, "daily_analysis": []}
    disp_col, rain_col = combined.columns[0], combined.columns[1]
    results = []
    max_corr, best_lag = -1, 0
    for lag in range(max_lag_days + 1):
        shifted = combined[rain_col] if lag == 0 else combined[rain_col].shift(lag)
        aligned = pd.concat([combined[disp_col], shifted], axis=1).dropna()
        if len(aligned) < 10:
            continue
        r, p = stats.pearsonr(aligned.iloc[:, 0].values, aligned.iloc[:, 1].values)
        results.append({"lag_days": lag, "correlation": round(float(r), 4), "p_value": float(p)})
        if abs(r) > abs(max_corr):
            max_corr, best_lag = r, lag
    return {"max_correlation": round(float(max_corr), 4), "lag_at_max": best_lag, "daily_analysis": results}


def multivariate_regression(target, predictors):
    from sklearn.linear_model import LinearRegression
    df = pd.DataFrame({name: s for name, s in predictors.items()})
    df["_target"] = target
    df = df.dropna()
    if len(df) < len(predictors) + 2:
        return {"r_squared": None, "coefficients": {}}
    X = df[[c for c in df.columns if c != "_target"]].values
    y = df["_target"].values
    model = LinearRegression()
    model.fit(X, y)
    ss_res = np.sum((y - model.predict(X))**2)
    ss_tot = np.sum((y - y.mean())**2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    names = [c for c in df.columns if c != "_target"]
    coeffs = {names[i]: round(float(model.coef_[i]), 4) for i in range(len(names))}
    return {"r_squared": round(float(r2), 4), "coefficients": coeffs, "intercept": round(float(model.intercept_), 4), "n_samples": len(df)}
