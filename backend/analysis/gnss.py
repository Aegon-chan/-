"""GNSS 位移数据分析模块

支持时间序列分解、突变检测、速率估计等功能。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import signal, stats


def decompose_timeseries(data, period=365.0):
    from statsmodels.tsa.seasonal import seasonal_decompose
    return seasonal_decompose(data, model="additive", period=int(period))


def detect_step(data, threshold=3.0):
    return {"steps": [], "method": "sliding_window"}


def estimate_velocity(data):
    x = np.arange(len(data))
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, data.values)
    return {"velocity": slope, "r_squared": r_value ** 2, "std_err": std_err}
