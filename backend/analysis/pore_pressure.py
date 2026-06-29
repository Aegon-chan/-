"""孔隙水压力分析模块"""
from __future__ import annotations

import numpy as np
from scipy import stats, optimize


def pore_pressure_trend(pp_series):
    """孔压变化趋势分析

    Parameters
    ----------
    pp_series : pd.Series
        孔压时间序列

    Returns
    -------
    dict : {trend, r_squared, p_value, std_err}
    """
    x = np.arange(len(pp_series))
    y = pp_series.values
    slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
    return {
        "trend": slope,
        "intercept": intercept,
        "r_squared": r_value ** 2,
        "p_value": p_value,
        "std_err": std_err,
    }


def excess_pore_pressure_dissipation(pp_series, initial_pp):
    """超静孔压消散分析（指数衰减模型）

    拟合 pp(t) = initial_pp * exp(-t/tau) + residual
    计算半衰期 t_half = tau * ln(2)

    Parameters
    ----------
    pp_series : pd.Series
        孔压时间序列
    initial_pp : float
        初始超静孔压值

    Returns
    -------
    dict : {dissipation_rate, half_life, residual, r_squared}
    """
    t = np.arange(len(pp_series), dtype=float)
    y = pp_series.values

    if len(pp_series) < 3:
        return {"dissipation_rate": None, "half_life": None, "residual": None, "r_squared": None, "warning": "样本不足（<3）"}

    def model(t, tau, residual):
        return initial_pp * np.exp(-t / tau) + residual

    try:
        popt, _ = optimize.curve_fit(model, t, y, p0=[10, 0], maxfev=5000)
        tau, residual = popt
        half_life = tau * np.log(2)

        # R² 拟合优度
        fitted = model(t, tau, residual)
        ss_res = np.sum((y - fitted) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        return {
            "dissipation_rate": round(1.0 / tau, 6) if tau > 0 else None,
            "half_life": round(float(half_life), 4),
            "tau": round(float(tau), 4),
            "residual": round(float(residual), 4),
            "r_squared": round(float(r_squared), 4),
        }
    except (RuntimeError, ValueError):
        return {"dissipation_rate": None, "half_life": None, "residual": None, "r_squared": None, "warning": "拟合失败"}
