"""InSAR 形变数据分析模块"""
from __future__ import annotations

import numpy as np
from scipy import stats


def interpolate_deformation_field(points, values, grid_shape=(100, 100)):
    """InSAR 形变场插值（克里金近似 / 径向基）

    Parameters
    ----------
    points : np.ndarray
        (N, 2) 坐标点
    values : np.ndarray
        (N,) 形变值
    grid_shape : tuple
        输出网格 (rows, cols)

    Returns
    -------
    dict : {grid_values, x_grid, y_grid, method}
    """
    from scipy.interpolate import RBFInterpolator

    x_min, x_max = points[:, 0].min(), points[:, 0].max()
    y_min, y_max = points[:, 1].min(), points[:, 1].max()
    xs = np.linspace(x_min, x_max, grid_shape[1])
    ys = np.linspace(y_min, y_max, grid_shape[0])
    x_grid, y_grid = np.meshgrid(xs, ys)

    if len(points) < 4:
        return {
            "grid_values": np.full(grid_shape, float("nan")),
            "x_grid": x_grid, "y_grid": y_grid,
            "method": "rbf",
            "warning": "样本不足（<4），无法插值",
        }

    rbf = RBFInterpolator(points, values, kernel="thin_plate_spline", epsilon=1.0)
    grid_points = np.column_stack([x_grid.ravel(), y_grid.ravel()])
    grid_vals = rbf(grid_points).reshape(grid_shape)

    return {"grid_values": grid_vals, "x_grid": x_grid, "y_grid": y_grid, "method": "rbf"}


def calculate_cumulative_deformation(timeseries):
    """计算累积形变量

    Parameters
    ----------
    timeseries : pd.Series
        形变时间序列

    Returns
    -------
    pd.Series : 累积形变
    """
    return timeseries.cumsum()


def generate_deformation_rate_map(deformation_series):
    """形变速率分析

    Parameters
    ----------
    deformation_series : pd.Series
        形变时间序列

    Returns
    -------
    dict : {rate, r_squared, p_value}
    """
    x = np.arange(len(deformation_series))
    y = deformation_series.values
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    return {
        "rate": slope,
        "r_squared": r_value ** 2,
        "p_value": p_value,
        "std_err": std_err,
    }
