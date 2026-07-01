"""
文件上传 API

提供文件上传端点，将文件保存到 data/uploads/ 目录，
返回可通过静态挂载路径访问的 URL。
"""

from __future__ import annotations

import uuid
import os
import mimetypes
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter()

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "data" / "uploads"


@router.post("/upload", summary="Upload file")
async def upload_file(file: UploadFile = File(...)):
    """上传文件并返回可访问的 URL"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename cannot be empty")

    # 确保上传目录存在
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 生成唯一文件名，保留扩展名
    ext = os.path.splitext(file.filename)[1] or ""
    unique_name = f"{uuid.uuid4().hex}{ext}"
    save_path = UPLOAD_DIR / unique_name

    # 保存文件
    content = await file.read()
    save_path.write_bytes(content)

    # 获取 MIME 类型
    mime_type, _ = mimetypes.guess_type(file.filename)
    if mime_type is None:
        mime_type = "application/octet-stream"

    return {
        "url": f"/uploads/{unique_name}",
        "filename": file.filename,
        "size": len(content),
        "mime_type": mime_type,
    }
