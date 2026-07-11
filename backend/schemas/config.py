"""API Key Pydantic models."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ApiKeysStatusResponse(BaseModel):
    """Return API key config status for each model (boolean only, no actual key)."""
    deepseek: bool = Field(False)
    kimi: bool = Field(False)
    openai: bool = Field(False)


class ApiKeysUpdateRequest(BaseModel):
    """Request body for updating API keys. Omitted fields are not updated."""
    deepseek_api_key: Optional[str] = Field(None)
    kimi_api_key: Optional[str] = Field(None)
    openai_api_key: Optional[str] = Field(None)