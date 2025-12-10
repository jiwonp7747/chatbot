"""
AI API Configuration Module
Supports multiple AI providers with flexible configuration
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
import os
from enum import Enum


class AIProvider(Enum):
    """Supported AI providers"""
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    GEMINI = "GEMINI"


@dataclass
class AIConfig:
    """
    AI API configuration class

    Attributes:
        provider: AI provider name (openai, anthropic, google, custom)
        api_key: API authentication key
        api_url: API endpoint URL
        model_name: Model identifier
        max_tokens: Maximum tokens per request
        temperature: Response randomness (0.0-1.0)
        timeout: Request timeout in seconds
        extra_params: Additional provider-specific parameters
    """
    provider: str
    api_key: str
    api_url: str
    model_name: str
    max_tokens: int = 2000
    temperature: float = 0.7
    timeout: int = 30
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate configuration after initialization"""
        if not self.api_key:
            raise ValueError("API key is required")
        if not self.api_url:
            raise ValueError("API URL is required")
        if not self.model_name:
            raise ValueError("Model name is required")
        if not 0 <= self.temperature <= 1:
            raise ValueError("Temperature must be between 0 and 1")
        if self.max_tokens <= 0:
            raise ValueError("Max tokens must be positive")

    @classmethod
    def from_env(cls, prefix: str = "OPENAI") -> "AIConfig":
        """
        Create configuration from environment variables

        Environment variables:
            {PREFIX}_PROVIDER: AI provider name
            {PREFIX}_API_KEY: API key
            {PREFIX}_API_URL: API endpoint URL
            {PREFIX}_MODEL_NAME: Model name
            {PREFIX}_MAX_TOKENS: Max tokens (optional)
            {PREFIX}_TEMPERATURE: Temperature (optional)
            {PREFIX}_TIMEOUT: Timeout in seconds (optional)

        Args:
            prefix: Environment variable prefix (default: "AI")

        Returns:
            AIConfig instance
        """
        return cls(
            provider=os.getenv(f"{prefix}_PROVIDER", "openai"),
            api_key=os.getenv(f"{prefix}_API_KEY", ""),
            api_url=os.getenv(f"{prefix}_API_URL", ""),
            model_name=os.getenv(f"{prefix}_MODEL_NAME", ""),
            max_tokens=int(os.getenv(f"{prefix}_MAX_TOKENS", "2000")),
            temperature=float(os.getenv(f"{prefix}_TEMPERATURE", "0.7")),
            timeout=int(os.getenv(f"{prefix}_TIMEOUT", "30"))
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            "provider": self.provider,
            "api_url": self.api_url,
            "model_name": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "timeout": self.timeout,
            "extra_params": self.extra_params
        }
