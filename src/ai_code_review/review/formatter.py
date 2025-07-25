"""
Result formatter for AI Code Review
"""

from typing import Dict, List, Any, Optional
from dataclasses import asdict
import json

from .models import ReviewResult, FileReviewResult, ReviewIssue
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ResultFormatter:
    """Formats review results for display and output"""
    
    def __init__(self, config):
        """
        Initialize result formatter
        
        Args:
            config: Configuration manager
        """
        self.config = config
        self.ui_config = config.get('ui', {})
        
        # UI configuration
        self.color_output = self.ui_config.get('color_output', True)
        self.show_diff_context = self.ui_config.get('show_diff_context', True)
        self.max_display_issues = self.ui_config.get('max_display_issues', 20)
        self.summary_only = self.ui_config.get('summary_only', False)
    
    def format_review_result(self, result: ReviewResult, format_type: str = 'terminal') -> str:
        """
        Format complete review result
        
        Args:
            result: ReviewResult to format
            format_type: Output format (terminal, json, markdown)
            
        Returns:
            Formatted string
        """
        if format_type == 'json':
            return self._format_json(result)
        elif format_type == 'markdown':
            return self._format_markdown(result)
        else:
            return self._format_terminal(result)
    
    def _format_terminal(self, result: ReviewResult) -> str:
        """Format for terminal display with colors"""
        lines = []
        
        # Header
        lines.append(self._format_header(result))
        lines.append("")
        
        if result.total_issues == 0:
            lines.append(self._colorize("✅ No issues found!", 'green'))
            lines.append("")
            lines.append(self._format_summary_stats(result))
            return '\n'.join(lines)
        
        # Summary stats
        lines.append(self._format_summary_stats(result))
        lines.append("")
        
        if self.summary_only:
            return '\n'.join(lines)
        
        # File results
        displayed_issues = 0
        for filename, file_result in result.files.items():
            if file_result.total_issues == 0:
                continue
            
            # File header
            lines.append(self._format_file_header(file_result))
            
            # Issues
            for issue in file_result.issues:
                if displayed_issues >= self.max_display_issues:
                    remaining = sum(fr.total_issues for fr in result.files.values()) - displayed_issues
                    lines.append(f"... and {remaining} more issues (use --all to see all)")
                    break
                
                lines.append(self._format_issue(issue))
                displayed_issues += 1
            
            lines.append("")
            
            if displayed_issues >= self.max_display_issues:
                break
        
        # Footer
        lines.append(self._format_footer(result))
        
        return '\n'.join(lines)
    
    def _format_json(self, result: ReviewResult) -> str:
        """Format as JSON"""
        # Convert dataclasses to dictionaries
        result_dict = asdict(result)
        return json.dumps(result_dict, indent=2, default=str)
    
    def _format_markdown(self, result: ReviewResult) -> str:
        """Format as Markdown"""
        lines = []
        
        # Title
        lines.append("# AI Code Review Results")
        lines.append("")
        
        # Summary
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Files reviewed:** {result.total_files}")
        lines.append(f"- **Total issues:** {result.total_issues}")
        lines.append(f"- **Errors:** {result.total_errors}")
        lines.append(f"- **Warnings:** {result.total_warnings}")
        lines.append(f"- **Info:** {result.total_info}")
        lines.append(f"- **Suggestions:** {result.total_suggestions}")
        lines.append(f"- **Estimated cost:** ${result.total_cost:.4f}")
        lines.append("")
        
        if result.total_issues == 0:
            lines.append("✅ **No issues found!**")
            return '\n'.join(lines)
        
        # Issues by file
        lines.append("## Issues by File")
        lines.append("")
        
        for filename, file_result in result.files.items():
            if file_result.total_issues == 0:
                continue
            
            lines.append(f"### {filename}")
            lines.append("")
            lines.append(f"**Summary:** {file_result.summary}")
            lines.append("")
            
            if file_result.issues:
                lines.append("| Severity | Line | Rule | Message |")
                lines.append("|----------|------|------|---------|")
                
                for issue in file_result.issues:
                    line_num = str(issue.line) if issue.line else "N/A"
                    message = issue.message.replace('|', '\\|')  # Escape pipes for markdown
                    lines.append(f"| {issue.severity} | {line_num} | {issue.rule} | {message} |")
                
                lines.append("")
        
        return '\n'.join(lines)
    
    def _format_header(self, result: ReviewResult) -> str:
        """Format header section"""
        if self.color_output:
            return self._colorize("🔍 AI Code Review Results", 'blue', bold=True)
        else:
            return "AI Code Review Results"
    
    def _format_summary_stats(self, result: ReviewResult) -> str:
        """Format summary statistics"""
        lines = []
        
        # Basic stats
        stats_line = f"📊 Reviewed {result.total_files} files"
        if result.total_issues > 0:
            stats_line += f" • Found {result.total_issues} issues"
        
        lines.append(stats_line)
        
        # Issue breakdown
        if result.total_issues > 0:
            breakdown_parts = []
            if result.total_errors > 0:
                breakdown_parts.append(self._colorize(f"{result.total_errors} errors", 'red'))
            if result.total_warnings > 0:
                breakdown_parts.append(self._colorize(f"{result.total_warnings} warnings", 'yellow'))
            if result.total_info > 0:
                breakdown_parts.append(self._colorize(f"{result.total_info} info", 'blue'))
            if result.total_suggestions > 0:
                breakdown_parts.append(self._colorize(f"{result.total_suggestions} suggestions", 'green'))
            
            if breakdown_parts:
                lines.append(f"   └─ {' • '.join(breakdown_parts)}")
        
        # Cost info
        if result.total_cost > 0:
            cost_line = f"💰 Estimated cost: ${result.total_cost:.4f}"
            if result.total_tokens > 0:
                cost_line += f" ({result.total_tokens:,} tokens)"
            lines.append(cost_line)
        
        return '\n'.join(lines)
    
    def _format_file_header(self, file_result: FileReviewResult) -> str:
        """Format file header"""
        header = f"📄 {file_result.filename}"
        
        if file_result.total_issues > 0:
            issue_counts = []
            if file_result.error_count > 0:
                issue_counts.append(self._colorize(f"{file_result.error_count}E", 'red'))
            if file_result.warning_count > 0:
                issue_counts.append(self._colorize(f"{file_result.warning_count}W", 'yellow'))
            if file_result.info_count > 0:
                issue_counts.append(self._colorize(f"{file_result.info_count}I", 'blue'))
            if file_result.suggestion_count > 0:
                issue_counts.append(self._colorize(f"{file_result.suggestion_count}S", 'green'))
            
            if issue_counts:
                header += f" ({' '.join(issue_counts)})"
        
        return header
    
    def _format_issue(self, issue: ReviewIssue) -> str:
        """Format a single issue"""
        # Severity icon and color
        severity_info = {
            'error': ('❌', 'red'),
            'warning': ('⚠️', 'yellow'),
            'info': ('ℹ️', 'blue'),
            'suggestion': ('💡', 'green')
        }
        
        icon, color = severity_info.get(issue.severity, ('•', 'white'))
        
        # Build issue line
        parts = [icon]
        
        if issue.line:
            parts.append(f"Line {issue.line}:")
        
        parts.append(f"[{issue.rule.upper()}]")
        parts.append(issue.message)
        
        issue_line = ' '.join(parts)
        
        if self.color_output:
            issue_line = self._colorize(issue_line, color)
        
        lines = [f"  {issue_line}"]
        
        # Add suggestion if available
        if issue.suggestion:
            suggestion_line = f"    💡 Suggestion: {issue.suggestion}"
            if self.color_output:
                suggestion_line = self._colorize(suggestion_line, 'cyan')
            lines.append(suggestion_line)
        
        return '\n'.join(lines)
    
    def _format_footer(self, result: ReviewResult) -> str:
        """Format footer section"""
        lines = []
        
        if result.total_issues > 0:
            if result.total_errors > 0:
                lines.append(self._colorize("❌ Push blocked due to errors", 'red', bold=True))
            else:
                lines.append(self._colorize("⚠️ Issues found but push can continue", 'yellow', bold=True))
        else:
            lines.append(self._colorize("✅ All checks passed", 'green', bold=True))
        
        return '\n'.join(lines)
    
    def _colorize(self, text: str, color: str, bold: bool = False) -> str:
        """Apply color to text if color output is enabled"""
        if not self.color_output:
            return text
        
        # ANSI color codes
        colors = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'reset': '\033[0m'
        }
        
        color_code = colors.get(color, colors['white'])
        reset_code = colors['reset']
        
        if bold:
            color_code = f'\033[1m{color_code}'
        
        return f"{color_code}{text}{reset_code}"
    
    def format_summary_only(self, result: ReviewResult) -> str:
        """Format summary-only output"""
        lines = []
        
        # Quick summary
        if result.total_issues == 0:
            lines.append(self._colorize("✅ No issues found", 'green'))
        else:
            summary = f"Found {result.total_issues} issues: "
            parts = []
            if result.total_errors > 0:
                parts.append(f"{result.total_errors} errors")
            if result.total_warnings > 0:
                parts.append(f"{result.total_warnings} warnings")
            if result.total_info > 0:
                parts.append(f"{result.total_info} info")
            if result.total_suggestions > 0:
                parts.append(f"{result.total_suggestions} suggestions")
            
            summary += ", ".join(parts)
            
            if result.total_errors > 0:
                lines.append(self._colorize(f"❌ {summary}", 'red'))
            else:
                lines.append(self._colorize(f"⚠️ {summary}", 'yellow'))
        
        # Cost info
        if result.total_cost > 0:
            lines.append(f"Cost: ${result.total_cost:.4f}")
        
        return '\n'.join(lines)
    
    def export_results(self, result: ReviewResult, output_path: str, format_type: str = 'json') -> bool:
        """
        Export results to file
        
        Args:
            result: ReviewResult to export
            output_path: Path to output file
            format_type: Export format (json, markdown, csv)
            
        Returns:
            True if export successful
        """
        try:
            content = self.format_review_result(result, format_type)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Exported results to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export results to {output_path}: {e}")
            return False
    
    def get_issue_counts_by_severity(self, result: ReviewResult) -> Dict[str, int]:
        """Get issue counts grouped by severity"""
        return {
            'error': result.total_errors,
            'warning': result.total_warnings,
            'info': result.total_info,
            'suggestion': result.total_suggestions
        }
    
    def get_issue_counts_by_rule(self, result: ReviewResult) -> Dict[str, int]:
        """Get issue counts grouped by rule"""
        rule_counts = {}
        
        for file_result in result.files.values():
            for issue in file_result.issues:
                rule_counts[issue.rule] = rule_counts.get(issue.rule, 0) + 1
        
        return rule_counts
    
    def get_files_with_issues(self, result: ReviewResult) -> List[str]:
        """Get list of files that have issues"""
        return [
            filename for filename, file_result in result.files.items()
            if file_result.total_issues > 0
        ]