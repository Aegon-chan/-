"""地下水位数据分析模块"""
from __future__ import annotations


def water_level_trend(level_series):
    return None


def correlation_with_rainfall(level_series, rain_series):
    from scipy import stats
    return stats.pearsonr(level_series, rain_series)
