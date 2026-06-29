"""雨量数据分析模块"""
from __future__ import annotations


def cumulative_rainfall(daily_rain):
    return daily_rain.cumsum()


def rainfall_intensity(rain_series, window="1h"):
    return rain_series.resample(window).sum()


def estimate_return_period(max_annual_series):
    return {"return_periods": [], "method": "gumbel"}
