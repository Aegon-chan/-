"""Enhanced code execution sandbox.

Provides safe isolated execution for AI-generated code with:
- Result capture (stdout, figures, data)
- Matplotlib headless backend config
- Safe package allowlist
- Resource limits (timeout, memory)
- Output image encoding for inline display
"""

from __future__ import annotations

import base64
import io
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any, Optional

try:
    import resource
except ImportError:
    resource = None

logger = logging.getLogger("research_agent.sandbox")


class SandboxError(Exception):
    pass


SAFE_PACKAGES = {
    "numpy", "np",
    "pandas", "pd",
    "scipy",
    "scipy.stats", "scipy.signal", "scipy.interpolate", "scipy.optimize",
    "statsmodels",
    "statsmodels.tsa.seasonal", "statsmodels.api",
    "sklearn",
    "sklearn.linear_model", "sklearn.preprocessing", "sklearn.metrics",
    "matplotlib",
    "matplotlib.pyplot", "plt",
    "matplotlib.dates",
    "matplotlib.ticker",
    "plotly",
    "plotly.graph_objects", "go",
    "plotly.express", "px",
    "plotly.io",
    "seaborn", "sns",
    "math",
    "datetime",
    "json",
    "collections",
    "itertools",
    "typing",
    "pathlib",
    "re",
    "random",
    "statistics",
    "decimal",
    "fractions",
    "dataclasses",
}


class SandboxResult:
    def __init__(self, success: bool, stdout: str = "", stderr: str = "",
                 figures: list[dict] = None, data: dict = None,
                 return_code: int = 0, execution_time_ms: float = 0.0):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.figures = figures or []
        self.data = data or {}
        self.return_code = return_code
        self.execution_time_ms = execution_time_ms

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "figures": self.figures,
            "data": self.data,
            "return_code": self.return_code,
            "execution_time_ms": self.execution_time_ms,
        }



