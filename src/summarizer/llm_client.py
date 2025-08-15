"""LLM client for OpenAI and Anthropic APIs."""

import os
import time
import json
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

try:
    import openai
except ImportError:
    openai = None

try:
    import anthropic
except ImportError:
    anthropic = None

from ..config import LLMConfig
from ..logger import get_logger


class LLMError(Exception):
    """LLM related errors."""
    pass


class RateLimitError(LLMError):
    """Rate limit exceeded error."""
    pass


class BaseLLMClient(ABC):
    """Base class for LLM clients."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.logger = get_logger()
        self.api_key = os.getenv(config.api_key_env)
        
        if not self.api_key:
            raise LLMError(f"API key not found in environment variable: {config.api_key_env}")
    
    @abstractmethod
    def generate_summary(self, content: str, context: str = "") -> str:
        """Generate a summary of the given content."""
        pass
    
    @abstractmethod
    def generate_weekly_summary(self, articles_summary: str) -> str:
        """Generate a weekly summary from multiple articles."""
        pass
    
    def _retry_with_backoff(self, func, max_retries: int = None, *args, **kwargs):
        """Execute function with exponential backoff retry logic."""
        max_retries = max_retries or self.config.max_retries
        
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except RateLimitError:
                if attempt == max_retries:
                    raise
                
                wait_time = (2 ** attempt) * self.config.rate_limit_delay
                self.logger.warning(f"Rate limit hit, waiting {wait_time}s before retry {attempt + 1}")
                time.sleep(wait_time)
            except Exception as e:
                if attempt == max_retries:
                    raise
                
                wait_time = (2 ** attempt) * 1.0
                self.logger.warning(f"API error on attempt {attempt + 1}: {e}, retrying in {wait_time}s")
                time.sleep(wait_time)


class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        
        if openai is None:
            raise LLMError("OpenAI package not installed. Install with: pip install openai")
        
        self.client = openai.OpenAI(api_key=self.api_key)
    
    def generate_summary(self, content: str, context: str = "") -> str:
        """Generate summary using OpenAI API."""
        return self._retry_with_backoff(self._call_openai_api, None, content, context)
    
    def _call_openai_api(self, content: str, context: str = "") -> str:
        """Make actual API call to OpenAI."""
        prompt = self._build_summary_prompt(content, context)
        
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "You are a technical news summarizer. Create concise, informative summaries that highlight key technical details and relevance."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature
            )
            
            summary = response.choices[0].message.content.strip()
            self.logger.debug(f"Generated summary of length {len(summary)}")
            return summary
            
        except openai.RateLimitError as e:
            self.logger.warning(f"OpenAI rate limit: {e}")
            raise RateLimitError(f"OpenAI rate limit: {e}")
        except Exception as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise LLMError(f"OpenAI API error: {e}")
    
    def generate_weekly_summary(self, articles_summary: str) -> str:
        """Generate weekly summary using OpenAI API."""
        prompt = f"""Create a weekly summary report from these article summaries:

{articles_summary}

Please provide:
1. Key trends and themes
2. Important developments
3. Notable releases or updates
4. Security or performance insights

Keep it concise but comprehensive."""

        return self._retry_with_backoff(self._call_openai_weekly_api, None, prompt)
    
    def _call_openai_weekly_api(self, prompt: str) -> str:
        """Make API call for weekly summary."""
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": "You are a technical news analyst. Create insightful weekly summaries that identify trends and important developments."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config.max_tokens * 3,  # Longer for weekly summary
                temperature=self.config.temperature
            )
            
            return response.choices[0].message.content.strip()
            
        except openai.RateLimitError as e:
            raise RateLimitError(f"OpenAI rate limit: {e}")
        except Exception as e:
            raise LLMError(f"OpenAI API error: {e}")
    
    def _build_summary_prompt(self, content: str, context: str = "") -> str:
        """Build prompt for summarization."""
        context_part = f"Context: {context}\n\n" if context else ""
        
        return f"""{context_part}Please summarize this technical article in 2-3 sentences, focusing on:
- Key technical points
- Practical implications
- Relevance to software development/security

Article content:
{content[:3000]}"""  # Limit content to avoid token limits


class AnthropicClient(BaseLLMClient):
    """Anthropic (Claude) API client."""
    
    def __init__(self, config: LLMConfig):
        super().__init__(config)
        
        if anthropic is None:
            raise LLMError("Anthropic package not installed. Install with: pip install anthropic")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def generate_summary(self, content: str, context: str = "") -> str:
        """Generate summary using Anthropic API."""
        return self._retry_with_backoff(self._call_anthropic_api, None, content, context)
    
    def _call_anthropic_api(self, content: str, context: str = "") -> str:
        """Make actual API call to Anthropic."""
        prompt = self._build_summary_prompt(content, context)
        
        try:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            summary = response.content[0].text.strip()
            self.logger.debug(f"Generated summary of length {len(summary)}")
            return summary
            
        except anthropic.RateLimitError as e:
            self.logger.warning(f"Anthropic rate limit: {e}")
            raise RateLimitError(f"Anthropic rate limit: {e}")
        except Exception as e:
            self.logger.error(f"Anthropic API error: {e}")
            raise LLMError(f"Anthropic API error: {e}")
    
    def generate_weekly_summary(self, articles_summary: str) -> str:
        """Generate weekly summary using Anthropic API."""
        prompt = f"""Create a comprehensive weekly summary report from these article summaries:

{articles_summary}

Please analyze and provide:
1. **Key Trends**: Major themes and patterns across articles
2. **Important Developments**: Significant announcements, releases, or breakthroughs
3. **Technical Insights**: Notable technical details, security issues, or performance improvements
4. **Future Implications**: What these developments might mean going forward

Structure your response clearly with sections. Keep it informative but concise."""

        return self._retry_with_backoff(self._call_anthropic_weekly_api, None, prompt)
    
    def _call_anthropic_weekly_api(self, prompt: str) -> str:
        """Make API call for weekly summary."""
        try:
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens * 3,  # Longer for weekly summary
                temperature=self.config.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            return response.content[0].text.strip()
            
        except anthropic.RateLimitError as e:
            raise RateLimitError(f"Anthropic rate limit: {e}")
        except Exception as e:
            raise LLMError(f"Anthropic API error: {e}")
    
    def _build_summary_prompt(self, content: str, context: str = "") -> str:
        """Build prompt for summarization."""
        context_part = f"Context: {context}\n\n" if context else ""
        
        return f"""{context_part}Please create a concise technical summary of this article in 2-3 sentences. Focus on:

- Key technical concepts and innovations
- Practical implications for developers/engineers
- Security, performance, or architectural insights
- Relevance to current technology trends

Article content:
{content[:3000]}

Summary:"""


class LLMClientFactory:
    """Factory for creating LLM clients."""
    
    @staticmethod
    def create_client(config: LLMConfig) -> BaseLLMClient:
        """Create appropriate LLM client based on configuration."""
        if config.provider.lower() == 'openai':
            return OpenAIClient(config)
        elif config.provider.lower() == 'anthropic':
            return AnthropicClient(config)
        else:
            raise LLMError(f"Unsupported LLM provider: {config.provider}")


class MockLLMClient(BaseLLMClient):
    """Mock LLM client for testing."""
    
    def generate_summary(self, content: str, context: str = "") -> str:
        """Generate mock summary."""
        words = content.split()[:20]
        return f"Mock summary: {' '.join(words)}..."
    
    def generate_weekly_summary(self, articles_summary: str) -> str:
        """Generate mock weekly summary."""
        return f"Mock weekly summary based on {len(articles_summary.split())} words of content."