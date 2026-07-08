"""Mobile application adapter.

Provides lightweight REST API endpoints for mobile clients.
"""
from .api import router as mobile_router

__all__ = ["mobile_router"]
