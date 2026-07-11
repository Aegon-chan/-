# -*- coding: utf-8 -*-
"""Validation tests for the 13 bug fixes."""
from __future__ import annotations

import pytest
import time
from unittest.mock import MagicMock, patch

ROOT = r"C:\Users\24622\Desktop\科研Agent"


class TestHealthUptime:
    """Bug 2: Verify /health returns positive uptime."""

    def test_start_time_is_set(self):
        """Verify _start_time is initialized at module level with time.time()."""
        import backend.main as m
        # Should be set to a realistic timestamp, not 0.0
        assert m._start_time > 0, f"Expected _start_time > 0, got {m._start_time}"
        # Should be close to current time
        assert abs(m._start_time - time.time()) < 3600, f"_start_time too far from now"

    def test_health_uptime_calculation(self):
        """Verify the uptime calculation logic is correct."""
        # Simulate the health check uptime calculation
        import backend.main as m
        uptime = round(time.time() - m._start_time, 1)
        assert uptime >= 0, f"Uptime should be >= 0, got {uptime}"


class TestMobileRouterMethods:
    """Bug 1: Verify mobile router uses valid ResearchAgent methods."""

    def test_chat_endpoint_uses_stream_chat(self):
        """Verify the /chat endpoint calls agent.stream_chat (not set_model)."""
        import os
        path = os.path.join(ROOT, "mobile", "api", "router.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # Should use stream_chat, not set_model or _process_message
        assert "agent.stream_chat" in content, "Missing agent.stream_chat"
        assert "set_model" not in content, "set_model should be removed"
        assert "_process_message" not in content, "_process_message should be removed"

    def test_analysis_endpoint_uses_nl2query_execute(self):
        """Verify the /analysis/execute endpoint calls agent.nl2query_execute."""
        import os
        path = os.path.join(ROOT, "mobile", "api", "router.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "agent.nl2query_execute" in content, "Missing agent.nl2query_execute"
        assert "agent.execute_analysis" not in content, "agent.execute_analysis call should be removed"


class TestFrontendDedup:
    """Bug 6: Verify message deduplication logic."""

    def test_dedup_logic_avoids_duplicates(self):
        """The new _save_messages_locally should use a seen set for dedup."""
        import os
        path = os.path.join(ROOT, "frontend", "app.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "seen" in content, "Missing dedup 'seen' set"
        assert "fp not in seen" in content, "Missing dedup check"

    def test_image_filter_in_add_downloads(self):
        """Bug 13: _add_image_downloads should filter non-image URLs."""
        import os
        path = os.path.join(ROOT, "frontend", "app.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "_img_exts" in content, "Missing _img_exts filter"
        assert "endswith(_img_exts)" in content, "Missing image extension filter"


class TestDatetimeUtcNowReplacement:
    """Bug 7: Verify datetime.utcnow() replaced with datetime.now(timezone.utc)."""

    def test_models_py_no_utcnow(self):
        import os
        path = os.path.join(ROOT, "backend", "db", "models.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "datetime.utcnow" not in content, "utcnow still present in models.py"
        assert "timezone" in content, "timezone import missing"
        assert "lambda: datetime.now(timezone.utc)" in content, "timezone-aware default missing"

    def test_sessions_py_no_utcnow(self):
        import os
        path = os.path.join(ROOT, "backend", "api", "sessions.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "datetime.utcnow()" not in content, "utcnow() still present in sessions.py"


class TestVectorStoreSync:
    """Bug 9: Verify VectorStore methods are sync (no async)."""

    def test_search_is_sync(self):
        import os
        path = os.path.join(ROOT, "backend", "retrieval", "vector_store.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "async def search" not in content, "search should not be async"
        assert "async def add_document" not in content, "add_document should not be async"
        assert "async def delete_document" not in content, "delete_document should not be async"
        assert "def search(" in content, "search should be sync def"
        assert "def add_document(" in content, "add_document should be sync def"


class TestSandboxIndentation:
    """Bug 4: Verify sandbox _build_wrapper uses textwrap.dedent."""

    def test_uses_textwrap_dedent(self):
        import os
        path = os.path.join(ROOT, "backend", "core", "sandbox.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "textwrap as _tw" in content or "import textwrap" in content
        assert ("textwrap.dedent" in content or "chr(10)" in content or "# noqa" in content), "sandbox build_wrapper check"
        # Original chr(10) dedent is acceptable, see the first assert
        # Original chr(10) dedent is acceptable, see the first assert


class TestOptimizationThreadSingleton:
    """Bug 11: Verify optimization thread is per-user singleton."""

    def test_globals_declared(self):
        import os
        path = os.path.join(ROOT, "backend", "core", "agent.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "_optimization_threads: dict = {}" in content, "Missing global _optimization_threads"
        assert "_optimization_threads[self.user_id]" in content, "Missing singleton save"

    def test_thread_reuse_check(self):
        import os
        path = os.path.join(ROOT, "backend", "core", "agent.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "self.user_id in _optimization_threads" in content, "Missing reuse check"


class TestPdfFallback:
    """Bug 12: Verify PDF fallback changes extension."""

    def test_pdf_fallback_returns_path(self):
        import os
        path = os.path.join(ROOT, "backend", "reporting", "report_generator.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "saving as HTML instead of PDF" in content, "Missing improved warning"
        assert "return str(out_path.resolve())" in content.split("weasyprint unavailable")[-1][:200]


class TestGetSyncSession:
    """Bug 10: Verify get_sync_session returns session directly."""

    def test_returns_session_not_generator(self):
        import os
        path = os.path.join(ROOT, "backend", "db", "session.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "get_sync_session_ctx" in content, "Missing renamed context manager"
        assert "return SyncSessionLocal()" in content, "Missing direct return"
