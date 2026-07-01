"""Tests for CodeSandbox."""
from __future__ import annotations

import pytest
from backend.core.sandbox import CodeSandbox


class TestCodeSandbox:
    """Test sandbox execution and resource limits."""

    def test_init(self):
        sandbox = CodeSandbox()
        assert sandbox is not None

    def test_simple_execution(self):
        sandbox = CodeSandbox(timeout=10)
        code = "result = 1 + 1; print(result)"
        result = sandbox.execute_python(code)
        assert result.success is True
        assert "2" in result.stdout

    def test_failing_code(self):
        sandbox = CodeSandbox(timeout=10)
        code = "raise ValueError(""test error"")"
        result = sandbox.execute_python(code)
        assert result.success is False

    def test_timeout(self):
        sandbox = CodeSandbox(timeout=1)
        code = "import time; time.sleep(5)"
        result = sandbox.execute_python(code)
        assert result.success is False

    def test_syntax_error(self):
        sandbox = CodeSandbox(timeout=10)
        code = "if True print(""no colon"")"
        result = sandbox.execute_python(code)
        assert result.success is False

    def test_safe_imports(self):
        sandbox = CodeSandbox(timeout=10)
        code = "import os; print(os.name)"
        result = sandbox.execute_python(code)
        assert result.success is True

    def test_output_capture(self):
        sandbox = CodeSandbox(timeout=10)
        code = "x = 42; print(f'x={x}'); import json; data = {'key': 'value'}; print(json.dumps(data))"
        result = sandbox.execute_python(code)
        assert result.success is True
        assert "x=42" in result.stdout
        assert "value" in result.stdout

    def test_result_return(self):
        sandbox = CodeSandbox(timeout=10)
        code = "result = 42\nresult"
        result = sandbox.execute_python(code)
        assert result.success is True

    def test_multiple_executions(self):
        sandbox = CodeSandbox(timeout=10)
        r1 = sandbox.execute_python("x = 10; print(x)")
        assert r1.success is True
        assert "10" in r1.stdout
        # Each sandbox execution is a separate subprocess; chain operations in one call
        r2 = sandbox.execute_python("x = 10; y = x + 5; print(y)")
        assert r2.success is True
        assert "15" in r2.stdout
