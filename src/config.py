"""Configuration management for ainews."""

import os
import yaml
from typing import Dict, List, Any
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WebsiteConfig:
    url: str
    enabled: bool
    max_pages: int = 3
    max_articles: int = 50
    delay_between_requests: float = 1.0


@dataclass
class LLMConfig:
    provider: str
    api_key_env: str
    model: str
    max_tokens: int = 150
    temperature: float = 0.3
    max_retries: int = 3
    rate_limit_delay: float = 1.0


@dataclass
class StorageConfig:
    data_dir: str
    backup_enabled: bool = True
    retention_days: int = 90
    max_file_size_mb: int = 100


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "./logs/ainews.log"
    max_file_size_mb: int = 50
    backup_count: int = 5


@dataclass
class FilteringConfig:
    min_relevance_score: float = 0.3
    max_articles_per_day: int = 100
    duplicate_threshold: float = 0.9


@dataclass
class ReportingConfig:
    weekly_day: str = "sunday"
    output_format: str = "markdown"
    include_summaries: bool = True
    max_articles_per_topic: int = 10


@dataclass
class Config:
    interest_topics: List[str]
    websites: Dict[str, WebsiteConfig]
    llm_config: LLMConfig
    storage: StorageConfig
    logging: LoggingConfig
    filtering: FilteringConfig
    reporting: ReportingConfig


class ConfigError(Exception):
    """Configuration related errors."""
    pass


def load_config(config_path: str = "config/config.yaml") -> Config:
    """Load and validate configuration from YAML file."""
    try:
        config_file = Path(config_path)
        if not config_file.exists():
            raise ConfigError(f"Configuration file not found: {config_path}")
        
        with open(config_file, 'r') as f:
            data = yaml.safe_load(f)
        
        # Validate required sections
        required_sections = ['interest_topics', 'websites', 'llm_config']
        for section in required_sections:
            if section not in data:
                raise ConfigError(f"Missing required configuration section: {section}")
        
        # Parse website configurations
        websites = {}
        for name, website_data in data['websites'].items():
            # Type conversion for website config
            website_data = website_data.copy()
            if 'max_pages' in website_data:
                website_data['max_pages'] = int(website_data['max_pages'])
            if 'max_articles' in website_data:
                website_data['max_articles'] = int(website_data['max_articles'])
            if 'delay_between_requests' in website_data:
                website_data['delay_between_requests'] = float(website_data['delay_between_requests'])
            websites[name] = WebsiteConfig(**website_data)
        
        # Parse LLM configuration with type conversion
        llm_data = data['llm_config'].copy()
        # Ensure integer fields are converted to int
        if 'max_tokens' in llm_data:
            llm_data['max_tokens'] = int(llm_data['max_tokens'])
        if 'max_retries' in llm_data:
            llm_data['max_retries'] = int(llm_data['max_retries'])
        # Ensure float fields are converted to float
        if 'temperature' in llm_data:
            llm_data['temperature'] = float(llm_data['temperature'])
        if 'rate_limit_delay' in llm_data:
            llm_data['rate_limit_delay'] = float(llm_data['rate_limit_delay'])
        
        llm_config = LLMConfig(**llm_data)
        
        # Validate API key environment variable
        api_key = os.getenv(llm_config.api_key_env)
        if not api_key:
            raise ConfigError(
                f"API key environment variable not set: {llm_config.api_key_env}"
            )
        
        # Parse other configurations with defaults and type conversion
        storage_data = data.get('storage', {}).copy()
        if 'retention_days' in storage_data:
            storage_data['retention_days'] = int(storage_data['retention_days'])
        if 'max_file_size_mb' in storage_data:
            storage_data['max_file_size_mb'] = int(storage_data['max_file_size_mb'])
        storage = StorageConfig(**storage_data)
        
        logging_data = data.get('logging', {}).copy()
        if 'max_file_size_mb' in logging_data:
            logging_data['max_file_size_mb'] = int(logging_data['max_file_size_mb'])
        if 'backup_count' in logging_data:
            logging_data['backup_count'] = int(logging_data['backup_count'])
        logging_config = LoggingConfig(**logging_data)
        
        filtering_data = data.get('filtering', {}).copy()
        if 'min_relevance_score' in filtering_data:
            filtering_data['min_relevance_score'] = float(filtering_data['min_relevance_score'])
        if 'max_articles_per_day' in filtering_data:
            filtering_data['max_articles_per_day'] = int(filtering_data['max_articles_per_day'])
        if 'duplicate_threshold' in filtering_data:
            filtering_data['duplicate_threshold'] = float(filtering_data['duplicate_threshold'])
        filtering = FilteringConfig(**filtering_data)
        
        reporting_data = data.get('reporting', {}).copy()
        if 'max_articles_per_topic' in reporting_data:
            reporting_data['max_articles_per_topic'] = int(reporting_data['max_articles_per_topic'])
        reporting = ReportingConfig(**reporting_data)
        
        # Create data directories
        data_dir = Path(storage.data_dir)
        data_dir.mkdir(exist_ok=True)
        (data_dir / "articles").mkdir(exist_ok=True)
        (data_dir / "reports").mkdir(exist_ok=True)
        (data_dir / "metadata").mkdir(exist_ok=True)
        
        # Create logs directory
        log_dir = Path(logging_config.file).parent
        log_dir.mkdir(exist_ok=True)
        
        return Config(
            interest_topics=data['interest_topics'],
            websites=websites,
            llm_config=llm_config,
            storage=storage,
            logging=logging_config,
            filtering=filtering,
            reporting=reporting
        )
        
    except yaml.YAMLError as e:
        raise ConfigError(f"Error parsing YAML configuration: {e}")
    except Exception as e:
        raise ConfigError(f"Error loading configuration: {e}")


def validate_config(config: Config) -> None:
    """Validate configuration values."""
    # Validate interest topics
    if not config.interest_topics:
        raise ConfigError("At least one interest topic must be specified")
    
    # Validate websites
    enabled_websites = [name for name, cfg in config.websites.items() if cfg.enabled]
    if not enabled_websites:
        raise ConfigError("At least one website must be enabled")
    
    # Validate LLM configuration
    if config.llm_config.provider not in ['openai', 'anthropic']:
        raise ConfigError(f"Unsupported LLM provider: {config.llm_config.provider}")
    
    if config.llm_config.max_tokens <= 0:
        raise ConfigError("max_tokens must be positive")
    
    if not 0 <= config.llm_config.temperature <= 2:
        raise ConfigError("temperature must be between 0 and 2")
    
    # Validate filtering configuration
    if not 0 <= config.filtering.min_relevance_score <= 1:
        raise ConfigError("min_relevance_score must be between 0 and 1")
    
    if not 0 <= config.filtering.duplicate_threshold <= 1:
        raise ConfigError("duplicate_threshold must be between 0 and 1")