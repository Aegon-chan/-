"""降雨分析模块单元测试"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pytest import approx
from backend.analysis.rainfall import (
    cumulative_rainfall,
    dry_wet_spell_analysis,
    estimate_return_period,
    rainfall_intensity,
    seasonal_rainfall_distribution,
)


@pytest.fixture
def daily_rain():
    """生成 365 天模拟日降雨数据"""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=365, freq="D")
    # 大部分天无雨，少数天有雨
    rain = np.zeros(365)
    rainy_days = np.random.choice(365, 60, replace=False)
    rain[rainy_days] = np.random.exponential(10, 60)
    return pd.Series(rain, index=dates)


def test_cumulative_rainfall(daily_rain):
    cum = cumulative_rainfall(daily_rain)
    assert len(cum) == len(daily_rain)
    assert cum.iloc[-1] == approx(daily_rain.sum(), rel=1e-5)
    assert (cum.diff().iloc[1:] >= 0).all()  # 单调不减


def test_rainfall_intensity_hourly():
    # 测试重采样（即使数据是日尺度，也应能正常分组）
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    rain = pd.Series(np.random.exponential(5, 10), index=dates)
    result = rainfall_intensity(rain, window="1D")
    assert len(result) == len(rain)
    assert result.sum() == rain.sum()


def test_estimate_return_period_sufficient():
    data = [50, 60, 55, 70, 65, 80, 75, 90, 85, 100]
    result = estimate_return_period(data)
    assert result["method"] == "gumbel"
    assert "return_periods" in result
    for rp in ["2", "5", "10", "20", "50", "100"]:
        assert rp in result["return_periods"]
        if result["return_periods"][rp] is not None:
            assert result["return_periods"][rp] > 0


def test_estimate_return_period_insufficient():
    data = [50, 60]
    result = estimate_return_period(data)
    assert "warning" in result


def test_dry_wet_spell_analysis(daily_rain):
    result = dry_wet_spell_analysis(daily_rain, dry_threshold=1.0)
    assert "dry" in result
    assert "wet" in result
    assert result["dry"]["total_days"] + result["wet"]["total_days"] == len(daily_rain)
    assert result["dry"]["count"] > 0
    assert result["wet"]["count"] > 0


def test_seasonal_rainfall_distribution(daily_rain):
    # 重采样为月数据
    monthly = daily_rain.resample("ME").sum()
    result = seasonal_rainfall_distribution(monthly)
    assert "monthly" in result
    assert "seasonal" in result
    assert len(result["monthly"]) == 12
    assert all(s in result["seasonal"] for s in ["春", "夏", "秋", "冬"])


def test_seasonal_rainfall_empty():
    result = seasonal_rainfall_distribution(pd.Series(dtype=float))
    assert result == {"monthly": {}, "seasonal": {}}

