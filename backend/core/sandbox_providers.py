""">SandboxProvider ABC + 3 implementations.

SubprocessProvider (local subprocess, default)
DockerProvider     (Docker container, single-node production)
KubernetesProvider (K8s Job, multi-tenant production)
"""
from __future__ import annotations

import base64
import json as _json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("research_agent.sandbox.providers")


class SandboxError(Exception):
    """Non-recoverable sandbox error."""
    pass


class SandboxResult:
    """Container for sandbox execution result."""

    def __init__(
        self,
        success: bool,
        stdout: str = "",
        stderr: str = "",
        figures: list[dict] | None = None,
        data: dict | None = None,
        return_code: int = 0,
        execution_time_ms: float = 0.0,
    ):
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


# ---------------------------------------------------------------------------
# Wrapper helpers (generate the code that runs inside the sandbox)
# ---------------------------------------------------------------------------

_WRAPPER_PROLOGUE = textwrap.dedent("""\
    import os as _os
    _os.environ.setdefault("MPLBACKEND", "Agg")
    _os.environ.setdefault("MATPLOTLIBRC", "/nonexistent")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as _plt
    # === Configure CJK font support for Chinese labels ===
    _os.environ["MATPLOTLIBRC"] = ""
    matplotlib.rcParams["font.sans-serif"] = [
        "Microsoft YaHei", "SimHei", "Noto Sans SC",
        "Source Han Serif SC", "SimSun", "DejaVu Sans",
    ]
    matplotlib.rcParams["axes.unicode_minus"] = False
    _plt_boxplot_orig = _plt.boxplot
    def _plt_boxplot_compat(x, *args, **kwargs):
        if 'labels' in kwargs and 'tick_labels' not in kwargs:
            kwargs['tick_labels'] = kwargs.pop('labels')
        return _plt_boxplot_orig(x, *args, **kwargs)
    _plt.boxplot = _plt_boxplot_compat
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
    import math as _math
    def _sanitize_for_json(obj):
        if obj is None:
            return None
        if isinstance(obj, (bool, int, float, str)):
            if isinstance(obj, float):
                if _math.isnan(obj) or _math.isinf(obj):
                    return None
            return obj
        if isinstance(obj, (_np.integer,)):
            return int(obj)
        if isinstance(obj, (_np.floating,)):
            v = float(obj)
            if _math.isnan(v) or _math.isinf(v):
                return None
            return v
        if isinstance(obj, (_np.ndarray,)):
            return [_sanitize_for_json(x) for x in obj.tolist()]
        if isinstance(obj, dict):
            return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_sanitize_for_json(x) for x in obj]
        try:
            return str(obj)
        except Exception:
            return None
    import json as _json
    print("<<SANDBOX_RESULT>>")
    print(_json.dumps(__sandbox_results, default=_sanitize_for_json))
    print("<<SANDBOX_RESULT_END>>")
""")


def build_wrapper(code: str, context: dict | None = None) -> str:
    """Wrap user code in the figure/data capture prologue/epilogue."""
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
    return _WRAPPER_PROLOGUE + indented + _WRAPPER_EPILOGUE


def parse_result(stdout: str, stderr: str,
                 return_code: int, elapsed_ms: float) -> SandboxResult:
    """Parse sandbox stdout/stderr into a SandboxResult."""
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
            parsed = _json.loads(match.group(1))
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


def save_figures_to_disk(figures: list[dict], output_dir: Path):
    """Decode base64 figures and write them to disk."""
    for fig in figures:
        try:
            b64 = fig.get("b64", "")
            if b64:
                img_bytes = base64.b64decode(b64)
                path = output_dir / f"{fig['id']}.png"
                path.write_bytes(img_bytes)
                fig["path"] = str(path.resolve())
        except Exception as e:
            logger.warning("Failed to save figure %s: %s", fig.get("id"), e)


def _get_python_exe() -> str:
    """Get Python interpreter path, PyInstaller compatible."""
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
        for name in ["python", "python3"]:
            found = shutil.which(name)
            if found:
                logger.warning("PyInstaller: using system Python %s", found)
                return found
        raise RuntimeError(
            "PyInstaller env: no Python interpreter found. "
            "Sandbox requires a bundled or system Python."
        )
    return exe


