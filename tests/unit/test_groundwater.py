"""Tests for groundwater analysis module."""
from __future__ import annotations

import pytest
import pandas as pd
import numpy as np

class TestGroundwater:
    def test_water_level_trend(self):
        from backend.analysis.groundwater import water_level_trend
        import pandas as pd
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        data = pd.Series(np.random.randn(30).cumsum(), index=dates)
        result = water_level_trend(data)
        assert result is not None

    def test_correlation(self):
        from backend.analysis.groundwater import correlation_with_rainfall
        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        gw = pd.Series(np.random.randn(30).cumsum(), index=dates)
        rain = pd.Series(np.random.randn(30).cumsum(), index=dates)
        result = correlation_with_rainfall(gw, rain)
        assert result is not None
