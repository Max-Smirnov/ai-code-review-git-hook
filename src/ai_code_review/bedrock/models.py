"""
Model management for AWS Bedrock
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum

from ..utils.logging import get_logger

logger = get_logger(__name__)


class ModelProvider(Enum):
    """Supported model providers"""
    ANTHROPIC = "anthropic"
    META = "meta"
    COHERE = "cohere"
    AI21 = "ai21"
    AMAZON = "amazon"


@dataclass
class ModelInfo:
    """Information about a Bedrock model"""
    model_id: str
    provider: str
    name: str
    description: str
    max_tokens: int
    input_cost_per_1k: float  # Cost per 1K input tokens in USD
    output_cost_per_1k: float  # Cost per 1K output tokens in USD
    context_window: int
    supports_system_prompt: bool = True
    recommended_for_code: bool = True


class ModelManager:
    """Manages Bedrock model information and capabilities"""
    
    def __init__(self):
        """Initialize model manager with supported models"""
        self._models = self._initialize_models()
    
    def _initialize_models(self) -> Dict[str, ModelInfo]:
        """Initialize supported models with their information"""
        models = {}
        
        # Anthropic Claude models
        models["anthropic.claude-3-5-sonnet-20241022-v2:0"] = ModelInfo(
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            provider=ModelProvider.ANTHROPIC.value,
            name="Claude 3.5 Sonnet",
            description="Most capable model for complex reasoning and code analysis",
            max_tokens=8192,
            input_cost_per_1k=0.003,
            output_cost_per_1k=0.015,
            context_window=200000,
            supports_system_prompt=True,
            recommended_for_code=True
        )
        
        models["anthropic.claude-3-haiku-20240307-v1:0"] = ModelInfo(
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            provider=ModelProvider.ANTHROPIC.value,
            name="Claude 3 Haiku",
            description="Fastest and most cost-effective model for simple tasks",
            max_tokens=4096,
            input_cost_per_1k=0.00025,
            output_cost_per_1k=0.00125,
            context_window=200000,
            supports_system_prompt=True,
            recommended_for_code=True
        )
        
        models["anthropic.claude-3-sonnet-20240229-v1:0"] = ModelInfo(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            provider=ModelProvider.ANTHROPIC.value,
            name="Claude 3 Sonnet",
            description="Balanced model for most use cases",
            max_tokens=4096,
            input_cost_per_1k=0.003,
            output_cost_per_1k=0.015,
            context_window=200000,
            supports_system_prompt=True,
            recommended_for_code=True
        )
        
        # Meta Llama models
        models["meta.llama3-70b-instruct-v1:0"] = ModelInfo(
            model_id="meta.llama3-70b-instruct-v1:0",
            provider=ModelProvider.META.value,
            name="Llama 3 70B Instruct",
            description="Large language model good for complex reasoning",
            max_tokens=2048,
            input_cost_per_1k=0.00265,
            output_cost_per_1k=0.0035,
            context_window=8192,
            supports_system_prompt=True,
            recommended_for_code=True
        )
        
        models["meta.llama3-8b-instruct-v1:0"] = ModelInfo(
            model_id="meta.llama3-8b-instruct-v1:0",
            provider=ModelProvider.META.value,
            name="Llama 3 8B Instruct",
            description="Smaller, faster model for basic tasks",
            max_tokens=2048,
            input_cost_per_1k=0.0003,
            output_cost_per_1k=0.0006,
            context_window=8192,
            supports_system_prompt=True,
            recommended_for_code=True
        )
        
        # Cohere models
        models["cohere.command-r-plus-v1:0"] = ModelInfo(
            model_id="cohere.command-r-plus-v1:0",
            provider=ModelProvider.COHERE.value,
            name="Command R+",
            description="Advanced model for complex tasks and reasoning",
            max_tokens=4000,
            input_cost_per_1k=0.003,
            output_cost_per_1k=0.015,
            context_window=128000,
            supports_system_prompt=True,
            recommended_for_code=True
        )
        
        models["cohere.command-r-v1:0"] = ModelInfo(
            model_id="cohere.command-r-v1:0",
            provider=ModelProvider.COHERE.value,
            name="Command R",
            description="Balanced model for general use cases",
            max_tokens=4000,
            input_cost_per_1k=0.0005,
            output_cost_per_1k=0.0015,
            context_window=128000,
            supports_system_prompt=True,
            recommended_for_code=True
        )
        
        # AI21 models
        models["ai21.jamba-instruct-v1:0"] = ModelInfo(
            model_id="ai21.jamba-instruct-v1:0",
            provider=ModelProvider.AI21.value,
            name="Jamba Instruct",
            description="Hybrid architecture model with long context",
            max_tokens=4096,
            input_cost_per_1k=0.0005,
            output_cost_per_1k=0.0007,
            context_window=256000,
            supports_system_prompt=True,
            recommended_for_code=True
        )
        
        return models
    
    def get_model_info(self, model_id: str) -> ModelInfo:
        """
        Get information about a specific model
        
        Args:
            model_id: Bedrock model ID
            
        Returns:
            ModelInfo object
            
        Raises:
            ValueError: If model is not supported
        """
        if model_id not in self._models:
            raise ValueError(f"Unsupported model: {model_id}")
        
        return self._models[model_id]
    
    def list_models(self) -> List[str]:
        """List all supported model IDs"""
        return list(self._models.keys())
    
    def list_models_by_provider(self, provider: str) -> List[str]:
        """
        List models by provider
        
        Args:
            provider: Provider name (anthropic, meta, cohere, ai21)
            
        Returns:
            List of model IDs for the provider
        """
        return [
            model_id for model_id, info in self._models.items()
            if info.provider == provider
        ]
    
    def get_recommended_models(self, use_case: str = "code_review") -> List[str]:
        """
        Get recommended models for a specific use case
        
        Args:
            use_case: Use case (code_review, general, cost_optimized, performance)
            
        Returns:
            List of recommended model IDs
        """
        if use_case == "code_review":
            # Best models for code review
            return [
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "anthropic.claude-3-sonnet-20240229-v1:0",
                "meta.llama3-70b-instruct-v1:0",
                "cohere.command-r-plus-v1:0"
            ]
        elif use_case == "cost_optimized":
            # Most cost-effective models
            return [
                "anthropic.claude-3-haiku-20240307-v1:0",
                "meta.llama3-8b-instruct-v1:0",
                "cohere.command-r-v1:0"
            ]
        elif use_case == "performance":
            # Fastest models
            return [
                "anthropic.claude-3-haiku-20240307-v1:0",
                "meta.llama3-8b-instruct-v1:0"
            ]
        elif use_case == "long_context":
            # Models with largest context windows
            return [
                "ai21.jamba-instruct-v1:0",
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "cohere.command-r-plus-v1:0"
            ]
        else:
            # General recommendations
            return [
                "anthropic.claude-3-5-sonnet-20241022-v2:0",
                "anthropic.claude-3-sonnet-20240229-v1:0",
                "meta.llama3-70b-instruct-v1:0"
            ]
    
    def is_model_supported(self, model_id: str) -> bool:
        """Check if a model is supported"""
        return model_id in self._models
    
    def get_cost_estimate(self, model_id: str, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate cost for a model invocation
        
        Args:
            model_id: Bedrock model ID
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            
        Returns:
            Estimated cost in USD
        """
        if not self.is_model_supported(model_id):
            return 0.0
        
        model_info = self.get_model_info(model_id)
        
        input_cost = (input_tokens / 1000) * model_info.input_cost_per_1k
        output_cost = (output_tokens / 1000) * model_info.output_cost_per_1k
        
        return input_cost + output_cost
    
    def compare_models(self, model_ids: List[str]) -> Dict[str, Dict[str, any]]:
        """
        Compare multiple models
        
        Args:
            model_ids: List of model IDs to compare
            
        Returns:
            Dictionary with model comparison data
        """
        comparison = {}
        
        for model_id in model_ids:
            if not self.is_model_supported(model_id):
                continue
            
            model_info = self.get_model_info(model_id)
            comparison[model_id] = {
                "name": model_info.name,
                "provider": model_info.provider,
                "max_tokens": model_info.max_tokens,
                "context_window": model_info.context_window,
                "input_cost_per_1k": model_info.input_cost_per_1k,
                "output_cost_per_1k": model_info.output_cost_per_1k,
                "recommended_for_code": model_info.recommended_for_code,
                "cost_per_review_estimate": self.get_cost_estimate(model_id, 2000, 500)  # Typical review
            }
        
        return comparison
    
    def get_model_by_criteria(self, 
                             max_cost_per_1k: Optional[float] = None,
                             min_context_window: Optional[int] = None,
                             provider: Optional[str] = None,
                             code_optimized: bool = True) -> List[str]:
        """
        Find models matching specific criteria
        
        Args:
            max_cost_per_1k: Maximum cost per 1K tokens
            min_context_window: Minimum context window size
            provider: Specific provider to filter by
            code_optimized: Whether to only include code-optimized models
            
        Returns:
            List of matching model IDs
        """
        matching_models = []
        
        for model_id, model_info in self._models.items():
            # Check code optimization requirement
            if code_optimized and not model_info.recommended_for_code:
                continue
            
            # Check provider filter
            if provider and model_info.provider != provider:
                continue
            
            # Check cost constraint
            if max_cost_per_1k and model_info.output_cost_per_1k > max_cost_per_1k:
                continue
            
            # Check context window requirement
            if min_context_window and model_info.context_window < min_context_window:
                continue
            
            matching_models.append(model_id)
        
        # Sort by cost (cheapest first)
        matching_models.sort(key=lambda x: self._models[x].output_cost_per_1k)
        
        return matching_models
    
    def get_provider_info(self) -> Dict[str, Dict[str, any]]:
        """Get information about all providers"""
        providers = {}
        
        for model_info in self._models.values():
            provider = model_info.provider
            if provider not in providers:
                providers[provider] = {
                    "models": [],
                    "min_cost": float('inf'),
                    "max_context": 0,
                    "supports_code": False
                }
            
            providers[provider]["models"].append(model_info.model_id)
            providers[provider]["min_cost"] = min(
                providers[provider]["min_cost"], 
                model_info.output_cost_per_1k
            )
            providers[provider]["max_context"] = max(
                providers[provider]["max_context"], 
                model_info.context_window
            )
            if model_info.recommended_for_code:
                providers[provider]["supports_code"] = True
        
        return providers