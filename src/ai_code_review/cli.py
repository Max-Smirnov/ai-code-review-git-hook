"""
Command-line interface for AI Code Review
"""

import sys
import os
import click
from pathlib import Path
from typing import Optional

from .config.manager import ConfigManager
from .git.operations import GitOperations
from .git.analyzer import ChangeAnalyzer
from .review.engine import ReviewEngine
from .ui.interactive import InteractiveUI
from .utils.exceptions import AICodeReviewError, UserAbortError
from .utils.logging import setup_logging, get_logger

# Initialize logger (will be configured later)
logger = get_logger(__name__)


@click.group()
@click.version_option()
@click.option('--config', '-c', help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--quiet', '-q', is_flag=True, help='Suppress output except errors')
@click.pass_context
def main(ctx, config, verbose, quiet):
    """AI-powered git pre-push hook for code review using AWS Bedrock"""
    
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Store global options
    ctx.obj['config_path'] = config
    ctx.obj['verbose'] = verbose
    ctx.obj['quiet'] = quiet
    
    # Configure logging level based on options
    if verbose:
        log_level = 'DEBUG'
    elif quiet:
        log_level = 'ERROR'
    else:
        log_level = 'INFO'
    
    # Setup basic logging (will be reconfigured after loading config)
    setup_logging({'level': log_level})


@main.command()
@click.option('--remote', default='origin', help='Remote name')
@click.option('--branch', help='Compare branch (overrides config)')
@click.option('--use-case', type=click.Choice(['target', 'branch']), default='target',
              help='Comparison use case: target (compare with push target) or branch (compare with specified branch)')
@click.pass_context
def review(ctx, remote, branch, use_case):
    """Run code review on current changes"""
    
    try:
        # Load configuration
        config = _load_config(ctx.obj.get('config_path'))
        
        # Setup logging with config
        setup_logging(config.get('logging', {}))
        logger.info("Starting AI code review")
        
        # Initialize components
        git_ops = GitOperations()
        analyzer = ChangeAnalyzer(config.to_dict())
        review_engine = ReviewEngine(config)
        ui = InteractiveUI(config)
        
        # Show startup banner
        ui.show_startup_banner()
        
        # Get current branch and simulate push refs
        current_branch = git_ops.get_current_branch()
        
        # Create mock git ref for current changes
        from .git.operations import GitRef
        git_ref = GitRef(
            local_ref=f"refs/heads/{current_branch}",
            local_sha="HEAD",
            remote_ref=f"refs/heads/{current_branch}",
            remote_sha="HEAD~1"
        )
        
        # Get changes based on use case
        with ui.show_progress_spinner("Analyzing git changes"):
            if use_case == 'target':
                changes = git_ops.get_diff_with_remote_target(git_ref, remote)
            else:
                compare_branch = branch or config.get('git.default_compare_branch', 'main')
                changes = git_ops.get_diff_with_specified_branch("HEAD", compare_branch, remote)
        
        if not changes:
            ui.console.print("[green]✅ No changes to review[/green]")
            return
        
        # Analyze and filter changes
        with ui.show_progress_spinner("Filtering changes"):
            analysis_result = analyzer.analyze_changes(changes)
        
        if not analysis_result.filtered_changes:
            ui.console.print("[yellow]⚠️ No reviewable changes found after filtering[/yellow]")
            return
        
        # Perform review
        file_progress = ui.show_file_progress(len(analysis_result.filtered_changes))
        
        if file_progress:
            with file_progress:
                task = file_progress.add_task("Reviewing files...", total=len(analysis_result.filtered_changes))
                
                # Mock progress updates (in real implementation, this would be integrated with review engine)
                review_result = review_engine.review_changes(analysis_result.filtered_changes)
                file_progress.update(task, completed=len(analysis_result.filtered_changes))
        else:
            with ui.show_progress_spinner("Performing AI code review"):
                review_result = review_engine.review_changes(analysis_result.filtered_changes)
        
        # Display results
        ui.display_review_results(review_result)
        
        # Get user decision
        continue_push = ui.get_user_decision(review_result)
        
        # Show final message
        ui.show_final_message(continue_push, review_result)
        
        # Exit with appropriate code
        if continue_push:
            sys.exit(0)
        else:
            sys.exit(5)  # User aborted
            
    except UserAbortError:
        logger.info("Review aborted by user")
        sys.exit(5)
    except AICodeReviewError as e:
        logger.error(f"Review failed: {e}")
        if ctx.obj.get('verbose'):
            import traceback
            traceback.print_exc()
        sys.exit(e.exit_code)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if ctx.obj.get('verbose'):
            import traceback
            traceback.print_exc()
        sys.exit(99)


@main.command()
@click.argument('stdin_input', required=False)
@click.pass_context
def hook(ctx, stdin_input):
    """Run as git pre-push hook (internal use)"""
    
    try:
        # Check if review is requested
        if not _should_run_review():
            logger.debug("Review not requested, skipping")
            sys.exit(0)
        
        # Get hook arguments
        if len(sys.argv) < 3:
            logger.error("Invalid hook arguments")
            sys.exit(1)
        
        remote_name = sys.argv[1] if len(sys.argv) > 1 else 'origin'
        remote_url = sys.argv[2] if len(sys.argv) > 2 else ''
        
        # Read stdin if not provided
        if stdin_input is None:
            stdin_input = sys.stdin.read()
        
        # Load configuration
        config = _load_config(ctx.obj.get('config_path'))
        setup_logging(config.get('logging', {}))
        
        logger.info(f"Running pre-push hook for remote {remote_name}")
        
        # Initialize components
        git_ops = GitOperations()
        analyzer = ChangeAnalyzer(config.to_dict())
        review_engine = ReviewEngine(config)
        ui = InteractiveUI(config)
        
        # Parse push refs
        refs = git_ops.parse_push_refs(stdin_input)
        if not refs:
            logger.info("No refs to push, skipping review")
            sys.exit(0)
        
        # Process each ref
        all_changes = {}
        
        for git_ref in refs:
            logger.debug(f"Processing ref: {git_ref.remote_ref}")
            
            # Determine comparison method based on environment
            compare_branch = os.environ.get('AI_REVIEW_BRANCH')
            if compare_branch:
                # Use specified branch comparison
                ref_changes = git_ops.get_diff_with_specified_branch(
                    git_ref.local_ref, compare_branch, remote_name
                )
            else:
                # Use target branch comparison (default)
                ref_changes = git_ops.get_diff_with_remote_target(git_ref, remote_name)
            
            all_changes.update(ref_changes)
        
        if not all_changes:
            logger.info("No changes to review")
            sys.exit(0)
        
        # Show startup banner
        ui.show_startup_banner()
        
        # Analyze changes
        with ui.show_progress_spinner("Analyzing changes"):
            analysis_result = analyzer.analyze_changes(all_changes)
        
        if not analysis_result.filtered_changes:
            ui.console.print("[yellow]⚠️ No reviewable changes found[/yellow]")
            sys.exit(0)
        
        # Perform review
        with ui.show_progress_spinner("Performing AI code review"):
            review_result = review_engine.review_changes(analysis_result.filtered_changes)
        
        # Display results and get decision
        ui.display_review_results(review_result)
        continue_push = ui.get_user_decision(review_result)
        
        # Show final message
        ui.show_final_message(continue_push, review_result)
        
        # Exit with appropriate code
        sys.exit(0 if continue_push else 5)
        
    except UserAbortError:
        logger.info("Push aborted by user")
        sys.exit(5)
    except AICodeReviewError as e:
        logger.error(f"Hook failed: {e}")
        sys.exit(e.exit_code)
    except Exception as e:
        logger.error(f"Unexpected hook error: {e}")
        sys.exit(99)


@main.command()
@click.option('--global', 'global_install', is_flag=True, help='Install globally for all repositories')
@click.pass_context
def install(ctx, global_install):
    """Install git pre-push hook"""
    
    try:
        config = _load_config(ctx.obj.get('config_path'))
        
        if global_install:
            _install_global_hook(config)
        else:
            _install_local_hook(config)
            
        click.echo("✅ Git hook installed successfully!")
        click.echo("\nUsage:")
        click.echo("  AI_REVIEW=1 git push origin main    # Enable review")
        click.echo("  git config alias.ai-push '!f() { AI_REVIEW=1 git push \"$@\"; }; f'")
        click.echo("  git ai-push origin main             # Using alias")
        
    except Exception as e:
        click.echo(f"❌ Installation failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.pass_context
def uninstall(ctx):
    """Uninstall git pre-push hook"""
    
    try:
        _uninstall_hook()
        click.echo("✅ Git hook uninstalled successfully!")
        
    except Exception as e:
        click.echo(f"❌ Uninstallation failed: {e}", err=True)
        sys.exit(1)


@main.command()
@click.pass_context
def test(ctx):
    """Test installation and configuration"""
    
    try:
        config = _load_config(ctx.obj.get('config_path'))
        
        click.echo("🧪 Testing AI Code Review installation...")
        
        # Test configuration
        is_valid, errors = config.validate()
        if not is_valid:
            click.echo("❌ Configuration validation failed:")
            for error in errors:
                click.echo(f"   • {error}")
            sys.exit(1)
        
        click.echo("✅ Configuration is valid")
        
        # Test AWS credentials
        try:
            from .bedrock.client import BedrockClient
            bedrock_client = BedrockClient(config.get('bedrock'))
            click.echo("✅ AWS Bedrock connection successful")
        except Exception as e:
            click.echo(f"❌ AWS Bedrock connection failed: {e}")
            sys.exit(1)
        
        # Test git repository
        try:
            git_ops = GitOperations()
            repo_info = git_ops.get_repository_info()
            click.echo(f"✅ Git repository detected: {repo_info.get('remote_url', 'local')}")
        except Exception as e:
            click.echo(f"❌ Git repository test failed: {e}")
            sys.exit(1)
        
        click.echo("\n🎉 All tests passed! AI Code Review is ready to use.")
        
    except Exception as e:
        click.echo(f"❌ Test failed: {e}", err=True)
        sys.exit(1)


def _should_run_review() -> bool:
    """Check if AI review should be triggered"""
    
    # Check environment variable
    if os.environ.get('AI_REVIEW') == '1':
        return True
    
    # Check git config
    try:
        import subprocess
        result = subprocess.run(
            ['git', 'config', '--get', 'ai.review'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip() == 'true':
            return True
    except:
        pass
    
    return False


def _load_config(config_path: Optional[str] = None) -> ConfigManager:
    """Load configuration"""
    try:
        if config_path:
            # TODO: Support custom config path
            pass
        
        return ConfigManager()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise AICodeReviewError(f"Configuration error: {e}", exit_code=3)


def _install_local_hook(config: ConfigManager) -> None:
    """Install hook in current repository"""
    git_dir = Path('.git')
    if not git_dir.exists():
        raise AICodeReviewError("Not in a git repository")
    
    hooks_dir = git_dir / 'hooks'
    hooks_dir.mkdir(exist_ok=True)
    
    hook_path = hooks_dir / 'pre-push'
    
    # Create hook script
    hook_content = f"""#!/usr/bin/env python3
\"\"\"
AI Code Review Pre-Push Hook
\"\"\"

import sys
import subprocess

# Check if review is requested
def should_run_review():
    import os
    
    # Check environment variable
    if os.environ.get('AI_REVIEW') == '1':
        return True
    
    # Check git config
    try:
        result = subprocess.run(
            ['git', 'config', '--get', 'ai.review'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip() == 'true':
            return True
    except:
        pass
    
    return False

def main():
    # If review not requested, exit immediately (allow push)
    if not should_run_review():
        sys.exit(0)
    
    # Run AI review
    try:
        result = subprocess.run([
            sys.executable, '-m', 'ai_code_review.cli', 'hook'
        ] + sys.argv[1:], input=sys.stdin.read(), text=True)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"AI Code Review failed: {{e}}", file=sys.stderr)
        sys.exit(99)

if __name__ == '__main__':
    main()
"""
    
    with open(hook_path, 'w') as f:
        f.write(hook_content)
    
    # Make executable
    hook_path.chmod(0o755)


def _install_global_hook(config: ConfigManager) -> None:
    """Install hook globally"""
    # TODO: Implement global hook installation
    raise NotImplementedError("Global installation not yet implemented")


def _uninstall_hook() -> None:
    """Uninstall hook from current repository"""
    hook_path = Path('.git/hooks/pre-push')
    if hook_path.exists():
        hook_path.unlink()


if __name__ == '__main__':
    main()