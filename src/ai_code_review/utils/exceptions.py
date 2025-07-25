"""
Custom exceptions for AI Code Review
"""


class AICodeReviewError(Exception):
    """Base exception for all AI Code Review errors"""
    
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


class ConfigurationError(AICodeReviewError):
    """Raised when there's a configuration error"""
    
    def __init__(self, message: str):
        super().__init__(f"Configuration error: {message}", exit_code=3)


class GitError(AICodeReviewError):
    """Raised when git operations fail"""
    
    def __init__(self, message: str, command: str = None):
        if command:
            full_message = f"Git operation failed: {message} (command: {command})"
        else:
            full_message = f"Git operation failed: {message}"
        super().__init__(full_message, exit_code=1)
        self.command = command


class BedrockError(AICodeReviewError):
    """Raised when AWS Bedrock operations fail"""
    
    def __init__(self, message: str, service_error: str = None):
        if service_error:
            full_message = f"AWS Bedrock error: {message} ({service_error})"
        else:
            full_message = f"AWS Bedrock error: {message}"
        super().__init__(full_message, exit_code=2)
        self.service_error = service_error


class NetworkError(AICodeReviewError):
    """Raised when network operations fail"""
    
    def __init__(self, message: str, url: str = None):
        if url:
            full_message = f"Network error: {message} (URL: {url})"
        else:
            full_message = f"Network error: {message}"
        super().__init__(full_message, exit_code=4)
        self.url = url


class ValidationError(AICodeReviewError):
    """Raised when validation fails"""
    
    def __init__(self, message: str, field: str = None):
        if field:
            full_message = f"Validation error in {field}: {message}"
        else:
            full_message = f"Validation error: {message}"
        super().__init__(full_message, exit_code=3)
        self.field = field


class UserAbortError(AICodeReviewError):
    """Raised when user aborts the operation"""
    
    def __init__(self, message: str = "Operation aborted by user"):
        super().__init__(message, exit_code=5)


class TimeoutError(AICodeReviewError):
    """Raised when operations timeout"""
    
    def __init__(self, message: str, timeout_seconds: int = None):
        if timeout_seconds:
            full_message = f"Operation timed out after {timeout_seconds}s: {message}"
        else:
            full_message = f"Operation timed out: {message}"
        super().__init__(full_message, exit_code=6)
        self.timeout_seconds = timeout_seconds