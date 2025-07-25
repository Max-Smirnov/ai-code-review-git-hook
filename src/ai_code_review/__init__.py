"""
AI Code Review Git Hook

A Python-based git pre-push hook that performs AI-powered code review
using AWS Bedrock APIs with configurable rules and interactive feedback.
"""

__version__ = "0.1.0"
__author__ = "AI Code Review Team"
__email__ = "contact@example.com"

# Package-level imports
from .config.manager import ConfigManager
from .utils.exceptions import (
    AICodeReviewError,
    ConfigurationError,
    GitError,
    BedrockError,
    NetworkError
)

__all__ = [
    "ConfigManager",
    "AICodeReviewError",
    "ConfigurationError", 
    "GitError",
    "BedrockError",
    "NetworkError",
]