def _sandbox_env() -> dict:
    """Build a clean environment dict for sandbox subprocesses."""
    env = dict(os.environ)
    for var in ["PYTHONPATH", "PYTHONSTARTUP", "PYTHONHOME",
                "LD_PRELOAD", "LD_LIBRARY_PATH"]:
        env.pop(var, None)
    env["MPLBACKEND"] = "Agg"
    env["MATPLOTLIBRC"] = "/nonexistent"
    env["LC_ALL"] = "C"
    return env


# ---------------------------------------------------------------------------
# SandboxProvider ABC
# ---------------------------------------------------------------------------


class SandboxProvider(ABC):
    """Abstract base for sandbox execution backends."""

    @abstractmethod
    def execute_python(
        self,
        code: str,
        input_data: str = "",
        context: dict | None = None,
    ) -> SandboxResult:
        ...

    @abstractmethod
    def execute_r(self, code: str, input_data: str = "") -> SandboxResult:
        ...

    @abstractmethod
    def clean(self):
        ...


# ---------------------------------------------------------------------------
# SubprocessProvider
# ---------------------------------------------------------------------------


class SubprocessProvider(SandboxProvider):
    """Sandbox execution via local subprocess."""

    def __init__(
        self,
        timeout: int = 30,
        work_dir: Path | None = None,
        figure_output_dir: Path | None = None,
    ):
        self.timeout = timeout
        self.work_dir = work_dir or Path(tempfile.mkdtemp(prefix="sandbox_"))
        self.figure_output_dir = figure_output_dir or (self.work_dir / "figures")
        self.figure_output_dir.mkdir(parents=True, exist_ok=True)

    def execute_python(
        self,
        code: str,
        input_data: str = "",
        context: dict | None = None,
    ) -> SandboxResult:
        start = time.perf_counter()
        wrapped = build_wrapper(code, context)
        script_path = self.work_dir / "sandbox_script.py"
        script_path.write_text(wrapped, encoding="utf-8")

        try:
            result = subprocess.run(
                [_get_python_exe(), str(script_path)],
                input=input_data,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
                cwd=str(self.work_dir),
                env=_sandbox_env(),
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.perf_counter() - start) * 1000
            logger.warning("Subprocess sandbox timeout after %ss", self.timeout)
            return SandboxResult(
                success=False,
                stderr=f"Execution timeout ({self.timeout}s)",
                return_code=-1,
                execution_time_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.exception("Subprocess sandbox error")
            return SandboxResult(
                success=False,
                stderr=str(e),
                return_code=-1,
                execution_time_ms=elapsed,
            )

        elapsed_ms = (time.perf_counter() - start) * 1000
        sr = parse_result(result.stdout, result.stderr,
                          result.returncode, elapsed_ms)
        save_figures_to_disk(sr.figures, self.figure_output_dir)
        return sr

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
                stderr=f"R execution timeout ({self.timeout}s)",
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


# ---------------------------------------------------------------------------
# DockerProvider
# ---------------------------------------------------------------------------


class DockerProvider(SandboxProvider):
    """Sandbox execution via Docker container."""

    def __init__(
        self,
        timeout: int = 30,
        max_memory_mb: int = 512,
        image: str = "research-agent-sandbox:latest",
        work_dir: Path | None = None,
    ):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.image = image
        self.work_dir = work_dir or Path(tempfile.mkdtemp(prefix="sandbox_docker_"))

    def execute_python(
        self,
        code: str,
        input_data: str = "",
        context: dict | None = None,
    ) -> SandboxResult:
        if not shutil.which("docker"):
            logger.warning("Docker not available, falling back to subprocess")
            return SubprocessProvider(timeout=self.timeout, work_dir=self.work_dir).execute_python(code, input_data, context)

        start = time.perf_counter()

        try:
            result = subprocess.run(
                ["docker", "run", "--rm",
                 "--network", "none",
                 "--memory", f"{self.max_memory_mb}m",
                 "--cpus", "1",
                 "-i",
                 self.image,
                 "python3"],
                input=code,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.work_dir),
            )
        except subprocess.TimeoutExpired:
            elapsed = (time.perf_counter() - start) * 1000
            logger.warning("Docker sandbox timeout after %ss", self.timeout)
            return SandboxResult(
                success=False,
                stderr=f"Execution timeout ({self.timeout}s) in Docker",
                return_code=-1,
                execution_time_ms=elapsed,
            )
        except FileNotFoundError:
            logger.warning("Docker binary not found, falling back")
            return SubprocessProvider(timeout=self.timeout, work_dir=self.work_dir).execute_python(code, input_data, context)
        except Exception as e:
            logger.exception("Docker sandbox error, falling back")
            return SubprocessProvider(timeout=self.timeout, work_dir=self.work_dir).execute_python(code, input_data, context)

        elapsed_ms = (time.perf_counter() - start) * 1000
        return SandboxResult(
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            return_code=result.returncode,
            execution_time_ms=elapsed_ms,
        )

    def execute_r(self, code: str, input_data: str = "") -> SandboxResult:
        return SubprocessProvider(timeout=self.timeout, work_dir=self.work_dir).execute_r(code, input_data)

    def clean(self):
        if self.work_dir and self.work_dir.exists():
            shutil.rmtree(str(self.work_dir), ignore_errors=True)


