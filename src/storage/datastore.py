"""JSON-based data persistence for ainews."""

import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from ..models import Article, CrawlSession, ProcessedUrl, WeeklyReport
from ..logger import get_logger


class DataStoreError(Exception):
    """Data store related errors."""
    pass


class JSONDataStore:
    """JSON-based data storage with atomic operations and backup support."""
    
    def __init__(self, data_dir: str, backup_enabled: bool = True):
        self.data_dir = Path(data_dir)
        self.backup_enabled = backup_enabled
        self.logger = get_logger()
        
        # Ensure directories exist
        self.articles_dir = self.data_dir / "articles"
        self.reports_dir = self.data_dir / "reports"
        self.metadata_dir = self.data_dir / "metadata"
        
        for dir_path in [self.articles_dir, self.reports_dir, self.metadata_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def _atomic_write(self, file_path: Path):
        """Context manager for atomic file writes."""
        temp_path = file_path.with_suffix(file_path.suffix + '.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                yield f
            # Atomic move
            shutil.move(str(temp_path), str(file_path))
            self.logger.debug(f"Successfully wrote {file_path}")
        except Exception as e:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            self.logger.error(f"Failed to write {file_path}: {e}")
            raise DataStoreError(f"Failed to write {file_path}: {e}")
    
    def _backup_file(self, file_path: Path) -> None:
        """Create a backup of an existing file."""
        if not self.backup_enabled or not file_path.exists():
            return
            
        backup_path = file_path.with_suffix(f"{file_path.suffix}.backup")
        try:
            shutil.copy2(str(file_path), str(backup_path))
            self.logger.debug(f"Created backup: {backup_path}")
        except Exception as e:
            self.logger.warning(f"Failed to create backup for {file_path}: {e}")
    
    def save_daily_articles(self, articles: List[Article], date: str = None) -> None:
        """Save articles for a specific date."""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        file_path = self.articles_dir / f"{date}.json"
        self._backup_file(file_path)
        
        # Convert articles to dictionaries
        articles_data = [article.to_dict() for article in articles]
        
        with self._atomic_write(file_path):
            with open(file_path.with_suffix(file_path.suffix + '.tmp'), 'w', encoding='utf-8') as f:
                json.dump({
                    'date': date,
                    'count': len(articles),
                    'articles': articles_data,
                    'saved_at': datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Saved {len(articles)} articles for {date}")
    
    def load_daily_articles(self, date: str) -> List[Article]:
        """Load articles for a specific date."""
        file_path = self.articles_dir / f"{date}.json"
        
        if not file_path.exists():
            self.logger.debug(f"No articles found for date: {date}")
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            articles = [Article.from_dict(article_data) for article_data in data['articles']]
            self.logger.debug(f"Loaded {len(articles)} articles for {date}")
            return articles
            
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.error(f"Failed to load articles for {date}: {e}")
            raise DataStoreError(f"Corrupted data file for {date}: {e}")
        except Exception as e:
            self.logger.error(f"Error loading articles for {date}: {e}")
            raise DataStoreError(f"Failed to load articles for {date}: {e}")
    
    def get_articles_in_range(self, start_date: str, end_date: str) -> List[Article]:
        """Get all articles within a date range (inclusive)."""
        articles = []
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
        current = start
        
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            daily_articles = self.load_daily_articles(date_str)
            articles.extend(daily_articles)
            current += timedelta(days=1)
        
        self.logger.debug(f"Found {len(articles)} articles between {start_date} and {end_date}")
        return articles
    
    def save_crawl_session(self, session: CrawlSession) -> None:
        """Save crawl session metadata."""
        file_path = self.metadata_dir / "last_crawl.json"
        self._backup_file(file_path)
        
        with self._atomic_write(file_path):
            with open(file_path.with_suffix(file_path.suffix + '.tmp'), 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
        
        self.logger.debug(f"Saved crawl session: {session.session_id}")
    
    def load_last_crawl_session(self) -> Optional[CrawlSession]:
        """Load the last crawl session."""
        file_path = self.metadata_dir / "last_crawl.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return CrawlSession(**data)
        except Exception as e:
            self.logger.error(f"Failed to load last crawl session: {e}")
            return None
    
    def save_processed_urls(self, processed_urls: Dict[str, ProcessedUrl]) -> None:
        """Save processed URLs for duplicate detection."""
        file_path = self.metadata_dir / "processed_urls.json"
        self._backup_file(file_path)
        
        # Convert to serializable format
        urls_data = {url: processed_url.to_dict() 
                    for url, processed_url in processed_urls.items()}
        
        with self._atomic_write(file_path):
            with open(file_path.with_suffix(file_path.suffix + '.tmp'), 'w', encoding='utf-8') as f:
                json.dump({
                    'updated_at': datetime.now().isoformat(),
                    'count': len(urls_data),
                    'urls': urls_data
                }, f, indent=2, ensure_ascii=False)
        
        self.logger.debug(f"Saved {len(processed_urls)} processed URLs")
    
    def load_processed_urls(self) -> Dict[str, ProcessedUrl]:
        """Load processed URLs for duplicate detection."""
        file_path = self.metadata_dir / "processed_urls.json"
        
        if not file_path.exists():
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            processed_urls = {url: ProcessedUrl.from_dict(url_data) 
                            for url, url_data in data['urls'].items()}
            
            self.logger.debug(f"Loaded {len(processed_urls)} processed URLs")
            return processed_urls
            
        except Exception as e:
            self.logger.error(f"Failed to load processed URLs: {e}")
            return {}
    
    def save_weekly_report(self, report: WeeklyReport) -> None:
        """Save a weekly report."""
        week_start = datetime.fromisoformat(report.week_start).strftime('%Y-%m-%d')
        file_path = self.reports_dir / f"week-{week_start}.json"
        self._backup_file(file_path)
        
        with self._atomic_write(file_path):
            with open(file_path.with_suffix(file_path.suffix + '.tmp'), 'w', encoding='utf-8') as f:
                json.dump(report.to_dict(), f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Saved weekly report for week starting {week_start}")
    
    def cleanup_old_data(self, retention_days: int) -> None:
        """Clean up old data files based on retention policy."""
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        cutoff_str = cutoff_date.strftime('%Y-%m-%d')
        
        cleaned_files = 0
        
        # Clean up old article files
        for file_path in self.articles_dir.glob("*.json"):
            try:
                # Extract date from filename (format: YYYY-MM-DD.json)
                date_str = file_path.stem
                if date_str < cutoff_str:
                    file_path.unlink()
                    cleaned_files += 1
                    self.logger.debug(f"Deleted old article file: {file_path}")
            except Exception as e:
                self.logger.warning(f"Failed to clean up {file_path}: {e}")
        
        # Clean up old report files
        for file_path in self.reports_dir.glob("week-*.json"):
            try:
                # Extract date from filename (format: week-YYYY-MM-DD.json)
                date_part = file_path.stem.replace('week-', '')
                if date_part < cutoff_str:
                    file_path.unlink()
                    cleaned_files += 1
                    self.logger.debug(f"Deleted old report file: {file_path}")
            except Exception as e:
                self.logger.warning(f"Failed to clean up {file_path}: {e}")
        
        if cleaned_files > 0:
            self.logger.info(f"Cleaned up {cleaned_files} old data files")
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        stats = {
            'articles': len(list(self.articles_dir.glob("*.json"))),
            'reports': len(list(self.reports_dir.glob("*.json"))),
            'metadata_files': len(list(self.metadata_dir.glob("*.json"))),
            'total_size_mb': 0
        }
        
        # Calculate total size
        total_size = 0
        for path in self.data_dir.rglob("*.json"):
            try:
                total_size += path.stat().st_size
            except OSError:
                pass
        
        stats['total_size_mb'] = round(total_size / (1024 * 1024), 2)
        return stats