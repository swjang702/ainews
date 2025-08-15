#!/usr/bin/env python3
"""Daily crawling script for ainews."""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import datetime
from src.config import load_config, validate_config, ConfigError
from src.logger import setup_logging, get_logger
from src.crawler import WebCrawler
from src.filters.topic_filter import TopicFilter
from src.filters.relevance import RelevanceScorer
from src.summarizer.content_processor import ContentProcessor
from src.storage.datastore import JSONDataStore
from src.storage.duplicate_detector import DuplicateDetector
from src.models import CrawlSession


def main():
    """Main daily crawling function."""
    try:
        # Load configuration
        config = load_config()
        validate_config(config)
        
        # Setup logging
        logger = setup_logging(config.logging)
        logger.info("Starting daily crawl process")
        
        # Initialize components
        datastore = JSONDataStore(
            config.storage.data_dir,
            config.storage.backup_enabled
        )
        
        duplicate_detector = DuplicateDetector(config.filtering.duplicate_threshold)
        processed_urls = datastore.load_processed_urls()
        duplicate_detector.load_processed_urls(processed_urls)
        
        content_processor = ContentProcessor(config.llm_config)
        topic_filter = TopicFilter(config.interest_topics, config.filtering.min_relevance_score)
        relevance_scorer = RelevanceScorer(config.interest_topics)
        
        crawler = WebCrawler(config.websites)
        
        # Create crawl session
        enabled_websites = [name for name, cfg in config.websites.items() if cfg.enabled]
        session = CrawlSession.create(enabled_websites)
        
        logger.info(f"Crawling {len(enabled_websites)} websites: {enabled_websites}")
        
        # Crawl articles
        raw_articles = crawler.crawl_all(config.websites)
        session.articles_found = len(raw_articles)
        logger.info(f"Found {len(raw_articles)} raw articles")
        
        if not raw_articles:
            logger.warning("No articles found during crawling")
            session.complete()
            datastore.save_crawl_session(session)
            return
        
        # Remove duplicates
        unique_articles, duplicates = duplicate_detector.find_duplicates_in_batch(raw_articles)
        logger.info(f"Filtered {len(duplicates)} duplicates, {len(unique_articles)} unique articles")
        
        # Filter by topics
        relevant_articles = topic_filter.filter_articles(unique_articles)
        logger.info(f"Found {len(relevant_articles)} topic-relevant articles")
        
        if not relevant_articles:
            logger.warning("No relevant articles found after topic filtering")
            session.complete()
            datastore.save_crawl_session(session)
            return
        
        # Apply relevance scoring
        scored_articles = relevance_scorer.score_articles_batch(relevant_articles)
        
        # Apply minimum relevance threshold
        final_articles = [
            article for article in scored_articles 
            if article.relevance_score >= config.filtering.min_relevance_score
        ]
        
        logger.info(f"Final selection: {len(final_articles)} articles after relevance filtering")
        
        # Limit articles per day if configured
        if len(final_articles) > config.filtering.max_articles_per_day:
            final_articles = final_articles[:config.filtering.max_articles_per_day]
            logger.info(f"Limited to {len(final_articles)} articles per day limit")
        
        # Generate summaries
        if final_articles:
            final_articles = content_processor.process_articles(final_articles)
            session.articles_processed = len(final_articles)
            
            # Save articles
            today = datetime.now().strftime('%Y-%m-%d')
            datastore.save_daily_articles(final_articles, today)
            
            # Save updated processed URLs
            datastore.save_processed_urls(duplicate_detector.get_processed_urls())
            
            # Print summary statistics
            stats = content_processor.get_processing_stats(final_articles)
            logger.info(f"Processing statistics: {stats}")
            
            # Print topic statistics
            topic_stats = topic_filter.get_topic_statistics(final_articles)
            logger.info(f"Topic distribution: {topic_stats['most_common_topics']}")
        
        # Complete session
        session.complete()
        datastore.save_crawl_session(session)
        
        # Cleanup old data if configured
        if config.storage.retention_days > 0:
            datastore.cleanup_old_data(config.storage.retention_days)
        
        logger.info("Daily crawl completed successfully")
        
        # Print final summary
        print(f"\n=== Daily Crawl Summary ===")
        print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Articles found: {session.articles_found}")
        print(f"Articles processed: {session.articles_processed}")
        print(f"Duplicates removed: {len(duplicates) if 'duplicates' in locals() else 0}")
        print(f"Final articles saved: {len(final_articles) if 'final_articles' in locals() else 0}")
        
        if 'final_articles' in locals() and final_articles:
            print(f"\nTop 3 articles by relevance:")
            for i, article in enumerate(final_articles[:3], 1):
                print(f"{i}. {article.title} (score: {article.relevance_score:.3f})")
        
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCrawl interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if 'logger' in locals():
            logger.error(f"Unexpected error during crawl: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()