# Simplified Parameter-Based Approach

## Overview

Based on your feedback, we'll implement a simpler approach where AI code review is triggered only when users explicitly request it via an environment variable or git configuration parameter. This ensures IDEs and normal git workflows are completely unaffected.

## Revised Architecture: Conditional Pre-Push Hook

### Implementation Strategy

The pre-push hook will check for a specific trigger before running the AI review:

```bash
# Normal push (no review) - works perfectly in IDEs
git push origin main

# Push with AI review (terminal only)
AI_REVIEW=1 git push origin main

# Or using git config
git -c ai.review=true push origin main

# Convenient git alias
git config alias.ai-push '!f() { AI_REVIEW=1 git push "$@"; }; f'
git ai-push origin main
```

### Pre-Push Hook Logic

```python
#!/usr/bin/env python3
"""
Conditional AI Code Review Pre-Push Hook
Only runs when explicitly requested via environment variable or git config
"""

import os
import sys
import subprocess

def should_run_review():
    """Check if AI review should be triggered"""
    
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
    
    # Check for --ai-review flag in git push command
    # (This requires parsing the original command, more complex)
    
    return False

def main():
    # If review not requested, exit immediately (allow push)
    if not should_run_review():
        sys.exit(0)
    
    # Only run AI review when explicitly requested
    from src.main import run_ai_review
    result = run_ai_review(sys.argv[1:])
    sys.exit(0 if result else 1)

if __name__ == '__main__':
    main()
```

## User Experience

### For IDE Users (Unchanged)
- All existing IDE git workflows work exactly as before
- No prompts, no delays, no interference
- Push operations complete normally

### For Terminal Users (Opt-in)
```bash
# Regular push (same as always)
$ git push origin main
Enumerating objects: 5, done.
# ... normal git output

# AI-reviewed push (when requested)
$ AI_REVIEW=1 git push origin main
🔍 AI Code Review requested...
📊 Analyzing 3 changed files...
✅ Review completed - 2 suggestions found
Continue with push? (y/n): y
Enumerating objects: 5, done.
# ... normal git output continues
```

## Configuration Options

### Environment Variables
```bash
# Enable review
export AI_REVIEW=1

# Configure comparison branch
export AI_REVIEW_BRANCH=develop

# Set review mode
export AI_REVIEW_MODE=strict  # strict, advisory, summary
```

### Git Configuration
```bash
# Enable for current repository
git config ai.review true
git config ai.branch main
git config ai.mode advisory

# Enable globally
git config --global ai.review false  # disabled by default
```

### Configuration File (Optional)
```yaml
# .ai-code-review.yaml (only loaded when review is triggered)
trigger:
  environment_var: "AI_REVIEW"
  git_config: "ai.review"
  default_enabled: false

review:
  default_branch: "main"
  mode: "advisory"  # strict, advisory, summary
  
# ... rest of configuration same as before
```

## Git Aliases for Convenience

```bash
# Setup convenient aliases
git config alias.ai-push '!f() { AI_REVIEW=1 git push "$@"; }; f'
git config alias.review-push '!f() { AI_REVIEW=1 git push "$@"; }; f'
git config alias.safe-push '!f() { AI_REVIEW=1 AI_REVIEW_MODE=strict git push "$@"; }; f'

# Usage
git ai-push origin main
git review-push origin feature-branch
git safe-push origin main
```

## Advanced Trigger Options

### Option 1: Git Hook with Parameter Detection
```python
def detect_review_request():
    """Detect if review was requested through various means"""
    
    # Method 1: Environment variable
    if os.environ.get('AI_REVIEW') == '1':
        return True, 'environment'
    
    # Method 2: Git config
    if get_git_config('ai.review') == 'true':
        return True, 'config'
    
    # Method 3: Special branch naming convention
    current_branch = get_current_branch()
    if current_branch.startswith('review/'):
        return True, 'branch_naming'
    
    # Method 4: Commit message flag
    last_commit_msg = get_last_commit_message()
    if '[ai-review]' in last_commit_msg:
        return True, 'commit_message'
    
    return False, None
```

### Option 2: Wrapper Script Approach
```bash
#!/bin/bash
# git-ai-push wrapper script

# Set environment variable and call git push
AI_REVIEW=1 git push "$@"
```

### Option 3: Git Custom Command
```python
#!/usr/bin/env python3
# git-ai-push custom command

import sys
import os
import subprocess

def main():
    # Set environment variable
    os.environ['AI_REVIEW'] = '1'
    
    # Call git push with all arguments
    cmd = ['git', 'push'] + sys.argv[1:]
    result = subprocess.run(cmd)
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()
```

## Benefits of This Approach

### ✅ Advantages
- **Zero IDE Impact**: Normal git operations completely unaffected
- **Opt-in Only**: Users choose when to use AI review
- **Familiar Workflow**: Uses standard git mechanisms
- **Flexible Triggers**: Multiple ways to enable review
- **Backward Compatible**: Existing workflows unchanged

### 🔧 Implementation Simplicity
- Single pre-push hook with conditional logic
- No complex environment detection needed
- Standard git configuration mechanisms
- Simple installation process

### 👥 User Adoption
- Non-intrusive introduction
- Users can try it gradually
- Easy to disable/remove
- Clear mental model (explicit opt-in)

## Installation Process

```bash
# 1. Install the tool
pip install ai-code-review-git

# 2. Install hook in repository
cd /path/to/your/repo
ai-code-review install

# 3. Configure (optional)
git config ai.review false  # disabled by default
git config ai.branch main

# 4. Set up convenient alias
git config alias.ai-push '!f() { AI_REVIEW=1 git push "$@"; }; f'

# 5. Use when needed
git ai-push origin main
```

## Migration Path

### Phase 1: Manual Trigger (Current Plan)
- Environment variable trigger
- Git config trigger
- Convenient aliases

### Phase 2: Enhanced Triggers (Future)
- Branch naming conventions
- Commit message flags
- Project-specific defaults

### Phase 3: IDE Integration (Future)
- VS Code extension with manual trigger
- JetBrains plugin integration
- Optional automatic triggers

This approach provides a clean, non-intrusive way to introduce AI code review while maintaining complete compatibility with existing workflows and IDE integrations.