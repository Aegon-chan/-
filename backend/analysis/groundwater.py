"""地下水位数据分析模块"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def water_level_trend(level_series):
    """地下水位趋势分析（线性回归）

    Parameters
    ----------
    level_series : pd.Series
        地下水位时间序列

    Returns
    -------
    dict : {trend, r_squared, p_value, std_err}
    """
    x = np.arange(len(level_series))
    y = level_series.values
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    return {
        "trend": slope,
        "intercept": intercept,
        "r_squared": r_value ** 2,
        "p_value": p_value,
        "std_err": std_err,
    }


def correlation_with_rainfall(level_series, rain_series):
    """地下水位与降雨量相关性分析

    Parameters
    ----------
    level_series : pd.Series
    rain_series : pd.Series

    Returns
    -------
    tuple : (r, p_value)
    """
    # 对齐两个序列
    combined = pd.concat([level_series, rain_series], axis=1).dropna()
    if len(combined) < 3:
        return (float("nan"), float("nan"))
    r, p = stats.pearsonr(combined.iloc[:, 0].values, combined.iloc[:, 1].values)
    return (r, p)
