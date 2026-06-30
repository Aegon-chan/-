"""Tests for the cross-correlation analysis module."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backend.analysis.cross_correlation import (
    cross_correlation,
    rainfall_deformation_analysis,
    multivariate_regression,
)


class TestCrossCorrelation:
    def test_basic_correlation(self):
        x = np.random.randn(100)
        y = x * 0.8 + np.random.randn(100) * 0.2
        a = pd.Series(x, index=pd.date_range("2024-01-01", periods=100, freq="D"))
        b = pd.Series(y, index=pd.date_range("2024-01-01", periods=100, freq="D"))
        result = cross_correlation(a, b)
        assert result["correlation"] is not None
        assert result["correlation"] > 0.5

    def test_negative_correlation(self):
        x = np.random.randn(50)
        y = -x * 0.7 + np.random.randn(50) * 0.3
        a = pd.Series(x)
        b = pd.Series(y)
        result = cross_correlation(a, b)
        assert result["correlation"] < -0.3

    def test_insufficient_data(self):
        a = pd.Series([1, 2])
        b = pd.Series([3, 4])
        result = cross_correlation(a, b)
        assert result["correlation"] is None

    def test_spearman_method(self):
        x = np.random.randn(80)
        y = x ** 3 + np.random.randn(80) * 0.1
        a = pd.Series(x)
        b = pd.Series(y)
        result = cross_correlation(a, b, method="spearman")
        assert result["lag_at_max"] is not None
        assert result["correlation"] is not None


class TestRainfallDeformation:
    def test_deformation_lag(self):
        dates = pd.date_range("2024-01-01", periods=100, freq="D")
        rainfall = pd.Series(np.random.exponential(5, 100), index=dates)
        rain_trigger = np.zeros(100)
        rain_trigger[10:15] = 50
        rainfall += pd.Series(rain_trigger, index=dates)
        deformation = pd.Series(np.random.randn(100) * 0.5, index=dates)
        deformation.iloc[15:25] += 2.0
        result = rainfall_deformation_analysis(deformation, rainfall, max_lag_days=20)
        assert result["max_correlation"] is not None
        assert result["lag_at_max"] >= 0

    def test_insufficient_samples(self):
        a = pd.Series([1, 2, 3])
        b = pd.Series([4, 5, 6])
        result = rainfall_deformation_analysis(a, b)
        assert result["max_correlation"] is None


class TestMultivariateRegression:
    def test_basic_regression(self):
        n = 50
        x1 = np.random.randn(n)
        x2 = np.random.randn(n)
        y = 2.0 * x1 + 0.5 * x2 + np.random.randn(n) * 0.1
        target = pd.Series(y)
        predictors = {"x1": pd.Series(x1), "x2": pd.Series(x2)}
        result = multivariate_regression(target, predictors)
        assert result["r_squared"] is not None
        assert result["r_squared"] > 0.8
        assert len(result["coefficients"]) == 2

    def test_insufficient_data(self):
        target = pd.Series([1, 2])
        predictors = {"x1": pd.Series([3, 4])}
        result = multivariate_regression(target, predictors)
        assert result["r_squared"] is None