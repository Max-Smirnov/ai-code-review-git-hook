# Commit Hash Comparison Feature Implementation Plan

This document outlines the plan for adding the ability to compare and review against a specific commit hash to the AI Code Review Git Hook.

## Feature Overview

This enhancement adds a third comparison mode to the existing two modes:
- **Target Mode**: Compare with remote target branch (where you're pushing)
- **Branch Mode**: Compare with specified branch (default: main)
- **Commit Mode** (new): Compare with specific commit hash

## Implementation Details

### 1. CLI Interface Changes

Update `src/ai_code_review/cli.py`:

```python
@main.command()
@click.option('--remote', default='origin', help='Remote name')
@click.option('--branch', help='Compare branch (overrides config)')
@click.option('--commit', help='Compare with specific commit hash')
@click.option('--use-case', type=click.Choice(['target', 'branch', 'commit']), default='target',
              help='Comparison use case: target (compare with push target), branch (compare with specified branch), or commit (compare with specific commit hash)')
@click.pass_context
def review(ctx, remote, branch, commit, use_case):
    """Run code review on current changes"""
    
    # ... existing code ...
    
    # Get changes based on use case
    with ui.show_progress_spinner("Analyzing git changes"):
        if use_case == 'target':
            changes = git_ops.get_diff_with_remote_target(git_ref, remote)
        elif use_case == 'commit':
            if not commit:
                commit = config.get('git.default_compare_commit')
                if not commit:
                    ui.console.print("[red]Error: No commit hash specified for commit comparison[/red]")
                    sys.exit(1)
            changes = git_ops.get_diff_with_commit("HEAD", commit)
        else:  # branch
            compare_branch = branch or config.get('git.default_compare_branch', 'main')
            changes = git_ops.get_diff_with_specified_branch("HEAD", compare_branch, remote)
```

Update the `hook` function to check for the `AI_REVIEW_COMMIT` environment variable:

```python
@main.command()
@click.argument('stdin_input', required=False)
@click.pass_context
def hook(ctx, stdin_input):
    """Run as git pre-push hook (internal use)"""
    
    # ... existing code ...
    
    # Process each ref
    all_changes = {}
    
    for git_ref in refs:
        logger.debug(f"Processing ref: {git_ref.remote_ref}")
        
        # Determine comparison method based on environment
        compare_commit = os.environ.get('AI_REVIEW_COMMIT')
        compare_branch = os.environ.get('AI_REVIEW_BRANCH')
        
        if compare_commit:
            # Use specified commit comparison
            ref_changes = git_ops.get_diff_with_commit(
                git_ref.local_ref, compare_commit
            )
        elif compare_branch:
            # Use specified branch comparison
            ref_changes = git_ops.get_diff_with_specified_branch(
                git_ref.local_ref, compare_branch, remote_name
            )
        else:
            # Use target branch comparison (default)
            ref_changes = git_ops.get_diff_with_remote_target(git_ref, remote_name)
        
        all_changes.update(ref_changes)
```

Update the `_should_run_review` function to check for commit hash in git config:

```python
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
        
        # Check for commit hash in git config
        result = subprocess.run(
            ['git', 'config', '--get', 'ai.review.commit'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            os.environ['AI_REVIEW_COMMIT'] = result.stdout.strip()
            return True
    except:
        pass
    
    return False
```

### 2. Git Operations Implementation

Update `src/ai_code_review/git/operations.py`:

Add a new method to the `GitOperations` class:

```python
@log_performance
def get_diff_with_commit(self, local_ref: str, commit_hash: str) -> Dict[str, FileChange]:
    """
    Get diff between local ref and specific commit hash
    
    Args:
        local_ref: Local reference (e.g., "HEAD")
        commit_hash: Specific commit hash to compare against
        
    Returns:
        Dictionary of filename -> FileChange
    """
    logger.debug(f"Getting diff between commit {commit_hash} and {local_ref}")
    
    # Validate commit hash exists
    if not self._commit_exists(commit_hash):
        raise GitError(f"Commit hash {commit_hash} not found in repository")
    
    # Get commit information
    commit_info = self.get_commit_info(commit_hash)
    
    # Use existing _get_diff_between_refs method
    changes = self._get_diff_between_refs(local_ref, commit_hash)
    
    # Add commit information to each FileChange
    for filename, change in changes.items():
        change.commit_info = commit_info
    
    return changes
```

Add helper methods for commit hash validation:

```python
def _commit_exists(self, commit_hash: str) -> bool:
    """
    Check if a commit hash exists in the repository
    
    Args:
        commit_hash: Commit hash to check
        
    Returns:
        True if commit exists, False otherwise
    """
    try:
        # Use git cat-file to check if commit exists
        # The ^{commit} syntax ensures it's a commit object
        self._run_git_command(['cat-file', '-e', f"{commit_hash}^{{commit}}"])
        return True
    except GitError:
        return False

def validate_commit_hash(self, commit_hash: str) -> str:
    """
    Validate and normalize a commit hash
    
    Args:
        commit_hash: Commit hash to validate (can be abbreviated)
        
    Returns:
        Full commit hash if valid
        
    Raises:
        GitError: If commit hash is invalid or not found
    """
    if not commit_hash or not isinstance(commit_hash, str):
        raise GitError("Invalid commit hash: must be a non-empty string")
    
    # Remove any whitespace
    commit_hash = commit_hash.strip()
    
    # Basic format validation (hexadecimal)
    if not re.match(r'^[0-9a-f]+$', commit_hash, re.IGNORECASE):
        raise GitError(f"Invalid commit hash format: {commit_hash}")
    
    # Check if commit exists
    if not self._commit_exists(commit_hash):
        raise GitError(f"Commit hash not found: {commit_hash}")
    
    # Get full commit hash
    try:
        full_hash = self._run_git_command(['rev-parse', commit_hash])
        return full_hash
    except GitError as e:
        raise GitError(f"Failed to resolve commit hash {commit_hash}: {e}")

def get_commit_info(self, commit_hash: str) -> Dict[str, str]:
    """
    Get information about a specific commit
    
    Args:
        commit_hash: Commit hash
        
    Returns:
        Dictionary with commit information
    """
    try:
        # Validate commit hash
        full_hash = self.validate_commit_hash(commit_hash)
        
        # Get commit information
        info = {
            'hash': full_hash,
            'short_hash': self._run_git_command(['rev-parse', '--short', commit_hash]),
            'subject': self._run_git_command(['log', '-1', '--pretty=format:%s', commit_hash]),
            'author': self._run_git_command(['log', '-1', '--pretty=format:%an <%ae>', commit_hash]),
            'date': self._run_git_command(['log', '-1', '--pretty=format:%ad', '--date=iso', commit_hash]),
            'relative_date': self._run_git_command(['log', '-1', '--pretty=format:%ar', commit_hash])
        }
        
        return info
    except GitError as e:
        logger.error(f"Failed to get commit info for {commit_hash}: {e}")
        return {
            'hash': commit_hash,
            'error': str(e)
        }
```

Update the `FileChange` class to include commit information:

```python
@dataclass
class FileChange:
    """Represents a change to a file"""
    filename: str
    status: str  # A=added, M=modified, D=deleted, R=renamed, C=copied
    lines_added: int
    lines_removed: int
    diff: str
    old_filename: Optional[str] = None  # For renamed files
    commit_info: Optional[Dict[str, str]] = None  # For commit comparison
```

### 3. Review Engine Updates

Update `src/ai_code_review/review/engine.py`:

Enhance the `_build_review_prompt` method to include commit information:

```python
def _build_review_prompt(self, filename: str, change: FileChange, rules: Dict[str, Any]) -> str:
    """Build review prompt for a file"""
    prompt_parts = [
        "Please review the following code changes and provide feedback according to the specified rules.",
        "",
        f"**File:** {filename}",
        f"**Change Type:** {self._get_change_type_description(change.status)}",
        f"**Lines Added:** {change.lines_added}",
        f"**Lines Removed:** {change.lines_removed}",
    ]
    
    # Add commit information if available
    if hasattr(change, 'commit_info') and change.commit_info:
        commit_info = change.commit_info
        prompt_parts.extend([
            "",
            "**Comparison Context:**",
            f"Comparing against commit: {commit_info.get('short_hash', '')}",
            f"Commit message: {commit_info.get('subject', '')}",
            f"Author: {commit_info.get('author', '')}",
            f"Date: {commit_info.get('relative_date', '')}"
        ])
    
    prompt_parts.extend([
        "",
        "**Code Changes:**",
        "```diff",
        change.diff,
        "```",
        "",
        "**Review Criteria:**"
    ])
    
    # Rest of the method remains the same
    # ...
