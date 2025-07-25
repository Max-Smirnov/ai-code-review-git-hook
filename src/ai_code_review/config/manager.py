"""
Configuration manager for AI Code Review
"""

import os
import yaml
import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from copy import deepcopy

from ..utils.exceptions import ConfigurationError
from ..utils.logging import get_logger
from .validator import ConfigValidator

logger = get_logger(__name__)


class ConfigManager:
    """
    Manages hierarchical configuration loading and access
    
    Configuration is loaded in the following order (later configs override earlier ones):
    1. Default configuration (package defaults)
    2. Global user configuration (~/.ai-code-review/config.yaml)
    3. Project configuration (.ai-code-review.yaml in git root)
    4. Environment variables (prefixed with AI_CODE_REVIEW_)
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize configuration manager
        
        Args:
            project_root: Project root directory (defaults to current git root)
        """
        self.project_root = project_root or self._find_git_root()
        self.validator = ConfigValidator()
        self._config = {}
        self._loaded = False
        
        # Load configuration
        self.reload()
    
    def reload(self) -> None:
        """Reload configuration from all sources"""
        logger.debug("Reloading configuration")
        
        # Start with default configuration
        self._config = self._load_default_config()
        
        # Load global user configuration
        self._merge_config(self._load_global_config())
        
        # Load project configuration
        self._merge_config(self._load_project_config())
        
        # Apply environment variable overrides
        self._apply_env_overrides()
        
        # Validate final configuration
        self._validate_config()
        
        self._loaded = True
        logger.debug("Configuration loaded successfully")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Args:
            key: Configuration key (e.g., 'bedrock.model')
            default: Default value if key not found
            
        Returns:
            Configuration value
        """
        if not self._loaded:
            self.reload()
        
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value using dot notation
        
        Args:
            key: Configuration key (e.g., 'bedrock.model')
            value: Value to set
        """
        keys = key.split('.')
        config = self._config
        
        # Navigate to parent of target key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # Set the value
        config[keys[-1]] = value
    
    def get_rule_templates(self, filename: str) -> List[str]:
        """
        Get applicable rule templates for a file
        
        Args:
            filename: File path to match against patterns
            
        Returns:
            List of template names
        """
        rule_templates = self.get('review.rule_templates', {})
        applicable_templates = []
        
        # Find matching patterns (order matters)
        for pattern, templates in rule_templates.items():
            if fnmatch.fnmatch(filename, pattern):
                if isinstance(templates, str):
                    applicable_templates.append(templates)
                elif isinstance(templates, list):
                    applicable_templates.extend(templates)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_templates = []
        for template in applicable_templates:
            if template not in seen:
                seen.add(template)
                unique_templates.append(template)
        
        return unique_templates
    
    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate current configuration
        
        Returns:
            Tuple of (is_valid, error_messages)
        """
        return self.validator.validate(self._config)
    
    def to_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary"""
        return deepcopy(self._config)
    
    def _find_git_root(self) -> Path:
        """Find git repository root"""
        current = Path.cwd()
        
        while current != current.parent:
            if (current / '.git').exists():
                return current
            current = current.parent
        
        # If no git root found, use current directory
        return Path.cwd()
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration"""
        default_config = {
            'bedrock': {
                'region': 'us-east-1',
                'profile': None,
                'model': 'anthropic.claude-3-5-sonnet-20241022-v2:0',
                'max_tokens': 4000,
                'temperature': 0.1,
                'timeout': 30,
                'retry_attempts': 3,
                'retry_delay': 1,
            },
            'git': {
                'default_compare_branch': 'main',
                'max_diff_size': 10000,
                'max_files': 50,
                'exclude_patterns': [
                    '*.min.js',
                    '*.min.css',
                    'package-lock.json',
                    'yarn.lock',
                    '*.generated.*',
                    'dist/*',
                    'build/*',
                    'node_modules/*',
                ],
                'include_patterns': [],
                'binary_file_extensions': [
                    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff',
                    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                    '.zip', '.tar', '.gz', '.rar', '.7z',
                    '.exe', '.dll', '.so', '.dylib',
                ],
            },
            'review': {
                'enabled_rules': [
                    'security',
                    'performance',
                    'maintainability',
                    'style',
                    'documentation',
                ],
                'severity_threshold': 'warning',
                'max_issues_per_file': 10,
                'context_lines': 3,
                'batch_size': 5,
                'rule_templates': {
                    '*.py': ['python', 'general'],
                    '*.js': ['javascript', 'general'],
                    '*.ts': ['typescript', 'general'],
                    '*.jsx': ['react', 'javascript', 'general'],
                    '*.tsx': ['react', 'typescript', 'general'],
                    '*.java': ['java', 'general'],
                    '*.go': ['golang', 'general'],
                    '*': ['general'],
                },
            },
            'ui': {
                'interactive_mode': True,
                'color_output': True,
                'show_diff_context': True,
                'show_progress': True,
                'max_display_issues': 20,
                'summary_only': False,
                'auto_approve_threshold': None,
            },
            'logging': {
                'level': 'INFO',
                'file': None,
                'max_file_size': '10MB',
                'backup_count': 3,
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            },
            'performance': {
                'cache_enabled': True,
                'cache_ttl': 3600,
                'parallel_processing': True,
                'max_workers': 4,
            },
        }
        
        return default_config
    
    def _load_global_config(self) -> Dict[str, Any]:
        """Load global user configuration"""
        global_config_path = Path.home() / '.ai-code-review' / 'config.yaml'
        return self._load_yaml_file(global_config_path)
    
    def _load_project_config(self) -> Dict[str, Any]:
        """Load project-specific configuration"""
        project_config_path = self.project_root / '.ai-code-review.yaml'
        return self._load_yaml_file(project_config_path)
    
    def _load_yaml_file(self, path: Path) -> Dict[str, Any]:
        """Load YAML configuration file"""
        if not path.exists():
            logger.debug(f"Configuration file not found: {path}")
            return {}
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            logger.debug(f"Loaded configuration from {path}")
            return config
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {path}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load {path}: {e}")
    
    def _merge_config(self, new_config: Dict[str, Any]) -> None:
        """Merge new configuration into existing configuration"""
        if not new_config:
            return
        
        self._deep_merge(self._config, new_config)
    
    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        """Deep merge two dictionaries"""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides"""
        prefix = 'AI_CODE_REVIEW_'
        
        for env_key, env_value in os.environ.items():
            if not env_key.startswith(prefix):
                continue
            
            # Convert environment variable name to config key
            config_key = env_key[len(prefix):].lower().replace('_', '.')
            
            # Parse value
            parsed_value = self._parse_env_value(env_value)
            
            # Set in configuration
            self.set(config_key, parsed_value)
            logger.debug(f"Applied environment override: {config_key} = {parsed_value}")
    
    def _parse_env_value(self, value: str) -> Union[str, int, float, bool, List[str]]:
        """Parse environment variable value to appropriate type"""
        # Boolean values
        if value.lower() in ('true', 'yes', '1', 'on'):
            return True
        elif value.lower() in ('false', 'no', '0', 'off'):
            return False
        
        # Numeric values
        try:
            if '.' in value:
                return float(value)
            else:
                return int(value)
        except ValueError:
            pass
        
        # List values (comma-separated)
        if ',' in value:
            return [item.strip() for item in value.split(',')]
        
        # String value
        return value
    
    def _validate_config(self) -> None:
        """Validate the final configuration"""
        is_valid, errors = self.validate()
        if not is_valid:
            raise ConfigurationError(f"Configuration validation failed: {'; '.join(errors)}")