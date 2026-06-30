"""降雨数据分析模块

支持累积降雨量、降雨强度、重现期估算、干湿期统计、季节性分布等功能。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def cumulative_rainfall(daily_rain):
    """计算累积降雨量

    Parameters
    ----------
    daily_rain : pd.Series
        逐日降雨量序列

    Returns
    -------
    pd.Series : 累积降雨量
    """
    return daily_rain.cumsum()


def rainfall_intensity(rain_series, window="1h"):
    """降雨强度重采样

    Parameters
    ----------
    rain_series : pd.Series
        降雨时间序列
    window : str
        重采样窗口（如 "1h", "1D", "3h"）

    Returns
    -------
    pd.Series : 重采样后的降雨强度
    """
    return rain_series.resample(window).sum()


def estimate_return_period(max_annual_series):
    """Gumbel 极值分布拟合估算重现期

    Parameters
    ----------
    max_annual_series : array-like
        年最大降雨量序列

    Returns
    -------
    dict : {return_periods, method, params}
    """
    data = np.asarray(max_annual_series, dtype=float)
    if len(data) < 3:
        return {"return_periods": {}, "method": "gumbel", "params": {}, "warning": "样本不足（<3）"}

    # Gumbel 分布拟合（极大值）
    loc, scale = stats.gumbel_r.fit(data)

    return_periods_list = [2, 5, 10, 20, 50, 100]
    result = {}
    for rp in return_periods_list:
        # Gumbel 累积分布逆函数：F(x) = exp(-exp(-(x-loc)/scale))
        # 针对 exceedance probability = 1 - 1/rp
        p = 1.0 - 1.0 / rp
        try:
            result[str(rp)] = round(float(stats.gumbel_r.ppf(p, loc=loc, scale=scale)), 2)
        except Exception:
            result[str(rp)] = None

    return {
        "return_periods": result,
        "method": "gumbel",
        "params": {"loc": round(float(loc), 4), "scale": round(float(scale), 4)},
        "n_samples": len(data),
    }


def dry_wet_spell_analysis(daily_rain, dry_threshold=1.0):
    """干期/湿期统计分析

    连续日降雨量 < dry_threshold 为干期，>= dry_threshold 为湿期。

    Parameters
    ----------
    daily_rain : pd.Series
        逐日降雨量（单位 mm）
    dry_threshold : float
        干湿判定阈值（mm/d），默认 1.0

    Returns
    -------
    dict : {dry, wet} 各包含 {count, max_days, mean_days, total_days}
    """
    is_dry = daily_rain < dry_threshold
    dry_spells = []
    wet_spells = []
    current = 1
    current_dry = bool(is_dry.iloc[0])

    for i in range(1, len(is_dry)):
        if bool(is_dry.iloc[i]) == current_dry:
            current += 1
        else:
            if current_dry:
                dry_spells.append(current)
            else:
                wet_spells.append(current)
            current = 1
            current_dry = not current_dry

    # 最后一段
    if current_dry:
        dry_spells.append(current)
    else:
        wet_spells.append(current)

    def _stats(spells):
        if not spells:
            return {"count": 0, "max_days": 0, "mean_days": 0.0, "total_days": 0}
        return {
            "count": len(spells),
            "max_days": max(spells),
            "mean_days": round(float(np.mean(spells)), 2),
            "total_days": sum(spells),
        }

    return {
        "dry": _stats(dry_spells),
        "wet": _stats(wet_spells),
        "threshold_mm": dry_threshold,
    }


def seasonal_rainfall_distribution(monthly_data):
    """季节性降雨分布统计

    Parameters
    ----------
    monthly_data : pd.Series
        月降雨量序列（DatetimeIndex）

    Returns
    -------
    dict : 按月份和季节的统计量
    """
    if monthly_data.empty:
        return {"monthly": {}, "seasonal": {}}

    month_names = ["1月", "2月", "3月", "4月", "5月", "6月",
                   "7月", "8月", "9月", "10月", "11月", "12月"]

    monthly = monthly_data.groupby(monthly_data.index.month).agg(["mean", "std", "sum"])
    total = monthly["sum"].sum()
    monthly_stats = {}
    for m in range(1, 13):
        row = monthly.loc[m] if m in monthly.index else None
        if row is not None:
            monthly_stats[month_names[m - 1]] = {
                "mean": round(float(row["mean"]), 2),
                "std": round(float(row["std"]), 2) if pd.notna(row["std"]) else 0.0,
                "total": round(float(row["sum"]), 2),
                "contribution": round(float(row["sum"] / total * 100), 1) if total > 0 else 0,
            }

    # 季节划分：春(3-5) 夏(6-8) 秋(9-11) 冬(12-2)
    season_map = {3: "春", 4: "春", 5: "春",
                  6: "夏", 7: "夏", 8: "夏",
                  9: "秋", 10: "秋", 11: "秋",
                  12: "冬", 1: "冬", 2: "冬"}
    seasonal = monthly_data.groupby(monthly_data.index.month.map(season_map)).sum()
    season_total = seasonal.sum()
    seasonal_stats = {}
    for s in ["春", "夏", "秋", "冬"]:
        val = seasonal.get(s, 0)
        seasonal_stats[s] = {
            "total": round(float(val), 2),
            "contribution": round(float(val / season_total * 100), 1) if season_total > 0 else 0,
        }

    return {"monthly": monthly_stats, "seasonal": seasonal_stats}