# ---------------------------------------------------------------------------
# KubernetesProvider  — multi-tenant sandbox via K8s Jobs
# ---------------------------------------------------------------------------

try:
    import kubernetes as k8s
    _HAS_K8S_CLIENT = True
except ImportError:
    _HAS_K8S_CLIENT = False


class KubernetesProvider(SandboxProvider):
    """Sandbox execution via ephemeral Kubernetes Jobs.

    Each execution creates a short-lived K8s Job in the configured namespace.
    The Job runs the sandbox image with the user code passed via a ConfigMap.

    Requires the ``kubernetes`` Python package and a valid kubeconfig.
    """

    def __init__(
        self,
        timeout: int = 60,
        image: str = "research-agent-sandbox:latest",
        namespace: str = "research-agent-sandbox",
        kubeconfig_path: str | None = None,
        in_cluster: bool = False,
        cpu_request: str = "500m",
        cpu_limit: str = "2",
        memory_request: str = "512Mi",
        memory_limit: str = "2Gi",
        tenant_id: str = "default",
    ):
        self.timeout = timeout
        self.image = image
        self.namespace = namespace
        self.tenant_id = tenant_id
        self.cpu_request = cpu_request
        self.cpu_limit = cpu_limit
        self.memory_request = memory_request
        self.memory_limit = memory_limit
        self._job_names: list[str] = []

        if not _HAS_K8S_CLIENT:
            raise RuntimeError(
                "kubernetes Python package is required. "
                "Install with: pip install kubernetes"
            )

        if in_cluster:
            k8s.config.load_incluster_config()
        else:
            k8s.config.load_kube_config(config_file=kubeconfig_path)

        self._batch_v1 = k8s.client.BatchV1Api()
        self._core_v1 = k8s.client.CoreV1Api()

    # ---- provider interface ----

    def execute_python(
        self,
        code: str,
        input_data: str = "",
        context: dict | None = None,
    ) -> SandboxResult:
        wrapped = build_wrapper(code, context)
        return self._run_job(wrapped, input_data)

    def execute_r(self, code: str, input_data: str = "") -> SandboxResult:
        return self._run_job(code, input_data, lang="R")

    def clean(self):
        """Clean up all created Jobs and ConfigMaps."""
        for name in self._job_names:
            try:
                self._batch_v1.delete_namespaced_job(
                    name=name,
                    namespace=self.namespace,
                    propagation_policy="Background",
                )
            except Exception:
                pass
            try:
                self._core_v1.delete_namespaced_config_map(
                    name=name,
                    namespace=self.namespace,
                )
            except Exception:
                pass
        self._job_names.clear()

    # ---- internal ----

    def _run_job(self, code: str, input_data: str = "",
                 lang: str = "python") -> SandboxResult:
        import uuid as _uuid
        job_name = f"sandbox-{self.tenant_id}-{_uuid.uuid4().hex[:8]}"
        self._job_names.append(job_name)

        # 1. ConfigMap — store the code
        cm = k8s.client.V1ConfigMap(
            metadata=k8s.client.V1ObjectMeta(
                name=job_name,
                namespace=self.namespace,
                labels={
                    "app": "research-agent-sandbox",
                    "tenant": self.tenant_id,
                },
            ),
            data={"code.py": code},
        )
        self._core_v1.create_namespaced_config_map(
            namespace=self.namespace, body=cm
        )

        cmd = ["python3", "/mnt/code/code.py"]
        if lang.upper() == "R":
            cmd = ["Rscript", "/mnt/code/code.R"]

        # 2. Job pod spec
        pod_spec = k8s.client.V1PodSpec(
            restart_policy="Never",
            containers=[
                k8s.client.V1Container(
                    name="sandbox",
                    image=self.image,
                    command=cmd,
                    volume_mounts=[
                        k8s.client.V1VolumeMount(
                            name="code", mount_path="/mnt/code"
                        )
                    ],
                    resources=k8s.client.V1ResourceRequirements(
                        requests={
                            "cpu": self.cpu_request,
                            "memory": self.memory_request,
                        },
                        limits={
                            "cpu": self.cpu_limit,
                            "memory": self.memory_limit,
                        },
                    ),
                    security_context=k8s.client.V1SecurityContext(
                        run_as_non_root=True,
                        read_only_root_filesystem=True,
                    ),
                )
            ],
            volumes=[
                k8s.client.V1Volume(
                    name="code",
                    config_map=k8s.client.V1ConfigMapVolumeSource(
                        name=job_name,
                    ),
                )
            ],
        )

        job = k8s.client.V1Job(
            metadata=k8s.client.V1ObjectMeta(
                name=job_name,
                namespace=self.namespace,
                labels={
                    "app": "research-agent-sandbox",
                    "tenant": self.tenant_id,
                },
            ),
            spec=k8s.client.V1JobSpec(
                backoff_limit=0,
                ttl_seconds_after_finished=300,
                template=k8s.client.V1PodTemplateSpec(
                    metadata=k8s.client.V1ObjectMeta(
                        labels={
                            "app": "research-agent-sandbox",
                            "tenant": self.tenant_id,
                        }
                    ),
                    spec=pod_spec,
                ),
            ),
        )

        start = time.perf_counter()
        self._batch_v1.create_namespaced_job(
            namespace=self.namespace, body=job
        )

        # 3. Wait for completion
        try:
            self._wait_for_job(job_name, start)
        except SandboxError as e:
            elapsed = (time.perf_counter() - start) * 1000
            return SandboxResult(
                success=False,
                stderr=str(e),
                return_code=-1,
                execution_time_ms=elapsed,
            )

        # 4. Collect logs
        elapsed_ms = (time.perf_counter() - start) * 1000
        try:
            pod_name = self._get_pod_name(job_name)
            log_data = self._core_v1.read_namespaced_pod_log(
                name=pod_name,
                namespace=self.namespace,
            )
        except Exception as e:
            return SandboxResult(
                success=False,
                stderr=f"Failed to collect logs: {e}",
                return_code=-1,
                execution_time_ms=elapsed_ms,
            )

        return parse_result(
            stdout=log_data,
            stderr="",
            return_code=0,
            elapsed_ms=elapsed_ms,
        )

    def _wait_for_job(self, job_name: str, start: float):
        """Block until the Job completes or the timeout expires."""
        import time as _time
        while True:
            if _time.perf_counter() - start > self.timeout:
                raise SandboxError(
                    f"K8s Job timeout after {self.timeout}s"
                )
            _time.sleep(1.0)
            api_response = self._batch_v1.read_namespaced_job_status(
                name=job_name,
                namespace=self.namespace,
            )
            status = api_response.status
            if status.succeeded and status.succeeded >= 1:
                return
            if status.failed and status.failed >= 1:
                try:
                    pod_name = self._get_pod_name(job_name)
                    logs = self._core_v1.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=self.namespace,
                    )
                except Exception:
                    logs = ""
                raise SandboxError(
                    f"K8s Job failed (backoff). Logs:\n{logs[:2000]}"
                )

    def _get_pod_name(self, job_name: str) -> str:
        """Get the first (only) Pod name created by the Job."""
        pods = self._core_v1.list_namespaced_pod(
            namespace=self.namespace,
            label_selector=f"job-name={job_name}",
        )
        if not pods.items:
            raise SandboxError(f"No pods found for job {job_name}")
        return pods.items[0].metadata.name
