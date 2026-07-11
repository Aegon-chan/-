"""Tests for pore pressure analysis module."""
from __future__ import annotations

import pytest
import numpy as np
import pandas as pd

class TestPorePressure:
    def test_trend(self):
        from backend.analysis.pore_pressure import pore_pressure_trend
        dates = pd.date_range("2024-01-01", periods=50, freq="D")
        data = pd.Series(np.random.randn(50).cumsum(), index=dates)
        result = pore_pressure_trend(data)
        assert result is not None

    def test_dissipation(self):
        from backend.analysis.pore_pressure import excess_pore_pressure_dissipation
        dates = pd.date_range("2024-01-01", periods=50, freq="D")
        data = pd.Series(np.exp(-np.linspace(0, 5, 50)) * 100, index=dates)
        result = excess_pore_pressure_dissipation(data, range(50))
        assert result is not None
