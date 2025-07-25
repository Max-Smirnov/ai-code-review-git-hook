"""
AWS Bedrock integration for AI Code Review
"""

from .client import BedrockClient
from .models import ModelManager

__all__ = [
    "BedrockClient",
    "ModelManager",
]