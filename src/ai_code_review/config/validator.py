"""
Configuration validator for AI Code Review
"""

import re
from typing import Dict, Any, List, Tuple
from jsonschema import validate, ValidationError as JsonSchemaValidationError

from ..utils.logging import get_logger

logger = get_logger(__name__)


class ConfigValidator:
    """Validates configuration against schema"""
    
    # Supported AWS Bedrock models
    BEDROCK_MODELS = [
        'anthropic.claude-3-5-sonnet-20241022-v2:0',
        'anthropic.claude-3-haiku-20240307-v1:0',
        'anthropic.claude-3-sonnet-20240229-v1:0',
        'meta.llama3-70b-instruct-v1:0',
        'meta.llama3-8b-instruct-v1:0',
        'cohere.command-r-plus-v1:0',
        'cohere.command-r-v1:0',
        'ai21.jamba-instruct-v1:0',
    ]
    
    SEVERITY_LEVELS = ['error', 'warning', 'info', 'suggestion']
    
    LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    
    def __init__(self):
        """Initialize validator with schema"""
        self.schema = self._build_schema()
    
    def validate(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate configuration
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        try:
            # Validate against JSON schema
            validate(instance=config, schema=self.schema)
            
            # Additional custom validations
            errors.extend(self._validate_bedrock_config(config.get('bedrock', {})))
            errors.extend(self._validate_git_config(config.get('git', {})))
            errors.extend(self._validate_review_config(config.get('review', {})))
            errors.extend(self._validate_ui_config(config.get('ui', {})))
            errors.extend(self._validate_logging_config(config.get('logging', {})))
            errors.extend(self._validate_performance_config(config.get('performance', {})))
            
        except JsonSchemaValidationError as e:
            errors.append(f"Schema validation error: {e.message}")
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def _build_schema(self) -> Dict[str, Any]:
        """Build JSON schema for configuration validation"""
        return {
            "type": "object",
            "properties": {
                "bedrock": {
                    "type": "object",
                    "properties": {
                        "region": {"type": "string", "pattern": r"^[a-z0-9-]+$"},
                        "profile": {"type": ["string", "null"]},
                        "model": {"type": "string", "enum": self.BEDROCK_MODELS},
                        "max_tokens": {"type": "integer", "minimum": 100, "maximum": 8000},
                        "temperature": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "timeout": {"type": "integer", "minimum": 1, "maximum": 300},
                        "retry_attempts": {"type": "integer", "minimum": 0, "maximum": 10},
                        "retry_delay": {"type": "number", "minimum": 0.1, "maximum": 60},
                    },
                    "additionalProperties": False
                },
                "git": {
                    "type": "object",
                    "properties": {
                        "default_compare_branch": {"type": "string"},
                        "max_diff_size": {"type": "integer", "minimum": 100},
                        "max_files": {"type": "integer", "minimum": 1},
                        "exclude_patterns": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "include_patterns": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "binary_file_extensions": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                    },
                    "additionalProperties": False
                },
                "review": {
                    "type": "object",
                    "properties": {
                        "enabled_rules": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "severity_threshold": {"type": "string", "enum": self.SEVERITY_LEVELS},
                        "max_issues_per_file": {"type": "integer", "minimum": 1},
                        "context_lines": {"type": "integer", "minimum": 0},
                        "batch_size": {"type": "integer", "minimum": 1},
                        "rule_templates": {
                            "type": "object",
                            "patternProperties": {
                                ".*": {
                                    "oneOf": [
                                        {"type": "string"},
                                        {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        }
                                    ]
                                }
                            }
                        },
                    },
                    "additionalProperties": False
                },
                "ui": {
                    "type": "object",
                    "properties": {
                        "interactive_mode": {"type": "boolean"},
                        "color_output": {"type": "boolean"},
                        "show_diff_context": {"type": "boolean"},
                        "show_progress": {"type": "boolean"},
                        "max_display_issues": {"type": "integer", "minimum": 1},
                        "summary_only": {"type": "boolean"},
                        "auto_approve_threshold": {"type": ["integer", "null"], "minimum": 0},
                    },
                    "additionalProperties": False
                },
                "logging": {
                    "type": "object",
                    "properties": {
                        "level": {"type": "string", "enum": self.LOG_LEVELS},
                        "file": {"type": ["string", "null"]},
                        "max_file_size": {"type": "string"},
                        "backup_count": {"type": "integer", "minimum": 0},
                        "format": {"type": "string"},
                    },
                    "additionalProperties": False
                },
                "performance": {
                    "type": "object",
                    "properties": {
                        "cache_enabled": {"type": "boolean"},
                        "cache_ttl": {"type": "integer", "minimum": 0},
                        "parallel_processing": {"type": "boolean"},
                        "max_workers": {"type": "integer", "minimum": 1, "maximum": 32},
                    },
                    "additionalProperties": False
                },
            },
            "additionalProperties": False
        }
    
    def _validate_bedrock_config(self, bedrock_config: Dict[str, Any]) -> List[str]:
        """Validate Bedrock-specific configuration"""
        errors = []
        
        # Validate AWS region format
        region = bedrock_config.get('region', '')
        if region and not re.match(r'^[a-z0-9-]+$', region):
            errors.append(f"Invalid AWS region format: {region}")
        
        # Validate model availability in region
        model = bedrock_config.get('model', '')
        region = bedrock_config.get('region', 'us-east-1')
        if model and not self._is_model_available_in_region(model, region):
            errors.append(f"Model {model} may not be available in region {region}")
        
        return errors
    
    def _validate_git_config(self, git_config: Dict[str, Any]) -> List[str]:
        """Validate Git-specific configuration"""
        errors = []
        
        # Validate branch name format
        branch = git_config.get('default_compare_branch', '')
        if branch and not self._is_valid_branch_name(branch):
            errors.append(f"Invalid branch name: {branch}")
        
        # Validate file patterns
        for pattern_type in ['exclude_patterns', 'include_patterns']:
            patterns = git_config.get(pattern_type, [])
            for pattern in patterns:
                if not self._is_valid_glob_pattern(pattern):
                    errors.append(f"Invalid {pattern_type} pattern: {pattern}")
        
        return errors
    
    def _validate_review_config(self, review_config: Dict[str, Any]) -> List[str]:
        """Validate Review-specific configuration"""
        errors = []
        
        # Validate rule templates patterns
        rule_templates = review_config.get('rule_templates', {})
        for pattern, templates in rule_templates.items():
            if not self._is_valid_glob_pattern(pattern):
                errors.append(f"Invalid rule template pattern: {pattern}")
            
            # Validate template names
            template_list = templates if isinstance(templates, list) else [templates]
            for template in template_list:
                if not self._is_valid_template_name(template):
                    errors.append(f"Invalid template name: {template}")
        
        return errors
    
    def _validate_ui_config(self, ui_config: Dict[str, Any]) -> List[str]:
        """Validate UI-specific configuration"""
        errors = []
        
        # Validate auto_approve_threshold logic
        threshold = ui_config.get('auto_approve_threshold')
        max_issues = ui_config.get('max_display_issues', 20)
        
        if threshold is not None and threshold > max_issues:
            errors.append(
                f"auto_approve_threshold ({threshold}) cannot be greater than "
                f"max_display_issues ({max_issues})"
            )
        
        return errors
    
    def _validate_logging_config(self, logging_config: Dict[str, Any]) -> List[str]:
        """Validate Logging-specific configuration"""
        errors = []
        
        # Validate file size format
        max_file_size = logging_config.get('max_file_size', '10MB')
        if not self._is_valid_file_size(max_file_size):
            errors.append(f"Invalid file size format: {max_file_size}")
        
        return errors
    
    def _validate_performance_config(self, perf_config: Dict[str, Any]) -> List[str]:
        """Validate Performance-specific configuration"""
        errors = []
        
        # Validate worker count vs system capabilities
        max_workers = perf_config.get('max_workers', 4)
        import os
        cpu_count = os.cpu_count() or 1
        
        if max_workers > cpu_count * 2:
            errors.append(
                f"max_workers ({max_workers}) is much higher than CPU count ({cpu_count}). "
                f"Consider reducing for better performance."
            )
        
        return errors
    
    def _is_model_available_in_region(self, model: str, region: str) -> bool:
        """Check if model is available in the specified region"""
        # This is a simplified check - in practice, you'd query AWS Bedrock API
        # or maintain a mapping of model availability by region
        
        # Claude models are generally available in us-east-1, us-west-2, eu-west-1
        claude_regions = ['us-east-1', 'us-west-2', 'eu-west-1']
        if model.startswith('anthropic.claude') and region not in claude_regions:
            return False
        
        # Llama models have different availability
        llama_regions = ['us-east-1', 'us-west-2']
        if model.startswith('meta.llama') and region not in llama_regions:
            return False
        
        return True
    
    def _is_valid_branch_name(self, branch: str) -> bool:
        """Validate git branch name format"""
        if not branch:
            return False
        
        # Git branch name rules (simplified)
        invalid_chars = ['~', '^', ':', '?', '*', '[', '\\', ' ']
        if any(char in branch for char in invalid_chars):
            return False
        
        if branch.startswith('.') or branch.endswith('.'):
            return False
        
        if '..' in branch or '//' in branch:
            return False
        
        return True
    
    def _is_valid_glob_pattern(self, pattern: str) -> bool:
        """Validate glob pattern format"""
        if not pattern:
            return False
        
        # Basic validation - could be more sophisticated
        try:
            import fnmatch
            fnmatch.translate(pattern)
            return True
        except Exception:
            return False
    
    def _is_valid_template_name(self, template: str) -> bool:
        """Validate template name format"""
        if not template:
            return False
        
        # Template names should be alphanumeric with underscores/hyphens
        return re.match(r'^[a-zA-Z0-9_-]+$', template) is not None
    
    def _is_valid_file_size(self, size_str: str) -> bool:
        """Validate file size format"""
        try:
            pattern = r'^(\d+(?:\.\d+)?)\s*([KMGT]?B?)$'
            match = re.match(pattern, size_str.upper().strip())
            return match is not None
        except Exception:
            return False