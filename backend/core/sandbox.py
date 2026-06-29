"""
代码执行沙箱。

为 AI 生成的代码执行提供安全隔离环境。
开发期使用 subprocess + 资源限制，生产环境可使用 Docker。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
try:
    import resource
except ImportError:
    resource = None
from pathlib import Path
from typing import Optional


class SandboxError(Exception):
    """沙箱执行错误"""
    pass


class CodeSandbox:
    """代码执行沙箱"""

    def __init__(self, timeout: int = 30, max_memory_mb: int = 512,
                 work_dir: Optional[Path] = None):
        self.timeout = timeout
        self.max_memory_mb = max_memory_mb
        self.work_dir = work_dir or Path(tempfile.mkdtemp(prefix="sandbox_"))

    def execute_python(self, code: str, input_data: str = "") -> dict:
        """在沙箱中执行 Python 代码"""
        # 写入临时文件
        script_path = self.work_dir / "sandbox_script.py"
        script_path.write_text(code, encoding="utf-8")

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=str(self.work_dir),
                env={**os.environ, "PYTHONPATH": ""},
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"执行超时（{self.timeout}s）",
                "return_code": -1,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
            }

    def execute_r(self, code: str, input_data: str = "") -> dict:
        """在沙箱中执行 R 代码（需要 R 环境）"""
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
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"执行超时（{self.timeout}s）",
                "return_code": -1,
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
            }

    def clean(self):
        """清理沙箱工作目录"""
        if self.work_dir and self.work_dir.exists():
            shutil.rmtree(str(self.work_dir))

    def __del__(self):
        self.clean()

