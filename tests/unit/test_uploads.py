"""Tests for backend/uploads.py - file upload and processing"""
from __future__ import annotations

import os
import tempfile



class TestExtractText:
    """Test extract_text_from_file with various file types"""

    def test_extract_csv(self):
        from backend.uploads import extract_text_from_file
        with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
            f.write("a,b,c\n1,2,3\n4,5,6\n")
            fpath = f.name
        try:
            result = extract_text_from_file(fpath, "text/csv")
            assert "a" in result
            assert "1" in result
        finally:
            os.unlink(fpath)

    def test_extract_txt(self):
        from backend.uploads import extract_text_from_file
        with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
            f.write("Hello world\nLine 2\n")
            fpath = f.name
        try:
            result = extract_text_from_file(fpath, "text/plain")
            assert "Hello world" in result
        finally:
            os.unlink(fpath)

    def test_extract_binary_no_ext(self):
        """Test binary file should return a message without crashing"""
        from backend.uploads import extract_text_from_file
        result = extract_text_from_file("/tmp/test.bin", "application/octet-stream")
        assert isinstance(result, str)


class TestImageToDataUri:
    """Test image_to_data_uri conversion"""

    def test_convert_png(self):
        from backend.uploads import image_to_data_uri
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
            fpath = f.name
        try:
            result = image_to_data_uri(fpath)
            assert result.startswith("data:image/png;base64,")
        finally:
            os.unlink(fpath)


class TestProcessAttachments:
    """Test process_attachments function"""

    def test_empty_attachments(self):
        from backend.uploads import process_attachments
        result = process_attachments(None)
        assert result == []

    def test_empty_list(self):
        from backend.uploads import process_attachments
        result = process_attachments([])
        assert result == []