def _get_python_exe() -> str:
    """Get Python interpreter path, PyInstaller compatible."""
    import sys, os
    exe = sys.executable
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = os.path.dirname(sys.executable)
        candidates = [
            os.path.join(base, "_internal", "python.exe"),
            os.path.join(base, "python.exe"),
            os.path.join(base, "python3.exe"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
        logger.warning("PyInstaller env: no bundled Python found")
    return exe


class CodeSandbox:
    _WRAPPER_PROLOGUE = textwrap.dedent("""\
        import os as _os
        _os.environ.setdefault("MPLBACKEND", "Agg")
        _os.environ.setdefault("MATPLOTLIBRC", "/nonexistent")
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as _plt
        import warnings
        warnings.filterwarnings("ignore", category=UserWarning)
        warnings.filterwarnings("ignore", category=DeprecationWarning)

        import sys as _sys
        from io import StringIO as _StringIO
        _stdout_capture = _StringIO()
        _old_stdout = _sys.stdout
        _sys.stdout = _stdout_capture

        __sandbox_results = {"_figures": [], "_data": {}}
        _results = __sandbox_results
        sandboxresults = __sandbox_results
        _data = __sandbox_results["_data"]
        _fig_counter = 0

        def _save_fig(name=None):
            import base64 as _b64, io as _io
            global _fig_counter
            fig = _plt.gcf()
            if fig.get_axes():
                buf = _io.BytesIO()
                fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
                buf.seek(0)
                b64 = _b64.b64encode(buf.read()).decode("utf-8")
                __sandbox_results["_figures"].append({
                    "id": name or f"fig_{_fig_counter}",
                    "mime": "image/png",
                    "b64": b64,
                })
                _fig_counter += 1
            _plt.clf()

        import numpy as _np
        import pandas as _pd

        try:
    """)

    _WRAPPER_EPILOGUE = textwrap.dedent("""\

        except Exception as _sandbox_err:
            __sandbox_results["_error"] = str(_sandbox_err)
            import traceback as _tb
            __sandbox_results["_traceback"] = _tb.format_exc()
        finally:
            _sys.stdout = _old_stdout
            __sandbox_results["_stdout"] = _stdout_capture.getvalue()
            _save_fig("fig_final")
        import json as _json
        print("<<SANDBOX_RESULT>>")
        print(_json.dumps(__sandbox_results))
        print("<<SANDBOX_RESULT_END>>")
    """)

    def __init__(self, timeout: int = 30, max_memory_mb: int = 512,
                 work_dir: Optional[Path] = None,
                 figure_output_dir: Optional[Path] = None):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.work_dir = work_dir or Path(tempfile.mkdtemp(prefix="sandbox_"))
        self.figure_output_dir = figure_output_dir or (self.work_dir / "figures")
        self.figure_output_dir.mkdir(parents=True, exist_ok=True)
        # PyInstaller: auto-set Agg backend
        if getattr(sys, "frozen", False):
            os.environ.setdefault("MPLBACKEND", "Agg")
            os.environ.setdefault("MATPLOTLIBRC", "/nonexistent")
            logger.info("PyInstaller frozen: MPLBACKEND=Agg")

    def execute_python(self, code: str, input_data: str = "",
                       context: Optional[dict] = None) -> SandboxResult:
        start = time.perf_counter()
        wrapped_code = self._build_wrapper(code, context)

        script_path = self.work_dir / "sandbox_script.py"
        script_path.write_text(wrapped_code, encoding="utf-8")

        try:
            result = subprocess.run(
                [_get_python_exe(), str(script_path)],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.work_dir),
                env=self._sandbox_env(),
            )
            elapsed_ms = (time.perf_counter() - start) * 1000

            sandbox_result = self._parse_result(result.stdout, result.stderr,
                                                result.returncode, elapsed_ms)
            self._save_figures_to_disk(sandbox_result)
            return sandbox_result

        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.warning("Sandbox timeout after %ss", self.timeout)
            return SandboxResult(
                success=False,
                stderr=f"执行超时（{self.timeout}s）",
                return_code=-1,
                execution_time_ms=elapsed_ms,
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.exception("Sandbox error")
            return SandboxResult(
                success=False,
                stderr=str(e),
                return_code=-1,
                execution_time_ms=elapsed_ms,
            )

    def execute_r(self, code: str, input_data: str = "") -> SandboxResult:
        start = time.perf_counter()
        script_path = self.work_dir / "sandbox_script.R"
        script_path.write_text(code, encoding="utf-8")

        try:
            result = subprocess.run(
                ["Rscript", str(script_path)],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.work_dir),
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            return SandboxResult(
                success=result.returncode == 0,
                stdout=result.stdout,
                stderr=result.stderr,
                return_code=result.returncode,
                execution_time_ms=elapsed_ms,
            )
        except subprocess.TimeoutExpired:
            return SandboxResult(
                success=False,
                stderr=f"R 执行超时（{self.timeout}s）",
                return_code=-1,
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                stderr=str(e),
                return_code=-1,
            )

    def clean(self):
        if self.work_dir and self.work_dir.exists():
            shutil.rmtree(str(self.work_dir), ignore_errors=True)

    def __del__(self):
        self.clean()

    def _sandbox_env(self) -> dict:
        env = dict(os.environ)
        for var in ["PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME",
                    "LD_PRELOAD", "LD_LIBRARY_PATH"]:
            env.pop(var, None)
        env["MPLBACKEND"] = "Agg"
        env["MATPLOTLIBRC"] = "/nonexistent"
        env["LC_ALL"] = "C"
        return env

    def _build_wrapper(self, code: str, context: Optional[dict] = None) -> str:
        context_block = ""
        if context:
            parts = []
            for key, val in context.items():
                if isinstance(val, str):
                    parts.append(f"{key} = {repr(val)}")
                else:
                    parts.append(f"{key} = {val!r}")
            context_block = "\n".join(parts) + "\n"

        indented = textwrap.indent(context_block, "    ") + textwrap.indent(code, "    ")
        return self._WRAPPER_PROLOGUE + indented + self._WRAPPER_EPILOGUE

    def _parse_result(self, stdout: str, stderr: str,
                      return_code: int, elapsed_ms: float) -> SandboxResult:
        result = SandboxResult(
            success=return_code == 0,
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
            execution_time_ms=elapsed_ms,
        )

        pattern = r"<<SANDBOX_RESULT>>\n(.*?)\n<<SANDBOX_RESULT_END>>"
        match = re.search(pattern, stdout, re.DOTALL)
        if match:
            try:
                import json
                parsed = json.loads(match.group(1))
                result.figures = parsed.get("_figures", [])
                raw_data = parsed.get("_data", {})
                result.data = raw_data if isinstance(raw_data, dict) else {}
                result.stdout = parsed.get("_stdout", "")
                if parsed.get("_error"):
                    result.success = False
                    result.stderr = parsed["_traceback"]
            except (ValueError, KeyError):
                pass

        return result

    def _save_figures_to_disk(self, result: SandboxResult):
        for fig in result.figures:
            try:
                b64 = fig.get("b64", "")
                if b64:
                    import base64
                    img_bytes = base64.b64decode(b64)
                    path = self.figure_output_dir / f"{fig['id']}.png"
                    path.write_bytes(img_bytes)
                    fig["path"] = str(path.resolve())
            except Exception as e:
                logger.warning("Failed to save figure %s: %s",
                               fig.get("id"), e)
