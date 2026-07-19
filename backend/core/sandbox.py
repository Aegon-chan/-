"""Facade for sandboxed code execution — delegates to provider implementations.

See ``sandbox_providers.py`` for ``SubprocessProvider``, ``DockerProvider``,
and ``KubernetesProvider``.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional

from backend.core.sandbox_providers import (
    SandboxProvider,
    SubprocessProvider,
    DockerProvider,
    KubernetesProvider,
    SandboxResult,
    SandboxError,
)

logger = logging.getLogger("research_agent.sandbox")

# Public re-exports
__all__ = [
    "CodeSandbox",
    "SandboxProvider",
    "SubprocessProvider",
    "DockerProvider",
    "KubernetesProvider",
    "SandboxResult",
    "SandboxError",
    "SAFE_PACKAGES",
]

# Legacy: re-export from providers module for backward compat
SAFE_PACKAGES = {
    "numpy", "np", "pandas", "pd",
    "scipy", "scipy.stats", "scipy.signal", "scipy.interpolate",
    "scipy.optimize",
    "statsmodels", "statsmodels.tsa.seasonal", "statsmodels.api",
    "sklearn", "sklearn.linear_model", "sklearn.preprocessing",
    "sklearn.metrics",
    "matplotlib", "matplotlib.pyplot", "plt",
    "matplotlib.dates", "matplotlib.ticker",
    "plotly", "plotly.graph_objects", "go", "plotly.express", "px",
    "plotly.io", "seaborn", "sns",
    "math", "datetime", "json", "collections", "itertools",
    "typing", "pathlib", "re", "random", "statistics",
    "decimal", "fractions", "dataclasses",
}


class CodeSandbox:
    """Facade for sandboxed code execution.

    Automatically selects the appropriate provider based on
    ``provider_type`` (or legacy ``docker_mode`` flag).
    """

    def __init__(self, timeout: int = 30, max_memory_mb: int = 512,
                 work_dir: Optional[Path] = None,
                 figure_output_dir: Optional[Path] = None,
                 docker_mode: bool = False,
                 docker_image: str = "research-agent-sandbox:latest",
                 provider_type: str = "subprocess",
                 k8s_namespace: str = "research-agent-sandbox",
                 tenant_id: str = "default"):
        self._provider: SandboxProvider

        # PyInstaller override
        if getattr(sys, "frozen", False):
            os.environ.setdefault("MPLBACKEND", "Agg")
            os.environ.setdefault("MATPLOTLIBRC", "/nonexistent")
            logger.info("PyInstaller frozen: MPLBACKEND=Agg")
            provider_type = "subprocess"
            docker_mode = False

        if provider_type == "k8s":
            self._provider = KubernetesProvider(
                timeout=timeout,
                namespace=k8s_namespace,
                tenant_id=tenant_id,
            )
        elif docker_mode or provider_type == "docker":
            self._provider = DockerProvider(
                timeout=timeout,
                max_memory_mb=max_memory_mb,
                image=docker_image,
            )
        else:
            self._provider = SubprocessProvider(
                timeout=timeout,
                work_dir=work_dir,
                figure_output_dir=figure_output_dir,
            )

    @property
    def provider(self) -> SandboxProvider:
        return self._provider

    def execute_python(self, code: str, input_data: str = "",
                       context: dict | None = None) -> SandboxResult:
        return self._provider.execute_python(code, input_data, context)

    def execute_r(self, code: str, input_data: str = "") -> SandboxResult:
        return self._provider.execute_r(code, input_data)

    def execute_python_docker(self, code: str,
                              input_data: str = "") -> SandboxResult:
        """Legacy entry — delegates to DockerProvider (or fallback)."""
        if isinstance(self._provider, DockerProvider):
            return self._provider.execute_python(code, input_data)
        return DockerProvider(
            timeout=30,
        ).execute_python(code, input_data)

    def clean(self):
        self._provider.clean()

    def __del__(self):
        try:
            self.clean()
        except Exception:
            pass
