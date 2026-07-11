"""Tests for InSAR analysis module."""
from __future__ import annotations

import pytest
import pandas as pd
import numpy as np

class TestInSAR:
    def test_imports(self):
        from backend.analysis.insar import (
            calculate_cumulative_deformation,
            generate_deformation_rate_map,
            interpolate_deformation_field,
        )
        assert callable(calculate_cumulative_deformation)
        assert callable(generate_deformation_rate_map)
        assert callable(interpolate_deformation_field)

    def test_cumulative_deformation(self):
        from backend.analysis.insar import calculate_cumulative_deformation
        dates = pd.date_range("2024-01-01", periods=10, freq="D")
        deformations = pd.Series(np.random.randn(10).cumsum(), index=dates)
        result = calculate_cumulative_deformation(deformations)
        assert result is not None
