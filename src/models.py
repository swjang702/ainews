"""Data models for ainews."""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
import hashlib
import json


@dataclass
class Article:
    """Article data model."""
    id: str
    title: str
    url: str
    source: str
    discovered_date: str
    content_hash: str
    summary: str
    related_topics: List[str]
    relevance_score: float
    raw_content: Optional[str] = None
    processed_at: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        title: str,
        url: str,
        source: str,
        raw_content: str = "",
        summary: str = "",
        related_topics: List[str] = None,
        relevance_score: float = 0.0
    ) -> 'Article':
        """Create a new article with auto-generated fields."""
        now = datetime.now().isoformat()
        content_hash = cls._generate_content_hash(raw_content or title)
        url_hash = cls._generate_url_hash(url)
        
        return cls(
            id=url_hash,
            title=title,
            url=url,
            source=source,
            discovered_date=now,
            content_hash=content_hash,
            summary=summary,
            related_topics=related_topics or [],
            relevance_score=relevance_score,
            raw_content=raw_content,
            processed_at=now
        )
    
    @staticmethod
    def _generate_url_hash(url: str) -> str:
        """Generate a unique ID from URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]
    
    @staticmethod
    def _generate_content_hash(content: str) -> str:
        """Generate a content hash for duplicate detection."""
        # Normalize content for hashing
        normalized = content.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert article to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Article':
        """Create article from dictionary."""
        return cls(**data)


@dataclass
class CrawlSession:
    """Represents a crawling session."""
    session_id: str
    start_time: str
    end_time: Optional[str]
    websites_crawled: List[str]
    articles_found: int
    articles_processed: int
    errors: List[str]
    
    @classmethod
    def create(cls, websites: List[str]) -> 'CrawlSession':
        """Create a new crawl session."""
        now = datetime.now().isoformat()
        session_id = hashlib.sha256(now.encode()).hexdigest()[:12]
        
        return cls(
            session_id=session_id,
            start_time=now,
            end_time=None,
            websites_crawled=websites,
            articles_found=0,
            articles_processed=0,
            errors=[]
        )
    
    def complete(self) -> None:
        """Mark the session as completed."""
        self.end_time = datetime.now().isoformat()
    
    def add_error(self, error: str) -> None:
        """Add an error to the session."""
        self.errors.append(f"{datetime.now().isoformat()}: {error}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary."""
        return asdict(self)


@dataclass
class ProcessedUrl:
    """Tracks processed URLs to prevent duplicates."""
    url: str
    first_seen: str
    last_seen: str
    process_count: int
    content_hash: str
    
    @classmethod
    def create(cls, url: str, content_hash: str) -> 'ProcessedUrl':
        """Create a new processed URL record."""
        now = datetime.now().isoformat()
        return cls(
            url=url,
            first_seen=now,
            last_seen=now,
            process_count=1,
            content_hash=content_hash
        )
    
    def update_seen(self, content_hash: str) -> None:
        """Update the last seen timestamp and increment count."""
        self.last_seen = datetime.now().isoformat()
        self.process_count += 1
        self.content_hash = content_hash
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProcessedUrl':
        """Create from dictionary."""
        return cls(**data)


@dataclass
class WeeklyReport:
    """Weekly report data model."""
    week_start: str
    week_end: str
    total_articles: int
    articles_by_topic: Dict[str, int]
    top_articles: List[Article]
    summary: str
    generated_at: str
    
    @classmethod
    def create(
        cls,
        week_start: str,
        week_end: str,
        articles: List[Article],
        summary: str = ""
    ) -> 'WeeklyReport':
        """Create a new weekly report."""
        # Count articles by topic
        topic_counts: Dict[str, int] = {}
        for article in articles:
            for topic in article.related_topics:
                topic_counts[topic] = topic_counts.get(topic, 0) + 1
        
        # Sort articles by relevance score and take top ones
        top_articles = sorted(articles, key=lambda a: a.relevance_score, reverse=True)[:20]
        
        return cls(
            week_start=week_start,
            week_end=week_end,
            total_articles=len(articles),
            articles_by_topic=topic_counts,
            top_articles=top_articles,
            summary=summary,
            generated_at=datetime.now().isoformat()
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        data = asdict(self)
        # Convert top_articles to dicts
        data['top_articles'] = [article.to_dict() for article in self.top_articles]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WeeklyReport':
        """Create report from dictionary."""
        # Convert top_articles back to Article objects
        if 'top_articles' in data:
            data['top_articles'] = [Article.from_dict(a) for a in data['top_articles']]
        return cls(**data)