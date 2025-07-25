# Configuration System Specification

## Overview

The configuration system provides a flexible, hierarchical approach to managing settings for the AI-powered git pre-push hook. It supports YAML-based configuration with validation, rule templates, and environment-specific overrides.

## Configuration Hierarchy

The system loads configuration in the following order (later configs override earlier ones):

1. **Default Configuration** (`config/default.yaml`)
2. **Global User Configuration** (`~/.ai-code-review/config.yaml`)
3. **Project Configuration** (`.ai-code-review.yaml` in git root)
4. **Environment Variables** (prefixed with `AI_CODE_REVIEW_`)

## Configuration Schema

### Main Configuration Structure

```yaml
# AWS Bedrock Configuration
bedrock:
  region: "us-east-1"                    # AWS region
  profile: null                          # AWS profile (optional)
  model: "anthropic.claude-3-5-sonnet-20241022-v2:0"
  max_tokens: 4000                       # Maximum tokens per request
  temperature: 0.1                       # Model temperature (0.0-1.0)
  timeout: 30                            # Request timeout in seconds
  retry_attempts: 3                      # Number of retry attempts
  retry_delay: 1                         # Delay between retries (seconds)

# Git Configuration
git:
  default_compare_branch: "main"         # Default branch for comparison
  max_diff_size: 10000                   # Maximum diff size in lines
  max_files: 50                          # Maximum number of files to review
  exclude_patterns:                      # Files/patterns to exclude
    - "*.min.js"
    - "*.min.css"
    - "package-lock.json"
    - "yarn.lock"
    - "*.generated.*"
    - "dist/*"
    - "build/*"
    - "node_modules/*"
  include_patterns:                      # Only include these patterns (optional)
    - "*.py"
    - "*.js"
    - "*.ts"
    - "*.jsx"
    - "*.tsx"
  binary_file_extensions:                # Extensions to treat as binary
    - ".jpg"
    - ".png"
    - ".gif"
    - ".pdf"
    - ".zip"

# Review Configuration
review:
  enabled_rules:                         # Active rule categories
    - security
    - performance
    - maintainability
    - style
    - documentation
  severity_threshold: "warning"          # Minimum severity to report
  max_issues_per_file: 10               # Maximum issues per file
  context_lines: 3                      # Lines of context around changes
  batch_size: 5                         # Files to process in parallel
  rule_templates:                       # Rule template assignments
    "*.py": ["python", "general"]
    "*.js": ["javascript", "general"]
    "*.ts": ["typescript", "general"]
    "*.jsx": ["react", "javascript", "general"]
    "*.tsx": ["react", "typescript", "general"]
    "*.java": ["java", "general"]
    "*.go": ["golang", "general"]
    "*": ["general"]                    # Fallback for all files

# User Interface Configuration
ui:
  interactive_mode: true                 # Enable interactive prompts
  color_output: true                    # Enable colored output
  show_diff_context: true               # Show diff context in results
  show_progress: true                   # Show progress indicators
  max_display_issues: 20                # Maximum issues to display
  summary_only: false                   # Show only summary (no details)
  auto_approve_threshold: null          # Auto-approve if issues below threshold

# Logging Configuration
logging:
  level: "INFO"                         # DEBUG, INFO, WARNING, ERROR
  file: null                           # Log file path (null = console only)
  max_file_size: "10MB"                # Maximum log file size
  backup_count: 3                      # Number of backup log files
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Performance Configuration
performance:
  cache_enabled: true                   # Enable caching
  cache_ttl: 3600                      # Cache TTL in seconds
  parallel_processing: true            # Enable parallel processing
  max_workers: 4                       # Maximum worker threads
```

## Rule Template System

### Template Structure

Each rule template is a YAML file that defines review criteria for specific file types or contexts.

