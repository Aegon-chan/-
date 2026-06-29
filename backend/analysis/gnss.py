"""GNSS 位移数据分析模块

支持时间序列分解、突变检测、速率估计、异常检测、信号滤波等功能。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def decompose_timeseries(data, period=365.0):
    """时间序列分解（趋势 + 季节 + 残差）

    Parameters
    ----------
    data : pd.Series
        带 DatetimeIndex 的位移时间序列
    period : float
        季节周期天数，默认 365

    Returns
    -------
    statsmodels DecomposeResult
    """
    from statsmodels.tsa.seasonal import seasonal_decompose
    return seasonal_decompose(data, model="additive", period=int(period))


def detect_step(data, threshold=3.0, window=5):
    """滑动窗口 t 检验检测阶跃突变

    Parameters
    ----------
    data : pd.Series
    threshold : float
        t 统计量阈值，默认 3.0
    window : int
        滑动窗口大小，默认 5

    Returns
    -------
    dict : {steps: [{index, magnitude, p_value}], method}
    """
    steps = []
    n = len(data)
    if n < 2 * window:
        return {"steps": [], "method": "sliding_window_t_test"}

    for i in range(window, n - window):
        left = data.iloc[i - window : i]
        right = data.iloc[i : i + window]
        t_stat, p_val = stats.ttest_ind(left, right, equal_var=False)
        if abs(t_stat) > threshold:
            steps.append({
                "index": i,
                "magnitude": float(right.mean() - left.mean()),
                "p_value": float(p_val),
            })

    return {"steps": steps, "method": "sliding_window_t_test"}


def estimate_velocity(data):
    """线性回归估计形变速率

    Parameters
    ----------
    data : pd.Series

    Returns
    -------
    dict : {velocity, r_squared, std_err, p_value}
    """
    x = np.arange(len(data))
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, data.values)
    return {
        "velocity": slope,
        "intercept": intercept,
        "r_squared": r_value ** 2,
        "std_err": std_err,
        "p_value": p_value,
    }


def outlier_detection(data, method="iqr", factor=1.5):
    """异常值检测

    Parameters
    ----------
    data : pd.Series
    method : str
        "iqr" — 四分位距法
        "zscore" — Z-Score 法
    factor : float
        IQR 倍数（iqr 模式）或 Z-Score 阈值（zscore 模式）

    Returns
    -------
    dict : {outliers: [{index, value}], method, threshold}
    """
    outliers = []
    values = data.values

    if method == "iqr":
        q1, q3 = np.percentile(values, [25, 75])
        iqr = q3 - q1
        lower = q1 - factor * iqr
        upper = q3 + factor * iqr
        mask = (values < lower) | (values > upper)
        threshold = {"lower": float(lower), "upper": float(upper)}
    elif method == "zscore":
        z = np.abs(stats.zscore(values))
        mask = z > factor
        threshold = float(factor)
    else:
        raise ValueError(f"Unknown method: {method}")

    for idx in np.where(mask)[0]:
        outliers.append({"index": int(idx), "value": float(values[idx])})

    return {"outliers": outliers, "method": method, "threshold": threshold}


def signal_filter(data, method="moving_average", window=5):
    """信号滤波

    Parameters
    ----------
    data : pd.Series
    method : str
        "moving_average" — 移动平均
        "savgol" — Savitzky-Golay 滤波
    window : int
        窗口大小

    Returns
    -------
    pd.Series : 滤波后的序列（与输入对齐）
    """
    if method == "moving_average":
        return data.rolling(window=window, center=True, min_periods=1).mean()
    elif method == "savgol":
        from scipy.signal import savgol_filter
        window = min(window, len(data) - 1 if len(data) % 2 == 0 else len(data))
        if window % 2 == 0:
            window -= 1
        window = max(3, window)
        smoothed = savgol_filter(data.values, window, polyorder=2)
        return pd.Series(smoothed, index=data.index)
    else:
        raise ValueError(f"Unknown filter method: {method}")