```

Update the `ReviewResult` class in `src/ai_code_review/review/models.py`:

```python
@dataclass
class ReviewResult:
    """Overall review result"""
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
    comparison_type: str = "unknown"  # target, branch, or commit
    comparison_reference: Optional[str] = None  # branch name or commit hash
```

Update the `_aggregate_results` method in `ReviewEngine`:

```python
def _aggregate_results(self, file_results: Dict[str, FileReviewResult], 
                      comparison_type: str = "unknown", 
                      comparison_reference: Optional[str] = None) -> ReviewResult:
    """Aggregate file results into overall result"""
    # Existing code...
    
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
        summary=summary,
        comparison_type=comparison_type,
        comparison_reference=comparison_reference
    )
```

### 4. Configuration Updates

Update `src/ai_code_review/config/manager.py`:

Update the default configuration in `_load_default_config()`:

```python
def _load_default_config(self) -> Dict[str, Any]:
    """Load default configuration"""
    default_config = {
        'bedrock': {
            # ... existing bedrock config ...
        },
        'git': {
            'default_compare_branch': 'main',
            'default_compare_commit': None,  # Add this line
            'max_diff_size': 10000,
            'max_files': 50,
            'exclude_patterns': [
                # ... existing patterns ...
            ],
            'include_patterns': [],
            'binary_file_extensions': [
                # ... existing extensions ...
            ],
        },
        # ... rest of the config ...
    }
    
    return default_config