```yaml
# Template metadata
name: "Python Code Review Template"
description: "Comprehensive Python code review rules"
version: "1.0.0"
file_patterns:
  - "*.py"
  - "*.pyx"

# Rule definitions
rules:
  security:
    enabled: true
    severity: "error"
    prompt: |
      Review this Python code for security vulnerabilities including:
      - SQL injection risks
      - Command injection vulnerabilities
      - Unsafe deserialization
      - Hardcoded secrets or credentials
      - Insecure random number generation
      - Path traversal vulnerabilities
      - XSS in web applications
    examples:
      - "Avoid using eval() or exec() with user input"
      - "Use parameterized queries instead of string concatenation"
      - "Don't hardcode API keys or passwords"

  performance:
    enabled: true
    severity: "warning"
    prompt: |
      Analyze this Python code for performance issues:
      - Inefficient algorithms or data structures
      - Unnecessary loops or iterations
      - Memory leaks or excessive memory usage
      - Blocking I/O operations
      - Inefficient database queries
      - Missing caching opportunities
    examples:
      - "Use list comprehensions instead of loops where appropriate"
      - "Consider using generators for large datasets"
      - "Cache expensive computations"

  maintainability:
    enabled: true
    severity: "warning"
    prompt: |
      Review code maintainability and readability:
      - Function and class complexity
      - Code duplication
      - Naming conventions
      - Documentation and comments
      - Error handling
      - Code organization
    examples:
      - "Functions should have a single responsibility"
      - "Use descriptive variable and function names"
      - "Add docstrings to public functions and classes"

  style:
    enabled: true
    severity: "info"
    prompt: |
      Check Python style and best practices:
      - PEP 8 compliance
      - Import organization
      - Line length and formatting
      - Consistent code style
      - Pythonic idioms
    examples:
      - "Follow PEP 8 naming conventions"
      - "Organize imports: standard library, third-party, local"
      - "Use f-strings for string formatting"

  documentation:
    enabled: true
    severity: "info"
    prompt: |
      Evaluate documentation quality:
      - Missing or inadequate docstrings
      - Unclear or outdated comments
      - Missing type hints
      - API documentation
    examples:
      - "Add type hints to function signatures"
      - "Document complex algorithms or business logic"
      - "Keep comments up-to-date with code changes"

# Custom prompts for specific contexts
context_prompts:
  new_file: |
    This is a new file. Pay special attention to:
    - Overall architecture and design patterns
    - Proper error handling
    - Security considerations from the start
    - Documentation completeness

  large_change: |
    This is a large change (>100 lines). Focus on:
    - Breaking changes and backward compatibility
    - Performance implications
    - Testing requirements
    - Documentation updates

  critical_path: |
    This change affects critical code paths. Emphasize:
    - Thorough error handling
    - Security implications
    - Performance impact
    - Testing coverage

# Severity mapping
severity_levels:
  error: 4      # Blocks push by default
  warning: 3    # Warns but allows push
  info: 2       # Informational
  suggestion: 1 # Optional improvements

# File-specific overrides
file_overrides:
  "test_*.py":
    rules:
      style:
        severity: "suggestion"  # Relax style rules for tests
  "migrations/*.py":
    rules:
      maintainability:
        enabled: false          # Skip maintainability for migrations
```

## Environment Variable Overrides

Configuration values can be overridden using environment variables with the prefix `AI_CODE_REVIEW_`:

```bash
# Override Bedrock model
export AI_CODE_REVIEW_BEDROCK_MODEL="anthropic.claude-3-haiku-20240307-v1:0"

# Override severity threshold
export AI_CODE_REVIEW_REVIEW_SEVERITY_THRESHOLD="error"

# Disable interactive mode
export AI_CODE_REVIEW_UI_INTERACTIVE_MODE="false"

# Set custom compare branch
export AI_CODE_REVIEW_GIT_DEFAULT_COMPARE_BRANCH="develop"
```

## Configuration Validation

The system validates configuration using JSON Schema:

```python
# Example validation rules
BEDROCK_MODELS = [
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "anthropic.claude-3-haiku-20240307-v1:0",
    "meta.llama3-70b-instruct-v1:0",
    # ... other supported models
]

SEVERITY_LEVELS = ["error", "warning", "info", "suggestion"]

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "bedrock": {
            "type": "object",
            "properties": {
                "model": {"enum": BEDROCK_MODELS},
                "max_tokens": {"type": "integer", "minimum": 100, "maximum": 8000},
                "temperature": {"type": "number", "minimum": 0.0, "maximum": 1.0}
            }
        },
        "review": {
            "type": "object",
            "properties": {
                "severity_threshold": {"enum": SEVERITY_LEVELS}
            }
        }
    }
}
```

## Default Rule Templates

### 1. General Template (`config/templates/general.yaml`)
- Universal code quality rules
- Security best practices
- Basic performance guidelines
- Documentation standards

### 2. Python Template (`config/templates/python.yaml`)
- PEP 8 compliance
- Python-specific security issues
- Performance patterns
- Pythonic idioms

### 3. JavaScript Template (`config/templates/javascript.yaml`)
- ESLint-style rules
- Modern JavaScript practices
- Browser security considerations
- Performance optimizations

### 4. TypeScript Template (`config/templates/typescript.yaml`)
- Type safety rules
- TypeScript best practices
- Interface and type definitions
- Generic usage patterns

### 5. React Template (`config/templates/react.yaml`)
- Component design patterns
- Hook usage guidelines
- Performance optimizations
- Accessibility considerations

## Configuration Management API

The configuration system provides a clean API for accessing settings:

```python
from src.config.manager import ConfigManager

# Initialize configuration
config = ConfigManager()

# Access nested configuration
bedrock_model = config.get('bedrock.model')
severity_threshold = config.get('review.severity_threshold')

# Get rule templates for file
templates = config.get_rule_templates('src/main.py')

# Validate configuration
is_valid, errors = config.validate()

# Reload configuration
config.reload()
```

This configuration system provides the flexibility and power needed to customize the code review process while maintaining simplicity for basic use cases.