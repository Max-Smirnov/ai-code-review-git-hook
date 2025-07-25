"""
Core review engine for AI Code Review
"""

import json
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any
from dataclasses import asdict
from pathlib import Path

from ..git.operations import FileChange
from ..bedrock.client import BedrockClient, BedrockResponse
from ..config.manager import ConfigManager
from ..utils.exceptions import BedrockError, ValidationError
from ..utils.logging import get_logger, log_performance
from .rules import RuleProcessor
from .models import ReviewIssue, FileReviewResult, ReviewResult

logger = get_logger(__name__)


class ReviewEngine:
    """Core engine for performing AI-powered code reviews"""
    
    def __init__(self, config: ConfigManager):
        """
        Initialize review engine
        
        Args:
            config: Configuration manager
        """
        self.config = config
        self.bedrock_client = BedrockClient(config.get('bedrock'))
        self.rule_processor = RuleProcessor(config)
        
        # Review configuration
        self.review_config = config.get('review', {})
        self.enabled_rules = self.review_config.get('enabled_rules', [])
        self.severity_threshold = self.review_config.get('severity_threshold', 'warning')
        self.max_issues_per_file = self.review_config.get('max_issues_per_file', 10)
        self.batch_size = self.review_config.get('batch_size', 5)
        
        # Performance configuration
        self.perf_config = config.get('performance', {})
        self.parallel_processing = self.perf_config.get('parallel_processing', True)
        self.max_workers = self.perf_config.get('max_workers', 4)
    
    @log_performance
    def review_changes(self, changes: Dict[str, FileChange]) -> ReviewResult:
        """
        Review all changed files
        
        Args:
            changes: Dictionary of filename -> FileChange
            
        Returns:
            ReviewResult with all review findings
        """
        logger.info(f"Starting review of {len(changes)} files")
        
        if not changes:
            return self._create_empty_result()
        
        # Process files in parallel if enabled
        if self.parallel_processing and len(changes) > 1:
            file_results = self._review_files_parallel(changes)
        else:
            file_results = self._review_files_sequential(changes)
        
        # Aggregate results
        result = self._aggregate_results(file_results)
        
        logger.info(f"Review completed: {result.total_issues} issues found across {result.total_files} files")
        return result
    
    def _review_files_parallel(self, changes: Dict[str, FileChange]) -> Dict[str, FileReviewResult]:
        """Review files in parallel"""
        logger.debug(f"Processing {len(changes)} files in parallel with {self.max_workers} workers")
        
        file_results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit batches of files
            futures = {}
            
            file_items = list(changes.items())
            for i in range(0, len(file_items), self.batch_size):
                batch = dict(file_items[i:i + self.batch_size])
                future = executor.submit(self._review_file_batch, batch)
                futures[future] = list(batch.keys())
            
            # Collect results
            for future in as_completed(futures):
                try:
                    batch_results = future.result()
                    file_results.update(batch_results)
                except Exception as e:
                    filenames = futures[future]
                    logger.error(f"Failed to review batch {filenames}: {e}")
                    # Create error results for failed files
                    for filename in filenames:
                        file_results[filename] = self._create_error_result(filename, str(e))
        
        return file_results
    
    def _review_files_sequential(self, changes: Dict[str, FileChange]) -> Dict[str, FileReviewResult]:
        """Review files sequentially"""
        logger.debug(f"Processing {len(changes)} files sequentially")
        
        file_results = {}
        
        for filename, change in changes.items():
            try:
                result = self._review_single_file(filename, change)
                file_results[filename] = result
            except Exception as e:
                logger.error(f"Failed to review {filename}: {e}")
                file_results[filename] = self._create_error_result(filename, str(e))
        
        return file_results
    
    def _review_file_batch(self, batch: Dict[str, FileChange]) -> Dict[str, FileReviewResult]:
        """Review a batch of files"""
        results = {}
        
        for filename, change in batch.items():
            try:
                result = self._review_single_file(filename, change)
                results[filename] = result
            except Exception as e:
                logger.error(f"Failed to review {filename}: {e}")
                results[filename] = self._create_error_result(filename, str(e))
        
        return results
    
    def _review_single_file(self, filename: str, change: FileChange) -> FileReviewResult:
        """
        Review a single file
        
        Args:
            filename: File path
            change: FileChange object
            
        Returns:
            FileReviewResult
        """
        logger.debug(f"Reviewing file: {filename}")
        
        # Get applicable rules for this file
        rule_templates = self.config.get_rule_templates(filename)
        if not rule_templates:
            logger.debug(f"No rule templates found for {filename}")
            return self._create_empty_file_result(filename)
        
        # Load and process rules
        rules = self.rule_processor.load_rules_for_file(filename, rule_templates)
        if not rules:
            logger.debug(f"No applicable rules for {filename}")
            return self._create_empty_file_result(filename)
        
        # Build review prompt
        prompt = self._build_review_prompt(filename, change, rules)
        system_prompt = self._build_system_prompt(rules)
        
        # Call Bedrock API
        try:
            response = self.bedrock_client.invoke_model(prompt, system_prompt)
            return self._parse_review_response(filename, response, rules)
        except BedrockError as e:
            logger.error(f"Bedrock error reviewing {filename}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error reviewing {filename}: {e}")
            raise
    
    def _build_review_prompt(self, filename: str, change: FileChange, rules: Dict[str, Any]) -> str:
        """Build review prompt for a file"""
        prompt_parts = [
            "Please review the following code changes and provide feedback according to the specified rules.",
            "",
            f"**File:** {filename}",
            f"**Change Type:** {self._get_change_type_description(change.status)}",
            f"**Lines Added:** {change.lines_added}",
            f"**Lines Removed:** {change.lines_removed}",
            "",
            "**Code Changes:**",
            "```diff",
            change.diff,
            "```",
            "",
            "**Review Criteria:**"
        ]
        
        # Add rule-specific prompts
        for rule_name, rule_config in rules.items():
            if rule_config.get('enabled', True):
                prompt_parts.append(f"\n**{rule_name.upper()}:**")
                prompt_parts.append(rule_config.get('prompt', ''))
        
        prompt_parts.extend([
            "",
            "**Response Format:**",
            "Please provide your review in the following JSON format:",
            "```json",
            "{",
            '  "issues": [',
            '    {',
            '      "rule": "security|performance|maintainability|style|documentation",',
            '      "severity": "error|warning|info|suggestion",',
            '      "line": <line_number_or_null>,',
            '      "message": "Description of the issue",',
            '      "suggestion": "How to fix it (optional)"',
            '    }',
            '  ],',
            '  "summary": "Overall assessment of the changes"',
            "}",
            "```",
            "",
            "**Important Guidelines:**",
            f"- Focus only on the changed lines and their immediate context",
            f"- Maximum {self.max_issues_per_file} issues per file",
            f"- Only report issues with severity >= {self.severity_threshold}",
            f"- Provide specific, actionable feedback",
            f"- Consider the file type and context when applying rules"
        ])
        
        return '\n'.join(prompt_parts)
    
    def _build_system_prompt(self, rules: Dict[str, Any]) -> str:
        """Build system prompt for the review"""
        return (
            "You are an expert code reviewer with deep knowledge of software engineering best practices, "
            "security vulnerabilities, performance optimization, and code maintainability. "
            "Your role is to provide constructive, specific, and actionable feedback on code changes. "
            "Focus on identifying real issues that could impact code quality, security, or maintainability. "
            "Be concise but thorough in your analysis."
        )
    
    def _get_change_type_description(self, status: str) -> str:
        """Get human-readable description of change type"""
        descriptions = {
            'A': 'Added (new file)',
            'M': 'Modified (existing file)',
            'D': 'Deleted (removed file)',
            'R': 'Renamed (moved file)',
            'C': 'Copied (duplicated file)'
        }
        return descriptions.get(status, f'Unknown ({status})')
    
    def _parse_review_response(self, filename: str, response: BedrockResponse, rules: Dict[str, Any]) -> FileReviewResult:
        """Parse Bedrock response into FileReviewResult"""
        try:
            # Extract JSON from response
            content = response.content.strip()
            
            # Find JSON block
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValidationError("No JSON found in response")
            
            json_content = content[json_start:json_end]
            parsed_response = json.loads(json_content)
            
            # Validate response structure
            if 'issues' not in parsed_response:
                raise ValidationError("Response missing 'issues' field")
            
            # Parse issues
            issues = []
            for issue_data in parsed_response.get('issues', []):
                try:
                    issue = ReviewIssue(
                        rule=issue_data.get('rule', 'unknown'),
                        severity=issue_data.get('severity', 'info'),
                        line=issue_data.get('line'),
                        message=issue_data.get('message', ''),
                        suggestion=issue_data.get('suggestion'),
                        file_path=filename
                    )
                    
                    # Validate severity
                    if issue.severity not in ['error', 'warning', 'info', 'suggestion']:
                        issue.severity = 'info'
                    
                    # Filter by severity threshold
                    if self._meets_severity_threshold(issue.severity):
                        issues.append(issue)
                        
                except Exception as e:
                    logger.warning(f"Failed to parse issue in {filename}: {e}")
                    continue
            
            # Limit number of issues
            if len(issues) > self.max_issues_per_file:
                logger.warning(f"Limiting {filename} to {self.max_issues_per_file} issues (found {len(issues)})")
                issues = issues[:self.max_issues_per_file]
            
            # Count issues by severity
            error_count = sum(1 for issue in issues if issue.severity == 'error')
            warning_count = sum(1 for issue in issues if issue.severity == 'warning')
            info_count = sum(1 for issue in issues if issue.severity == 'info')
            suggestion_count = sum(1 for issue in issues if issue.severity == 'suggestion')
            
            return FileReviewResult(
                filename=filename,
                issues=issues,
                summary=parsed_response.get('summary', 'No summary provided'),
                total_issues=len(issues),
                error_count=error_count,
                warning_count=warning_count,
                info_count=info_count,
                suggestion_count=suggestion_count,
                tokens_used=response.input_tokens + response.output_tokens,
                cost_estimate=response.cost_estimate
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response for {filename}: {e}")
            return self._create_error_result(filename, f"Invalid JSON response: {e}")
        except ValidationError as e:
            logger.error(f"Invalid response format for {filename}: {e}")
            return self._create_error_result(filename, f"Invalid response format: {e}")
        except Exception as e:
            logger.error(f"Unexpected error parsing response for {filename}: {e}")
            return self._create_error_result(filename, f"Parsing error: {e}")
    
    def _meets_severity_threshold(self, severity: str) -> bool:
        """Check if severity meets the configured threshold"""
        severity_levels = {'suggestion': 1, 'info': 2, 'warning': 3, 'error': 4}
        threshold_level = severity_levels.get(self.severity_threshold, 3)
        issue_level = severity_levels.get(severity, 2)
        return issue_level >= threshold_level
    
    def _create_empty_result(self) -> ReviewResult:
        """Create empty review result"""
        return ReviewResult(
            files={},
            total_files=0,
            total_issues=0,
            total_errors=0,
            total_warnings=0,
            total_info=0,
            total_suggestions=0,
            total_tokens=0,
            total_cost=0.0,
            summary="No files to review"
        )
    
    def _create_empty_file_result(self, filename: str) -> FileReviewResult:
        """Create empty file review result"""
        return FileReviewResult(
            filename=filename,
            issues=[],
            summary="No issues found",
            total_issues=0,
            error_count=0,
            warning_count=0,
            info_count=0,
            suggestion_count=0,
            tokens_used=0,
            cost_estimate=0.0
        )
    
    def _create_error_result(self, filename: str, error_message: str) -> FileReviewResult:
        """Create error result for a file"""
        error_issue = ReviewIssue(
            rule="system",
            severity="error",
            line=None,
            message=f"Review failed: {error_message}",
            file_path=filename
        )
        
        return FileReviewResult(
            filename=filename,
            issues=[error_issue],
            summary=f"Review failed: {error_message}",
            total_issues=1,
            error_count=1,
            warning_count=0,
            info_count=0,
            suggestion_count=0,
            tokens_used=0,
            cost_estimate=0.0
        )
    
    def _aggregate_results(self, file_results: Dict[str, FileReviewResult]) -> ReviewResult:
        """Aggregate file results into overall result"""
        total_files = len(file_results)
        total_issues = sum(result.total_issues for result in file_results.values())
        total_errors = sum(result.error_count for result in file_results.values())
        total_warnings = sum(result.warning_count for result in file_results.values())
        total_info = sum(result.info_count for result in file_results.values())
        total_suggestions = sum(result.suggestion_count for result in file_results.values())
        total_tokens = sum(result.tokens_used for result in file_results.values())
        total_cost = sum(result.cost_estimate for result in file_results.values())
        
        # Generate overall summary
        if total_issues == 0:
            summary = f"✅ No issues found in {total_files} files"
        else:
            summary = (f"Found {total_issues} issues in {total_files} files: "
                      f"{total_errors} errors, {total_warnings} warnings, "
                      f"{total_info} info, {total_suggestions} suggestions")
        
        return ReviewResult(
            files=file_results,
            total_files=total_files,
            total_issues=total_issues,
            total_errors=total_errors,
            total_warnings=total_warnings,
            total_info=total_info,
            total_suggestions=total_suggestions,
            total_tokens=total_tokens,
            total_cost=total_cost,
            summary=summary
        )