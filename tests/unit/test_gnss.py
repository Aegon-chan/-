"""GNSS 分析模块单元测试"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.analysis.gnss import (
    decompose_timeseries,
    detect_step,
    estimate_velocity,
    outlier_detection,
    signal_filter,
)


@pytest.fixture
def daily_ts():
    """生成 365 天模拟 GNSS 位移数据"""
    dates = pd.date_range("2024-01-01", periods=365, freq="D")
    np.random.seed(42)
    trend = np.linspace(0, 10, 365)  # 线性趋势
    seasonal = 2 * np.sin(2 * np.pi * np.arange(365) / 365)  # 年周期
    noise = np.random.normal(0, 0.5, 365)
    displacement = trend + seasonal + noise
    return pd.Series(displacement, index=dates)


def test_estimate_velocity(daily_ts):
    result = estimate_velocity(daily_ts)
    assert "velocity" in result
    assert result["r_squared"] > 0.7  # 强线性趋势
    assert result["p_value"] < 0.001
    assert result["std_err"] > 0


def test_detect_step_no_step(daily_ts):
    """平稳序列不应检测到阶跃"""
    result = detect_step(daily_ts, threshold=5.0, window=5)
    assert "steps" in result
    assert result["method"] == "sliding_window_t_test"


def test_detect_step_with_step():
    """手动插入阶跃，应被检测到"""
    data = pd.Series(np.random.normal(0, 0.1, 200))
    data.iloc[100:] += 5.0  # 在 index 100 插入阶跃
    result = detect_step(data, threshold=3.0, window=5)
    assert len(result["steps"]) > 0
    # 最近的一个阶跃应在 index 100 附近
    closest = min(result["steps"], key=lambda s: abs(s["index"] - 100))
    assert abs(closest["index"] - 100) <= 10


def test_outlier_detection_iqr():
    data = pd.Series(np.random.normal(0, 1, 100))
    data.iloc[0] = 100  # 明显异常
    result = outlier_detection(data, method="iqr")
    assert len(result["outliers"]) >= 1
    assert result["method"] == "iqr"
    assert result["outliers"][0]["index"] == 0


def test_outlier_detection_zscore():
    data = pd.Series(np.random.normal(0, 1, 100))
    data.iloc[0] = 100
    result = outlier_detection(data, method="zscore", factor=3.0)
    assert len(result["outliers"]) >= 1
    assert result["method"] == "zscore"


def test_signal_filter_moving_average(daily_ts):
    filtered = signal_filter(daily_ts, method="moving_average", window=7)
    assert len(filtered) == len(daily_ts)
    # 滤波后应更平滑
    assert filtered.std() < daily_ts.std()


def test_signal_filter_savgol(daily_ts):
    filtered = signal_filter(daily_ts, method="savgol", window=7)
    assert len(filtered) == len(daily_ts)
    assert filtered.std() < daily_ts.std()


def test_decompose_timeseries(daily_ts):
    result = decompose_timeseries(daily_ts, period=30)
    assert hasattr(result, "trend")
    assert hasattr(result, "seasonal")
    assert hasattr(result, "resid")

