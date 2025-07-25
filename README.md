# AI Code Review Git Hook

An AI-powered git pre-push hook that performs intelligent code review using AWS Bedrock APIs. Get instant feedback on your code changes before pushing to ensure quality, security, and maintainability.

## 🚀 Features

- **AI-Powered Reviews**: Uses AWS Bedrock (Claude, Llama, etc.) for intelligent code analysis
- **Parameter-Based Trigger**: Only runs when explicitly requested - no IDE interference
- **Configurable Rules**: YAML-based rule templates for different languages and frameworks
- **Interactive Interface**: Rich terminal UI with detailed feedback and user choices
- **Two Comparison Modes**:
  - Compare with remote target branch (where you're pushing)
  - Compare with specified branch (default: main)
- **Multi-Language Support**: Built-in templates for Python, JavaScript, TypeScript, and more
- **Cost Optimization**: Intelligent batching and filtering to minimize API costs
- **Security Focus**: Identifies vulnerabilities, hardcoded secrets, and security anti-patterns

## 📋 Requirements

- Python 3.8+
- Git repository
- AWS account with Bedrock access
- AWS credentials configured (CLI, environment variables, or IAM roles)

## 🛠️ Installation

### 1. Install from Source

Since this package hasn't been published to PyPI yet, install from source:

```bash
# Clone the repository
git clone https://github.com/your-username/ai-code-review-git-hook.git
cd ai-code-review-git-hook

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt
```

### 2. Install Git Hook

```bash
# Navigate to your git repository
cd /path/to/your/repo

# Install the pre-push hook
python -m ai_code_review.cli install

# Test the installation
python -m ai_code_review.cli test
```

### 3. Configure AWS Credentials

Ensure AWS credentials are configured with Bedrock access:

```bash
# Using AWS CLI
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

### 4. Set Up Convenient Alias (Optional)

```bash
git config alias.ai-push '!f() { AI_REVIEW=1 git push "$@"; }; f'
```

## 🎯 Usage

### Basic Usage

```bash
# Normal push (no review) - works in IDEs
git push origin main

# Push with AI review (terminal only)
AI_REVIEW=1 git push origin main

# Using git alias (if configured)
git ai-push origin main

# Using git config
git -c ai.review=true push origin main
```

### Manual Review

```bash
# Review current changes without pushing
python -m ai_code_review.cli review

# Review with specific comparison branch
python -m ai_code_review.cli review --branch develop

# Review with different use case
python -m ai_code_review.cli review --use-case branch --branch main
```

### Configuration

```bash
# Test configuration and connectivity
python -m ai_code_review.cli test

# Uninstall hook
python -m ai_code_review.cli uninstall
```

### Development Setup

If you're developing or contributing to the project:

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests (when available)
pytest

# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

## ⚙️ Configuration

### Project Configuration

Create `.ai-code-review.yaml` in your project root:

```yaml
# AWS Bedrock Configuration
bedrock:
  region: "us-east-1"
  model: "anthropic.claude-3-5-sonnet-20241022-v2:0"
  max_tokens: 4000
  temperature: 0.1

# Git Configuration
git:
  default_compare_branch: "main"
  exclude_patterns:
    - "*.min.js"
    - "package-lock.json"
    - "dist/*"

# Review Configuration
review:
  enabled_rules:
    - security
    - performance
    - maintainability
    - style
  severity_threshold: "warning"
  rule_templates:
    "*.py": ["python", "general"]
    "*.js": ["javascript", "general"]
    "*.ts": ["typescript", "general"]

# UI Configuration
ui:
  interactive_mode: true
  color_output: true
  show_progress: true
```

### Global Configuration

Create `~/.ai-code-review/config.yaml` for global settings:

```yaml
bedrock:
  region: "us-east-1"
  model: "anthropic.claude-3-haiku-20240307-v1:0"  # Cheaper model

logging:
  level: "INFO"
  file: "~/.ai-code-review/logs/review.log"
```

### Environment Variables

Override any configuration with environment variables:

```bash
export AI_CODE_REVIEW_BEDROCK_MODEL="anthropic.claude-3-haiku-20240307-v1:0"
export AI_CODE_REVIEW_REVIEW_SEVERITY_THRESHOLD="error"
export AI_CODE_REVIEW_UI_INTERACTIVE_MODE="false"
```

## 🎨 Supported Models

### Anthropic Claude
- `anthropic.claude-3-5-sonnet-20241022-v2:0` (Best for code review)
- `anthropic.claude-3-sonnet-20240229-v1:0` (Balanced)
- `anthropic.claude-3-haiku-20240307-v1:0` (Fast and cost-effective)

### Meta Llama
- `meta.llama3-70b-instruct-v1:0` (Large model)
- `meta.llama3-8b-instruct-v1:0` (Smaller, faster)

### Cohere
- `cohere.command-r-plus-v1:0` (Advanced reasoning)
- `cohere.command-r-v1:0` (Balanced)

### AI21
- `ai21.jamba-instruct-v1:0` (Long context)

## 📝 Rule Templates

### Built-in Templates

- **general**: Universal rules for all languages
- **python**: Python-specific rules (PEP 8, security, performance)
- **javascript**: JavaScript best practices
- **typescript**: TypeScript-specific rules
- **react**: React component patterns

### Custom Templates

Create custom rule templates in `~/.ai-code-review/templates/`:

```yaml
# ~/.ai-code-review/templates/my-custom.yaml
name: "My Custom Rules"
description: "Custom rules for my project"
file_patterns:
  - "*.py"

rules:
  custom_security:
    enabled: true
    severity: "error"
    prompt: |
      Check for my specific security requirements:
      - No hardcoded database URLs
      - All API calls must use authentication
      - Sensitive data must be encrypted
```

## 🎭 Interactive Mode

When running in interactive mode, you can:

1. **View Summary**: Quick overview of issues found
2. **Show Details**: Detailed issue breakdown by file
3. **List Files**: Files with issues and counts
4. **Export Results**: Save results to JSON/Markdown
5. **Make Decision**: Continue or abort the push

### Example Session

```
🔍 AI Code Review Results

📊 Reviewed 3 files • Found 5 issues
   └─ 1 errors • 3 warnings • 1 suggestions
💰 Estimated cost: $0.0234 (1,247 tokens)

What would you like to do?
  1. summary - Show summary again
  2. details - Show detailed issues
  3. files - List files with issues
  4. export - Export results to file
  5. continue - Continue with decision

❌ Errors found in your code. It's recommended to fix these issues before pushing.
Do you want to continue with the push anyway? [y/N]: n

🛑 Push cancelled - please fix the issues and try again
```

## 🔧 Advanced Usage

### Custom Comparison Branch

```bash
# Compare with develop branch instead of main
AI_REVIEW_BRANCH=develop git ai-push origin feature-branch
```

### Non-Interactive Mode

```bash
# Disable interactive prompts (useful for CI/CD)
AI_CODE_REVIEW_UI_INTERACTIVE_MODE=false AI_REVIEW=1 git push origin main
```

### Export Results

```bash
# Export results to file
python -m ai_code_review.cli review --export results.json --format json
```

## 🚨 Troubleshooting

### Common Issues

1. **"AWS credentials not found"**
   ```bash
   aws configure
   # or
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   ```

2. **"Model not available in region"**
   ```yaml
   bedrock:
     region: "us-east-1"  # Try us-east-1 or us-west-2
   ```

3. **"Hook not triggering"**
   ```bash
   # Check if hook is installed
   ls -la .git/hooks/pre-push
   
   # Reinstall if needed
   python -m ai_code_review.cli install
   ```

4. **"Too expensive"**
   ```yaml
   bedrock:
     model: "anthropic.claude-3-haiku-20240307-v1:0"  # Cheaper model
   
   git:
     max_files: 10  # Limit files reviewed
   ```

### Debug Mode

```bash
python -m ai_code_review.cli review --verbose
```

### Test Configuration

```bash
python -m ai_code_review.cli test
```

## 💰 Cost Optimization

- Use Claude Haiku for cost-effective reviews
- Set `max_files` and `max_diff_size` limits
- Use `exclude_patterns` to skip generated files
- Set appropriate `severity_threshold`

Typical costs:
- Small change (1-3 files): $0.01-0.05
- Medium change (5-10 files): $0.05-0.15
- Large change (20+ files): $0.15-0.50

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🆘 Support

- GitHub Issues: [Report bugs or request features](https://github.com/example/ai-code-review-git-hook/issues)
- Documentation: [Full documentation](https://github.com/example/ai-code-review-git-hook/docs)
- Discussions: [Community discussions](https://github.com/example/ai-code-review-git-hook/discussions)

## 🙏 Acknowledgments

- AWS Bedrock for AI model access
- Rich library for beautiful terminal output
- Click for CLI framework
- All contributors and users

---

**Made with ❤️ for better code quality**