"""
统一异常体系。

定义业务异常基类和常见子类，供全局异常处理器捕获。
"""
from __future__ import annotations

from typing import Any, Optional


class AppException(Exception):
    """业务异常基类。"""

    def __init__(
        self,
        code: str = "INTERNAL_ERROR",
        message: str = "服务器内部错误",
        status_code: int = 500,
        detail: Any = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.detail = detail

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "detail": self.detail,
        }


class NotFoundError(AppException):
    """资源未找到"""

    def __init__(self, resource: str = "资源", resource_id: str = ""):
        msg = f"{resource}未找到" + (f": {resource_id}" if resource_id else "")
        super().__init__(code="NOT_FOUND", message=msg, status_code=404)


class ValidationError(AppException):
    """请求参数校验失败"""

    def __init__(self, message: str = "请求参数校验失败", detail: Any = None):
        super().__init__(code="VALIDATION_ERROR", message=message, status_code=422, detail=detail)


class ConfigError(AppException):
    """配置缺失或错误"""

    def __init__(self, key: str = ""):
        msg = f"配置项缺失: {key}" if key else "配置错误"
        super().__init__(code="CONFIG_ERROR", message=msg, status_code=500)


class ModelError(AppException):
    """AI 模型调用异常"""

    def __init__(self, model_id: str = "", detail: Any = None):
        msg = f"模型 {model_id} 调用失败" if model_id else "模型调用失败"
        super().__init__(code="MODEL_ERROR", message=msg, status_code=502, detail=detail)


class RateLimitError(AppException):
    """频率限制"""

    def __init__(self, message: str = "请求过于频繁，请稍后重试"):
        super().__init__(code="RATE_LIMITED", message=message, status_code=429)
