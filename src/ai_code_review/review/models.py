"""
Data models for AI Code Review
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class ReviewIssue:
    """Represents a code review issue"""
    rule: str
    severity: str  # error, warning, info, suggestion
    line: Optional[int]
    message: str
    suggestion: Optional[str] = None
    file_path: Optional[str] = None


@dataclass
class FileReviewResult:
    """Result of reviewing a single file"""
    filename: str
    issues: List[ReviewIssue]
    summary: str
    total_issues: int
    error_count: int
    warning_count: int
    info_count: int
    suggestion_count: int
    tokens_used: int
    cost_estimate: float


@dataclass
class ReviewResult:
    """Complete review result"""
    files: Dict[str, FileReviewResult]
    total_files: int
    total_issues: int
    total_errors: int
    total_warnings: int
    total_info: int
    total_suggestions: int
    total_tokens: int
    total_cost: float
    summary: str