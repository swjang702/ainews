"""Duplicate detection system for articles."""

import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher

from ..models import Article, ProcessedUrl
from ..logger import get_logger


class DuplicateDetector:
    """Handles duplicate detection using content hashing and similarity matching."""
    
    def __init__(self, duplicate_threshold: float = 0.9):
        self.duplicate_threshold = duplicate_threshold
        self.processed_urls: Dict[str, ProcessedUrl] = {}
        self.logger = get_logger()
    
    def load_processed_urls(self, processed_urls: Dict[str, ProcessedUrl]) -> None:
        """Load previously processed URLs."""
        self.processed_urls = processed_urls
        self.logger.debug(f"Loaded {len(processed_urls)} processed URLs for duplicate detection")
    
    def is_url_processed(self, url: str) -> bool:
        """Check if a URL has been processed before."""
        return url in self.processed_urls
    
    def mark_url_processed(self, url: str, content_hash: str) -> None:
        """Mark a URL as processed."""
        if url in self.processed_urls:
            self.processed_urls[url].update_seen(content_hash)
        else:
            self.processed_urls[url] = ProcessedUrl.create(url, content_hash)
    
    def generate_content_hash(self, content: str) -> str:
        """Generate a hash for content."""
        # Normalize content for better duplicate detection
        normalized = self._normalize_content(content)
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
    
    def _normalize_content(self, content: str) -> str:
        """Normalize content for consistent hashing."""
        # Remove extra whitespace, convert to lowercase
        normalized = ' '.join(content.lower().split())
        
        # Remove common punctuation that might vary
        for char in '.,!?;:"()[]{}':
            normalized = normalized.replace(char, '')
        
        return normalized
    
    def find_duplicates_in_batch(self, articles: List[Article]) -> Tuple[List[Article], List[Article]]:
        """Find duplicates within a batch of articles and against existing ones."""
        unique_articles = []
        duplicate_articles = []
        seen_hashes = set()
        
        for article in articles:
            is_duplicate = False
            
            # Check against existing processed URLs
            if self.is_url_processed(article.url):
                existing_url = self.processed_urls[article.url]
                if self._is_content_similar(existing_url.content_hash, article.content_hash):
                    is_duplicate = True
                    self.logger.debug(f"Found duplicate by URL: {article.url}")
            
            # Check for content duplicates within the current batch
            if not is_duplicate:
                for seen_hash in seen_hashes:
                    if self._is_hash_similar(seen_hash, article.content_hash):
                        is_duplicate = True
                        self.logger.debug(f"Found duplicate by content hash: {article.title}")
                        break
            
            # Check for title similarity (catch near-duplicates)
            if not is_duplicate:
                for unique_article in unique_articles:
                    if self._are_titles_similar(article.title, unique_article.title):
                        is_duplicate = True
                        self.logger.debug(f"Found duplicate by title similarity: {article.title}")
                        break
            
            if is_duplicate:
                duplicate_articles.append(article)
            else:
                unique_articles.append(article)
                seen_hashes.add(article.content_hash)
                self.mark_url_processed(article.url, article.content_hash)
        
        self.logger.info(f"Filtered {len(duplicate_articles)} duplicates from {len(articles)} articles")
        return unique_articles, duplicate_articles
    
    def _is_content_similar(self, hash1: str, hash2: str) -> bool:
        """Check if two content hashes are similar enough to be considered duplicates."""
        return hash1 == hash2
    
    def _is_hash_similar(self, hash1: str, hash2: str) -> bool:
        """Check if two hashes are similar (exact match for now)."""
        return hash1 == hash2
    
    def _are_titles_similar(self, title1: str, title2: str) -> bool:
        """Check if two titles are similar enough to be considered duplicates."""
        # Normalize titles
        norm_title1 = self._normalize_title(title1)
        norm_title2 = self._normalize_title(title2)
        
        # Calculate similarity ratio
        similarity = SequenceMatcher(None, norm_title1, norm_title2).ratio()
        
        return similarity >= self.duplicate_threshold
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        # Remove common variations
        normalized = title.lower().strip()
        
        # Remove common prefixes/suffixes that don't affect content
        prefixes_to_remove = ['ask hn:', 'show hn:', 'tell hn:', 'hn:']
        for prefix in prefixes_to_remove:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):].strip()
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def find_similar_articles(self, article: Article, existing_articles: List[Article]) -> List[Article]:
        """Find articles similar to the given article."""
        similar = []
        
        for existing in existing_articles:
            # Check title similarity
            if self._are_titles_similar(article.title, existing.title):
                similar.append(existing)
                continue
            
            # Check content hash similarity
            if article.content_hash == existing.content_hash:
                similar.append(existing)
                continue
            
            # Check if they're from the same URL
            if article.url == existing.url:
                similar.append(existing)
        
        return similar
    
    def get_duplicate_stats(self) -> Dict[str, int]:
        """Get statistics about duplicate detection."""
        return {
            'total_processed_urls': len(self.processed_urls),
            'multi_processed_urls': len([url for url in self.processed_urls.values() 
                                       if url.process_count > 1])
        }
    
    def cleanup_old_urls(self, days: int = 30) -> int:
        """Remove old processed URLs to keep memory usage reasonable."""
        cutoff_date = datetime.now().isoformat()
        cutoff_timestamp = (datetime.now() - 
                          timedelta(days=days)).isoformat()
        
        old_urls = []
        for url, processed_url in self.processed_urls.items():
            if processed_url.last_seen < cutoff_timestamp:
                old_urls.append(url)
        
        for url in old_urls:
            del self.processed_urls[url]
        
        self.logger.info(f"Cleaned up {len(old_urls)} old processed URLs")
        return len(old_urls)
    
    def get_processed_urls(self) -> Dict[str, ProcessedUrl]:
        """Get the current processed URLs dictionary."""
        return self.processed_urls.copy()