```

Update `src/ai_code_review/config/validator.py`:

Update the schema in `_build_schema()`:

```python
def _build_schema(self) -> Dict[str, Any]:
    """Build JSON schema for configuration validation"""
    return {
        "type": "object",
        "properties": {
            # ... existing properties ...
            "git": {
                "type": "object",
                "properties": {
                    "default_compare_branch": {"type": "string"},
                    "default_compare_commit": {"type": ["string", "null"]},  # Add this line
                    "max_diff_size": {"type": "integer", "minimum": 100},
                    "max_files": {"type": "integer", "minimum": 1},
                    # ... rest of git properties ...
                },
                "additionalProperties": False
            },
            # ... rest of schema ...
        },
        "additionalProperties": False
    }
```

Add a method to validate commit hashes:

```python
def _is_valid_commit_hash(self, commit_hash: str) -> bool:
    """
    Validate git commit hash format
    
    Args:
        commit_hash: Commit hash to validate
        
    Returns:
        True if valid format, False otherwise
    """
    if not commit_hash:
        return True  # Allow empty/None values
    
    # Git commit hashes are 40-character hexadecimal strings
    # But we also allow abbreviated hashes (at least 7 characters)
    return re.match(r'^[0-9a-f]{7,40}$', commit_hash, re.IGNORECASE) is not None
