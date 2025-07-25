"""
Interactive user interface for AI Code Review
"""

import sys
import time
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live

from ..review.engine import ReviewResult, FileReviewResult
from ..review.formatter import ResultFormatter
from ..utils.exceptions import UserAbortError
from ..utils.logging import get_logger

logger = get_logger(__name__)


class InteractiveUI:
    """Interactive user interface for code review workflow"""
    
    def __init__(self, config):
        """
        Initialize interactive UI
        
        Args:
            config: Configuration manager
        """
        self.config = config
        self.ui_config = config.get('ui', {})
        
        # UI settings
        self.interactive_mode = self.ui_config.get('interactive_mode', True)
        self.color_output = self.ui_config.get('color_output', True)
        self.show_progress = self.ui_config.get('show_progress', True)
        
        # Initialize Rich console
        self.console = Console(
            color_system="auto" if self.color_output else None,
            force_terminal=True if sys.stdout.isatty() else False
        )
        
        # Result formatter
        self.formatter = ResultFormatter(config)
    
    def show_startup_banner(self) -> None:
        """Display startup banner"""
        if not self.interactive_mode:
            return
        
        banner_text = Text()
        banner_text.append("🔍 AI Code Review", style="bold blue")
        banner_text.append(" - Powered by AWS Bedrock", style="dim")
        
        panel = Panel(
            banner_text,
            title="Starting Review",
            border_style="blue",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        self.console.print()
    
    def show_progress_spinner(self, message: str) -> Optional[Any]:
        """
        Show progress spinner for long operations
        
        Args:
            message: Progress message
            
        Returns:
            Progress context manager or None
        """
        if not self.show_progress:
            self.console.print(f"⏳ {message}...")
            return None
        
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True
        )
    
    def show_file_progress(self, total_files: int) -> Optional[Any]:
        """
        Show file processing progress
        
        Args:
            total_files: Total number of files to process
            
        Returns:
            Progress context manager or None
        """
        if not self.show_progress or total_files <= 1:
            return None
        
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
            transient=False
        )
    
    def display_review_results(self, result: ReviewResult) -> None:
        """
        Display review results
        
        Args:
            result: ReviewResult to display
        """
        if not self.interactive_mode:
            # Non-interactive mode: just print formatted results
            formatted_output = self.formatter.format_review_result(result, 'terminal')
            self.console.print(formatted_output)
            return
        
        # Interactive mode: rich display
        self._display_results_interactive(result)
    
    def _display_results_interactive(self, result: ReviewResult) -> None:
        """Display results in interactive mode"""
        # Summary panel
        self._display_summary_panel(result)
        
        if result.total_issues == 0:
            self._display_success_message()
            return
        
        # Ask user what they want to see
        while True:
            choice = self._get_results_choice(result)
            
            if choice == 'summary':
                self._display_summary_panel(result)
            elif choice == 'details':
                self._display_detailed_results(result)
            elif choice == 'files':
                self._display_files_with_issues(result)
            elif choice == 'export':
                self._handle_export_results(result)
            elif choice == 'continue':
                break
            else:
                self.console.print("[red]Invalid choice. Please try again.[/red]")
    
    def _display_summary_panel(self, result: ReviewResult) -> None:
        """Display summary panel"""
        # Create summary table
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="bold")
        table.add_column("Count", justify="right")
        
        table.add_row("Files reviewed", str(result.total_files))
        table.add_row("Total issues", str(result.total_issues))
        
        if result.total_issues > 0:
            table.add_row("├─ Errors", f"[red]{result.total_errors}[/red]")
            table.add_row("├─ Warnings", f"[yellow]{result.total_warnings}[/yellow]")
            table.add_row("├─ Info", f"[blue]{result.total_info}[/blue]")
            table.add_row("└─ Suggestions", f"[green]{result.total_suggestions}[/green]")
        
        if result.total_cost > 0:
            table.add_row("Estimated cost", f"${result.total_cost:.4f}")
        
        # Determine panel style based on results
        if result.total_errors > 0:
            title = "❌ Review Results - Issues Found"
            border_style = "red"
        elif result.total_warnings > 0:
            title = "⚠️ Review Results - Warnings Found"
            border_style = "yellow"
        else:
            title = "✅ Review Results - All Good"
            border_style = "green"
        
        panel = Panel(
            table,
            title=title,
            border_style=border_style,
            padding=(1, 2)
        )
        
        self.console.print(panel)
        self.console.print()
    
    def _display_success_message(self) -> None:
        """Display success message when no issues found"""
        success_text = Text()
        success_text.append("🎉 Excellent! ", style="bold green")
        success_text.append("No issues found in your code changes.")
        
        panel = Panel(
            success_text,
            title="All Checks Passed",
            border_style="green",
            padding=(1, 2)
        )
        
        self.console.print(panel)
        self.console.print()
    
    def _get_results_choice(self, result: ReviewResult) -> str:
        """Get user choice for what to do with results"""
        choices = [
            "summary - Show summary again",
            "details - Show detailed issues",
            "files - List files with issues",
            "export - Export results to file",
            "continue - Continue with decision"
        ]
        
        self.console.print("[bold]What would you like to do?[/bold]")
        for i, choice in enumerate(choices, 1):
            self.console.print(f"  {i}. {choice}")
        
        self.console.print()
        
        while True:
            try:
                choice_input = Prompt.ask(
                    "Enter your choice",
                    choices=["1", "2", "3", "4", "5", "summary", "details", "files", "export", "continue"],
                    default="continue"
                )
                
                # Map numeric choices
                choice_map = {
                    "1": "summary",
                    "2": "details", 
                    "3": "files",
                    "4": "export",
                    "5": "continue"
                }
                
                return choice_map.get(choice_input, choice_input)
                
            except KeyboardInterrupt:
                raise UserAbortError("User interrupted")
    
    def _display_detailed_results(self, result: ReviewResult) -> None:
        """Display detailed issue results"""
        self.console.print("[bold]📋 Detailed Issues[/bold]")
        self.console.print()
        
        issue_count = 0
        max_display = self.ui_config.get('max_display_issues', 20)
        
        for filename, file_result in result.files.items():
            if file_result.total_issues == 0:
                continue
            
            # File header
            file_header = Text()
            file_header.append(f"📄 {filename}", style="bold")
            
            if file_result.total_issues > 0:
                counts = []
                if file_result.error_count > 0:
                    counts.append(f"[red]{file_result.error_count}E[/red]")
                if file_result.warning_count > 0:
                    counts.append(f"[yellow]{file_result.warning_count}W[/yellow]")
                if file_result.info_count > 0:
                    counts.append(f"[blue]{file_result.info_count}I[/blue]")
                if file_result.suggestion_count > 0:
                    counts.append(f"[green]{file_result.suggestion_count}S[/green]")
                
                file_header.append(f" ({' '.join(counts)})")
            
            self.console.print(file_header)
            
            # File summary
            if file_result.summary:
                self.console.print(f"   [dim]{file_result.summary}[/dim]")
            
            # Issues
            for issue in file_result.issues:
                if issue_count >= max_display:
                    remaining = sum(fr.total_issues for fr in result.files.values()) - issue_count
                    self.console.print(f"   [dim]... and {remaining} more issues[/dim]")
                    return
                
                self._display_single_issue(issue)
                issue_count += 1
            
            self.console.print()
    
    def _display_single_issue(self, issue) -> None:
        """Display a single issue"""
        # Severity styling
        severity_styles = {
            'error': 'red',
            'warning': 'yellow',
            'info': 'blue',
            'suggestion': 'green'
        }
        
        severity_icons = {
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️',
            'suggestion': '💡'
        }
        
        style = severity_styles.get(issue.severity, 'white')
        icon = severity_icons.get(issue.severity, '•')
        
        # Issue line
        issue_text = Text()
        issue_text.append(f"   {icon} ", style=style)
        
        if issue.line:
            issue_text.append(f"Line {issue.line}: ", style="dim")
        
        issue_text.append(f"[{issue.rule.upper()}] ", style="bold")
        issue_text.append(issue.message)
        
        self.console.print(issue_text)
        
        # Suggestion
        if issue.suggestion:
            suggestion_text = Text()
            suggestion_text.append("      💡 ", style="cyan")
            suggestion_text.append("Suggestion: ", style="cyan bold")
            suggestion_text.append(issue.suggestion, style="cyan")
            self.console.print(suggestion_text)
    
    def _display_files_with_issues(self, result: ReviewResult) -> None:
        """Display list of files with issues"""
        files_with_issues = [
            (filename, file_result) for filename, file_result in result.files.items()
            if file_result.total_issues > 0
        ]
        
        if not files_with_issues:
            self.console.print("[green]No files have issues![/green]")
            return
        
        self.console.print(f"[bold]📁 Files with Issues ({len(files_with_issues)})[/bold]")
        self.console.print()
        
        # Create table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("File", style="cyan")
        table.add_column("Errors", justify="center", style="red")
        table.add_column("Warnings", justify="center", style="yellow")
        table.add_column("Info", justify="center", style="blue")
        table.add_column("Suggestions", justify="center", style="green")
        table.add_column("Total", justify="center", style="bold")
        
        for filename, file_result in files_with_issues:
            table.add_row(
                filename,
                str(file_result.error_count) if file_result.error_count > 0 else "-",
                str(file_result.warning_count) if file_result.warning_count > 0 else "-",
                str(file_result.info_count) if file_result.info_count > 0 else "-",
                str(file_result.suggestion_count) if file_result.suggestion_count > 0 else "-",
                str(file_result.total_issues)
            )
        
        self.console.print(table)
        self.console.print()
    
    def _handle_export_results(self, result: ReviewResult) -> None:
        """Handle exporting results to file"""
        format_choice = Prompt.ask(
            "Export format",
            choices=["json", "markdown", "csv"],
            default="json"
        )
        
        default_filename = f"code-review-results.{format_choice}"
        filename = Prompt.ask("Output filename", default=default_filename)
        
        try:
            success = self.formatter.export_results(result, filename, format_choice)
            if success:
                self.console.print(f"[green]✅ Results exported to {filename}[/green]")
            else:
                self.console.print(f"[red]❌ Failed to export results[/red]")
        except Exception as e:
            self.console.print(f"[red]❌ Export failed: {e}[/red]")
    
    def get_user_decision(self, result: ReviewResult) -> bool:
        """
        Get user decision on whether to continue with push
        
        Args:
            result: ReviewResult to base decision on
            
        Returns:
            True to continue with push, False to abort
        """
        if not self.interactive_mode:
            # Non-interactive mode: auto-decide based on errors
            return result.total_errors == 0
        
        # Interactive mode: ask user
        return self._get_interactive_decision(result)
    
    def _get_interactive_decision(self, result: ReviewResult) -> bool:
        """Get interactive decision from user"""
        self.console.print()
        
        if result.total_errors > 0:
            # Errors found - recommend blocking
            decision_text = Text()
            decision_text.append("❌ ", style="red bold")
            decision_text.append("Errors found in your code. ", style="red")
            decision_text.append("It's recommended to fix these issues before pushing.")
            
            self.console.print(Panel(
                decision_text,
                title="Push Decision Required",
                border_style="red"
            ))
            
            return Confirm.ask(
                "[red]Do you want to continue with the push anyway?[/red]",
                default=False
            )
        
        elif result.total_warnings > 0:
            # Warnings found - allow but confirm
            decision_text = Text()
            decision_text.append("⚠️ ", style="yellow bold")
            decision_text.append("Warnings found in your code. ", style="yellow")
            decision_text.append("Consider addressing these issues.")
            
            self.console.print(Panel(
                decision_text,
                title="Push Decision",
                border_style="yellow"
            ))
            
            return Confirm.ask(
                "[yellow]Continue with the push?[/yellow]",
                default=True
            )
        
        else:
            # No issues - auto-continue
            success_text = Text()
            success_text.append("✅ ", style="green bold")
            success_text.append("No issues found. Ready to push!")
            
            self.console.print(Panel(
                success_text,
                title="All Clear",
                border_style="green"
            ))
            
            return True
    
    def show_final_message(self, continue_push: bool, result: ReviewResult) -> None:
        """
        Show final message based on user decision
        
        Args:
            continue_push: Whether user chose to continue
            result: ReviewResult for context
        """
        if continue_push:
            if result.total_issues == 0:
                message = "🚀 Pushing changes - all checks passed!"
                style = "green"
            else:
                message = "🚀 Pushing changes - please address the issues when possible"
                style = "yellow"
        else:
            message = "🛑 Push cancelled - please fix the issues and try again"
            style = "red"
        
        self.console.print()
        self.console.print(f"[{style} bold]{message}[/{style} bold]")
        
        if result.total_cost > 0:
            self.console.print(f"[dim]Review cost: ${result.total_cost:.4f}[/dim]")
    
    def show_error_message(self, error: Exception) -> None:
        """
        Show error message
        
        Args:
            error: Exception that occurred
        """
        error_text = Text()
        error_text.append("❌ Error: ", style="red bold")
        error_text.append(str(error))
        
        panel = Panel(
            error_text,
            title="Error",
            border_style="red",
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def show_help(self) -> None:
        """Show help information"""
        help_text = """
[bold]AI Code Review Help[/bold]

This tool performs AI-powered code review on your git changes before pushing.

[bold]Usage:[/bold]
  AI_REVIEW=1 git push origin main    # Enable review for this push
  git ai-push origin main             # Using git alias

[bold]During Review:[/bold]
  • summary - Show review summary
  • details - Show detailed issues  
  • files - List files with issues
  • export - Export results to file
  • continue - Make push decision

[bold]Configuration:[/bold]
  Edit .ai-code-review.yaml in your project root or
  ~/.ai-code-review/config.yaml for global settings

[bold]Exit Codes:[/bold]
  0 - Success (push allowed)
  1 - Git operation error
  2 - AWS Bedrock error
  3 - Configuration error
  5 - User aborted push
        """
        
        panel = Panel(
            help_text.strip(),
            title="Help",
            border_style="blue",
            padding=(1, 2)
        )
        
        self.console.print(panel)