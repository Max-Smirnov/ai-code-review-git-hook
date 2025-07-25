"""
AWS Bedrock client for AI Code Review
"""

import json
import time
import boto3
from typing import Dict, Any, Optional, List
from botocore.exceptions import ClientError, NoCredentialsError, BotoCoreError
from dataclasses import dataclass

from ..utils.exceptions import BedrockError, NetworkError
from ..utils.logging import get_logger, log_performance
from .models import ModelManager

logger = get_logger(__name__)


@dataclass
class BedrockResponse:
    """Response from Bedrock API"""
    content: str
    model_id: str
    input_tokens: int
    output_tokens: int
    stop_reason: str
    cost_estimate: float = 0.0


class BedrockClient:
    """AWS Bedrock client with retry logic and error handling"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Bedrock client
        
        Args:
            config: Bedrock configuration
        """
        self.config = config
        self.model_manager = ModelManager()
        
        # Extract configuration
        self.region = config.get('region', 'us-east-1')
        self.profile = config.get('profile')
        self.model_id = config.get('model', 'anthropic.claude-3-5-sonnet-20241022-v2:0')
        self.max_tokens = config.get('max_tokens', 4000)
        self.temperature = config.get('temperature', 0.1)
        self.timeout = config.get('timeout', 30)
        self.retry_attempts = config.get('retry_attempts', 3)
        self.retry_delay = config.get('retry_delay', 1)
        
        # Initialize AWS clients
        self._runtime_client = None
        self._management_client = None
        self._initialize_clients()
    
    def _initialize_clients(self) -> None:
        """Initialize AWS Bedrock clients"""
        try:
            session_kwargs = {'region_name': self.region}
            if self.profile:
                session_kwargs['profile_name'] = self.profile
            
            session = boto3.Session(**session_kwargs)
            
            # Create runtime client for model invocation
            self._runtime_client = session.client(
                'bedrock-runtime',
                region_name=self.region
            )
            
            # Create management client for listing models and other operations
            self._management_client = session.client(
                'bedrock',
                region_name=self.region
            )
            
            # Test credentials
            self._test_credentials()
            
            logger.info(f"Initialized Bedrock clients for region {self.region}")
            
        except NoCredentialsError:
            raise BedrockError(
                "AWS credentials not found. Please configure AWS credentials using "
                "AWS CLI, environment variables, or IAM roles."
            )
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            raise BedrockError(f"Failed to initialize Bedrock client: {error_code}", str(e))
        except Exception as e:
            raise BedrockError(f"Unexpected error initializing Bedrock client: {str(e)}")
    
    def _test_credentials(self) -> None:
        """Test AWS credentials by making a simple API call"""
        try:
            # Try to list foundation models to test credentials
            response = self._management_client.list_foundation_models()
            logger.debug("AWS credentials validated successfully")
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'UnauthorizedOperation':
                raise BedrockError(
                    "AWS credentials are valid but don't have permission to access Bedrock. "
                    "Please ensure your AWS user/role has the necessary Bedrock permissions."
                )
            else:
                raise BedrockError(f"AWS credential test failed: {error_code}", str(e))
    
    @log_performance
    def invoke_model(self, prompt: str, system_prompt: Optional[str] = None) -> BedrockResponse:
        """
        Invoke Bedrock model with retry logic
        
        Args:
            prompt: User prompt
            system_prompt: System prompt (optional)
            
        Returns:
            BedrockResponse object
        """
        logger.debug(f"Invoking model {self.model_id}")
        
        for attempt in range(self.retry_attempts + 1):
            try:
                return self._invoke_model_once(prompt, system_prompt)
            except BedrockError as e:
                if attempt == self.retry_attempts:
                    raise
                
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {self.retry_delay}s...")
                time.sleep(self.retry_delay * (2 ** attempt))  # Exponential backoff
        
        raise BedrockError("All retry attempts exhausted")
    
    def _invoke_model_once(self, prompt: str, system_prompt: Optional[str] = None) -> BedrockResponse:
        """Single model invocation attempt"""
        try:
            # Build request based on model type
            request_body = self._build_request_body(prompt, system_prompt)
            
            logger.debug(f"Sending request to {self.model_id}")
            
            # Make API call
            response = self._runtime_client.invoke_model(
                modelId=self.model_id,
                contentType='application/json',
                accept='application/json',
                body=json.dumps(request_body)
            )
            
            # Parse response
            response_body = json.loads(response['body'].read())
            
            return self._parse_response(response_body)
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            
            if error_code == 'ThrottlingException':
                raise BedrockError(f"Rate limit exceeded: {error_message}", error_code)
            elif error_code == 'ValidationException':
                raise BedrockError(f"Invalid request: {error_message}", error_code)
            elif error_code == 'ModelNotReadyException':
                raise BedrockError(f"Model not ready: {error_message}", error_code)
            elif error_code == 'ServiceQuotaExceededException':
                raise BedrockError(f"Service quota exceeded: {error_message}", error_code)
            else:
                raise BedrockError(f"Bedrock API error ({error_code}): {error_message}", error_code)
        
        except BotoCoreError as e:
            raise NetworkError(f"Network error calling Bedrock: {str(e)}")
        
        except json.JSONDecodeError as e:
            raise BedrockError(f"Failed to parse Bedrock response: {str(e)}")
        
        except Exception as e:
            raise BedrockError(f"Unexpected error calling Bedrock: {str(e)}")
    
    def _build_request_body(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Build request body based on model type"""
        model_info = self.model_manager.get_model_info(self.model_id)
        
        if model_info.provider == 'anthropic':
            return self._build_anthropic_request(prompt, system_prompt)
        elif model_info.provider == 'meta':
            return self._build_llama_request(prompt, system_prompt)
        elif model_info.provider == 'cohere':
            return self._build_cohere_request(prompt, system_prompt)
        elif model_info.provider == 'ai21':
            return self._build_ai21_request(prompt, system_prompt)
        else:
            raise BedrockError(f"Unsupported model provider: {model_info.provider}")
    
    def _build_anthropic_request(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Build request for Anthropic Claude models"""
        messages = [{"role": "user", "content": prompt}]
        
        request = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": messages
        }
        
        if system_prompt:
            request["system"] = system_prompt
        
        return request
    
    def _build_llama_request(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Build request for Meta Llama models"""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n{prompt} [/INST]"
        
        return {
            "prompt": full_prompt,
            "max_gen_len": self.max_tokens,
            "temperature": self.temperature,
            "top_p": 0.9
        }
    
    def _build_cohere_request(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Build request for Cohere models"""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        return {
            "message": full_prompt,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "p": 0.9
        }
    
    def _build_ai21_request(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Build request for AI21 models"""
        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"
        
        return {
            "messages": [{"role": "user", "content": full_prompt}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": 0.9
        }
    
    def _parse_response(self, response_body: Dict[str, Any]) -> BedrockResponse:
        """Parse response based on model type"""
        model_info = self.model_manager.get_model_info(self.model_id)
        
        if model_info.provider == 'anthropic':
            return self._parse_anthropic_response(response_body)
        elif model_info.provider == 'meta':
            return self._parse_llama_response(response_body)
        elif model_info.provider == 'cohere':
            return self._parse_cohere_response(response_body)
        elif model_info.provider == 'ai21':
            return self._parse_ai21_response(response_body)
        else:
            raise BedrockError(f"Unsupported model provider: {model_info.provider}")
    
    def _parse_anthropic_response(self, response_body: Dict[str, Any]) -> BedrockResponse:
        """Parse Anthropic Claude response"""
        content = ""
        if "content" in response_body and response_body["content"]:
            content = response_body["content"][0].get("text", "")
        
        usage = response_body.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        stop_reason = response_body.get("stop_reason", "unknown")
        
        # Estimate cost (approximate pricing)
        cost_estimate = self._estimate_cost(input_tokens, output_tokens)
        
        return BedrockResponse(
            content=content,
            model_id=self.model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
            cost_estimate=cost_estimate
        )
    
    def _parse_llama_response(self, response_body: Dict[str, Any]) -> BedrockResponse:
        """Parse Meta Llama response"""
        content = response_body.get("generation", "")
        
        # Llama doesn't provide detailed token usage in response
        input_tokens = 0
        output_tokens = len(content.split()) * 1.3  # Rough estimate
        stop_reason = response_body.get("stop_reason", "unknown")
        
        cost_estimate = self._estimate_cost(input_tokens, output_tokens)
        
        return BedrockResponse(
            content=content,
            model_id=self.model_id,
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            stop_reason=stop_reason,
            cost_estimate=cost_estimate
        )
    
    def _parse_cohere_response(self, response_body: Dict[str, Any]) -> BedrockResponse:
        """Parse Cohere response"""
        content = response_body.get("text", "")
        
        # Cohere token usage estimation
        input_tokens = 0
        output_tokens = len(content.split()) * 1.3
        stop_reason = "complete"
        
        cost_estimate = self._estimate_cost(input_tokens, output_tokens)
        
        return BedrockResponse(
            content=content,
            model_id=self.model_id,
            input_tokens=int(input_tokens),
            output_tokens=int(output_tokens),
            stop_reason=stop_reason,
            cost_estimate=cost_estimate
        )
    
    def _parse_ai21_response(self, response_body: Dict[str, Any]) -> BedrockResponse:
        """Parse AI21 response"""
        choices = response_body.get("choices", [])
        content = ""
        if choices:
            content = choices[0].get("message", {}).get("content", "")
        
        usage = response_body.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)
        stop_reason = "complete"
        
        cost_estimate = self._estimate_cost(input_tokens, output_tokens)
        
        return BedrockResponse(
            content=content,
            model_id=self.model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
            cost_estimate=cost_estimate
        )
    
    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost based on token usage"""
        model_info = self.model_manager.get_model_info(self.model_id)
        
        input_cost = (input_tokens / 1000) * model_info.input_cost_per_1k
        output_cost = (output_tokens / 1000) * model_info.output_cost_per_1k
        
        return input_cost + output_cost
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        return self.model_manager.get_model_info(self.model_id).__dict__
    
    def list_available_models(self) -> List[str]:
        """List available models"""
        return self.model_manager.list_models()
    
    def validate_model(self, model_id: str) -> bool:
        """Validate if model is supported"""
        return self.model_manager.is_model_supported(model_id)