```

Update the `_validate_git_config` method:

```python
def _validate_git_config(self, git_config: Dict[str, Any]) -> List[str]:
    """Validate Git-specific configuration"""
    errors = []
    
    # Validate branch name format
    branch = git_config.get('default_compare_branch', '')
    if branch and not self._is_valid_branch_name(branch):
        errors.append(f"Invalid branch name: {branch}")
    
    # Validate commit hash format
    commit = git_config.get('default_compare_commit', '')
    if commit and not self._is_valid_commit_hash(commit):
        errors.append(f"Invalid commit hash format: {commit}")
    
    # Validate file patterns
    for pattern_type in ['exclude_patterns', 'include_patterns']:
        patterns = git_config.get(pattern_type, [])
        for pattern in patterns:
            if not self._is_valid_glob_pattern(pattern):
                errors.append(f"Invalid {pattern_type} pattern: {pattern}")
    
    return errors
```

### 5. Documentation Updates

Update `README.md`:

```markdown
## 🚀 Features

- **AI-Powered Reviews**: Uses AWS Bedrock (Claude, Llama, etc.) for intelligent code analysis
- **Parameter-Based Trigger**: Only runs when explicitly requested - no IDE interference
- **Configurable Rules**: YAML-based rule templates for different languages and frameworks
- **Interactive Interface**: Rich terminal UI with detailed feedback and user choices
- **Three Comparison Modes**:
  - Compare with remote target branch (where you're pushing)
  - Compare with specified branch (default: main)
  - Compare with specific commit hash (new)
- **Multi-Language Support**: Built-in templates for Python, JavaScript, TypeScript, and more
- **Cost Optimization**: Intelligent batching and filtering to minimize API costs
- **Security Focus**: Identifies vulnerabilities, hardcoded secrets, and security anti-patterns
```

Add usage examples:

```markdown
### Manual Review

```bash
# Review current changes without pushing
python -m ai_code_review.cli review

# Review with specific comparison branch
python -m ai_code_review.cli review --branch develop

# Review with different use case
python -m ai_code_review.cli review --use-case branch --branch main

# Review with specific commit hash
python -m ai_code_review.cli review --use-case commit --commit abc123f
```

### Custom Commit Hash Comparison

```bash
# Compare with specific commit hash
AI_REVIEW_COMMIT=abc123f git ai-push origin feature-branch

# Compare with specific commit hash using git config
git -c ai.review.commit=abc123f git push origin feature-branch
```
```

Update configuration documentation:

```markdown
### Project Configuration

Create `.ai-code-review.yaml` in your project root:

```yaml
# Git Configuration
git:
  default_compare_branch: "main"
  default_compare_commit: null  # Set to a commit hash to use by default
  exclude_patterns:
    - "*.min.js"
    - "package-lock.json"
    - "dist/*"
```

### Environment Variables

Override any configuration with environment variables:

```bash
export AI_CODE_REVIEW_GIT_DEFAULT_COMPARE_COMMIT="abc123f"
```
```

Update `architecture.md` and `workflow-specification.md` to include the new comparison mode.

## Testing Plan

### Unit Tests

1. Test the `get_diff_with_commit` method
2. Test commit hash validation
3. Test the CLI interface with commit hash options
4. Test configuration with commit hash

### Integration Tests

1. Test end-to-end workflow with commit hash comparison
2. Test environment variable and git config overrides

### Manual Testing

1. Test basic functionality with valid commit hashes
2. Test edge cases (invalid hashes, very old commits, binary files)
3. Test configuration options and overrides

## Usage Examples

```bash
# CLI usage
python -m ai_code_review.cli review --use-case commit --commit abc123f

# Environment variable usage
AI_REVIEW_COMMIT=abc123f git push origin main

# Git config usage
git -c ai.review.commit=abc123f -c ai.review=true push origin main
```

## Configuration Example

```yaml
git:
  default_compare_branch: "main"
  default_compare_commit: null  # Set to a commit hash to use by default