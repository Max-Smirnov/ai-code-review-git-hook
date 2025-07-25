"""
Rule processor for AI Code Review
"""

import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional
import fnmatch

from ..utils.exceptions import ConfigurationError
from ..utils.logging import get_logger

logger = get_logger(__name__)


class RuleProcessor:
    """Processes and manages code review rules"""
    
    def __init__(self, config):
        """
        Initialize rule processor
        
        Args:
            config: Configuration manager
        """
        self.config = config
        self.review_config = config.get('review', {})
        self.enabled_rules = self.review_config.get('enabled_rules', [])
        
        # Cache for loaded rule templates
        self._template_cache = {}
    
    def load_rules_for_file(self, filename: str, template_names: List[str]) -> Dict[str, Any]:
        """
        Load applicable rules for a specific file
        
        Args:
            filename: File path
            template_names: List of rule template names to load
            
        Returns:
            Dictionary of rule_name -> rule_config
        """
        logger.debug(f"Loading rules for {filename} using templates: {template_names}")
        
        all_rules = {}
        
        # Load each template
        for template_name in template_names:
            try:
                template_rules = self._load_rule_template(template_name)
                if template_rules:
                    # Merge rules, with later templates taking precedence
                    all_rules.update(template_rules)
            except Exception as e:
                logger.warning(f"Failed to load rule template {template_name}: {e}")
                continue
        
        # Filter by enabled rules
        filtered_rules = {}
        for rule_name, rule_config in all_rules.items():
            if rule_name in self.enabled_rules:
                # Apply file-specific overrides if they exist
                final_config = self._apply_file_overrides(rule_config, filename)
                filtered_rules[rule_name] = final_config
        
        logger.debug(f"Loaded {len(filtered_rules)} rules for {filename}")
        return filtered_rules
    
    def _load_rule_template(self, template_name: str) -> Dict[str, Any]:
        """
        Load a rule template from file
        
        Args:
            template_name: Name of the template to load
            
        Returns:
            Dictionary of rules from the template
        """
        # Check cache first
        if template_name in self._template_cache:
            return self._template_cache[template_name]
        
        # Try to find template file
        template_paths = [
            Path(__file__).parent.parent / 'config' / 'templates' / f'{template_name}.yaml',
            Path.cwd() / '.ai-code-review' / 'templates' / f'{template_name}.yaml',
            Path.home() / '.ai-code-review' / 'templates' / f'{template_name}.yaml',
        ]
        
        template_data = None
        for template_path in template_paths:
            if template_path.exists():
                try:
                    with open(template_path, 'r', encoding='utf-8') as f:
                        template_data = yaml.safe_load(f)
                    logger.debug(f"Loaded template {template_name} from {template_path}")
                    break
                except Exception as e:
                    logger.warning(f"Failed to load template from {template_path}: {e}")
                    continue
        
        if template_data is None:
            logger.warning(f"Template {template_name} not found in any location")
            return {}
        
        # Extract rules from template
        rules = template_data.get('rules', {})
        
        # Cache the result
        self._template_cache[template_name] = rules
        
        return rules
    
    def _apply_file_overrides(self, rule_config: Dict[str, Any], filename: str) -> Dict[str, Any]:
        """
        Apply file-specific rule overrides
        
        Args:
            rule_config: Base rule configuration
            filename: File path
            
        Returns:
            Rule configuration with overrides applied
        """
        # Make a copy to avoid modifying the original
        final_config = rule_config.copy()
        
        # Check for file-specific overrides in the rule config
        file_overrides = rule_config.get('file_overrides', {})
        
        for pattern, overrides in file_overrides.items():
            if fnmatch.fnmatch(filename, pattern):
                logger.debug(f"Applying file override for pattern {pattern} to {filename}")
                final_config.update(overrides)
        
        return final_config
    
    def get_rule_prompt(self, rule_name: str, rule_config: Dict[str, Any]) -> str:
        """
        Get the prompt text for a specific rule
        
        Args:
            rule_name: Name of the rule
            rule_config: Rule configuration
            
        Returns:
            Prompt text for the rule
        """
        return rule_config.get('prompt', f'Review for {rule_name} issues')
    
    def get_rule_severity(self, rule_name: str, rule_config: Dict[str, Any]) -> str:
        """
        Get the default severity for a rule
        
        Args:
            rule_name: Name of the rule
            rule_config: Rule configuration
            
        Returns:
            Default severity level
        """
        return rule_config.get('severity', 'warning')
    
    def is_rule_enabled(self, rule_name: str, rule_config: Dict[str, Any]) -> bool:
        """
        Check if a rule is enabled
        
        Args:
            rule_name: Name of the rule
            rule_config: Rule configuration
            
        Returns:
            True if rule is enabled
        """
        return rule_config.get('enabled', True)
    
    def get_context_prompt(self, context: str, rule_config: Dict[str, Any]) -> Optional[str]:
        """
        Get context-specific prompt for a rule
        
        Args:
            context: Context type (new_file, large_change, etc.)
            rule_config: Rule configuration
            
        Returns:
            Context-specific prompt or None
        """
        context_prompts = rule_config.get('context_prompts', {})
        return context_prompts.get(context)
    
    def validate_rule_template(self, template_data: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate a rule template structure
        
        Args:
            template_data: Template data to validate
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check required fields
        if 'name' not in template_data:
            errors.append("Template missing 'name' field")
        
        if 'rules' not in template_data:
            errors.append("Template missing 'rules' field")
        else:
            rules = template_data['rules']
            if not isinstance(rules, dict):
                errors.append("'rules' field must be a dictionary")
            else:
                # Validate each rule
                for rule_name, rule_config in rules.items():
                    if not isinstance(rule_config, dict):
                        errors.append(f"Rule '{rule_name}' must be a dictionary")
                        continue
                    
                    # Check rule structure
                    if 'prompt' not in rule_config:
                        errors.append(f"Rule '{rule_name}' missing 'prompt' field")
                    
                    severity = rule_config.get('severity', 'warning')
                    if severity not in ['error', 'warning', 'info', 'suggestion']:
                        errors.append(f"Rule '{rule_name}' has invalid severity: {severity}")
        
        # Check file patterns if present
        if 'file_patterns' in template_data:
            patterns = template_data['file_patterns']
            if not isinstance(patterns, list):
                errors.append("'file_patterns' must be a list")
            else:
                for pattern in patterns:
                    if not isinstance(pattern, str):
                        errors.append(f"File pattern must be string: {pattern}")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def create_rule_template(self, template_name: str, template_data: Dict[str, Any]) -> bool:
        """
        Create a new rule template
        
        Args:
            template_name: Name for the new template
            template_data: Template configuration
            
        Returns:
            True if template was created successfully
        """
        # Validate template
        is_valid, errors = self.validate_rule_template(template_data)
        if not is_valid:
            raise ConfigurationError(f"Invalid template: {'; '.join(errors)}")
        
        # Create template directory if it doesn't exist
        template_dir = Path.home() / '.ai-code-review' / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        
        # Write template file
        template_path = template_dir / f'{template_name}.yaml'
        try:
            with open(template_path, 'w', encoding='utf-8') as f:
                yaml.dump(template_data, f, default_flow_style=False, sort_keys=False)
            
            logger.info(f"Created rule template: {template_path}")
            
            # Clear cache to force reload
            if template_name in self._template_cache:
                del self._template_cache[template_name]
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create template {template_name}: {e}")
            return False
    
    def list_available_templates(self) -> List[str]:
        """
        List all available rule templates
        
        Returns:
            List of template names
        """
        templates = set()
        
        # Check all possible template locations
        template_dirs = [
            Path(__file__).parent.parent / 'config' / 'templates',
            Path.cwd() / '.ai-code-review' / 'templates',
            Path.home() / '.ai-code-review' / 'templates',
        ]
        
        for template_dir in template_dirs:
            if template_dir.exists():
                for template_file in template_dir.glob('*.yaml'):
                    template_name = template_file.stem
                    templates.add(template_name)
        
        return sorted(list(templates))
    
    def get_template_info(self, template_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a template
        
        Args:
            template_name: Name of the template
            
        Returns:
            Template metadata or None if not found
        """
        template_paths = [
            Path(__file__).parent.parent / 'config' / 'templates' / f'{template_name}.yaml',
            Path.cwd() / '.ai-code-review' / 'templates' / f'{template_name}.yaml',
            Path.home() / '.ai-code-review' / 'templates' / f'{template_name}.yaml',
        ]
        
        for template_path in template_paths:
            if template_path.exists():
                try:
                    with open(template_path, 'r', encoding='utf-8') as f:
                        template_data = yaml.safe_load(f)
                    
                    # Extract metadata
                    info = {
                        'name': template_data.get('name', template_name),
                        'description': template_data.get('description', ''),
                        'version': template_data.get('version', '1.0.0'),
                        'file_patterns': template_data.get('file_patterns', []),
                        'rules': list(template_data.get('rules', {}).keys()),
                        'path': str(template_path)
                    }
                    
                    return info
                    
                except Exception as e:
                    logger.warning(f"Failed to read template info from {template_path}: {e}")
                    continue
        
        return None
    
    def clear_template_cache(self) -> None:
        """Clear the template cache"""
        self._template_cache.clear()
        logger.debug("Cleared rule template cache")