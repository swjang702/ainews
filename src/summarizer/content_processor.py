"""Content processing and summarization coordination."""

import re
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from ..models import Article
from ..config import LLMConfig
from .llm_client import LLMClientFactory, BaseLLMClient, LLMError
from ..logger import get_logger


class ContentProcessor:
    """Processes article content and coordinates summarization."""
    
    def __init__(self, llm_config: LLMConfig, max_workers: int = 3):
        self.llm_config = llm_config
        self.max_workers = max_workers
        self.logger = get_logger()
        
        # Initialize LLM client
        try:
            self.llm_client = LLMClientFactory.create_client(llm_config)
        except Exception as e:
            self.logger.error(f"Failed to initialize LLM client: {e}")
            raise
    
    def process_articles(self, articles: List[Article]) -> List[Article]:
        """Process and summarize a batch of articles."""
        self.logger.info(f"Processing {len(articles)} articles for summarization")
        
        # Filter articles that need processing
        articles_to_process = [article for article in articles if not article.summary.strip()]
        articles_already_processed = [article for article in articles if article.summary.strip()]
        
        if not articles_to_process:
            self.logger.info("All articles already have summaries")
            return articles
        
        self.logger.info(f"Generating summaries for {len(articles_to_process)} articles")
        
        # Process articles in parallel with rate limiting
        processed_articles = self._process_articles_parallel(articles_to_process)
        
        # Combine processed and already processed articles
        all_articles = processed_articles + articles_already_processed
        
        self.logger.info(f"Successfully processed {len(processed_articles)} new summaries")
        return all_articles
    
    def _process_articles_parallel(self, articles: List[Article]) -> List[Article]:
        """Process articles in parallel with proper rate limiting."""
        processed_articles = []
        failed_articles = []
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_article = {
                executor.submit(self._process_single_article, article): article
                for article in articles
            }
            
            # Process completed tasks
            for future in as_completed(future_to_article):
                article = future_to_article[future]
                
                try:
                    processed_article = future.result()
                    processed_articles.append(processed_article)
                    
                    # Rate limiting between requests
                    time.sleep(self.llm_config.rate_limit_delay)
                    
                except Exception as e:
                    self.logger.error(f"Failed to process article '{article.title[:50]}...': {e}")
                    failed_articles.append(article)
        
        # Add failed articles with empty summaries
        for article in failed_articles:
            article.summary = "Summary generation failed"
            processed_articles.append(article)
        
        return processed_articles
    
    def _process_single_article(self, article: Article) -> Article:
        """Process a single article."""
        try:
            # Prepare content for summarization
            prepared_content = self._prepare_content(article)
            
            # Generate context for better summarization
            context = self._generate_context(article)
            
            # Generate summary
            summary = self.llm_client.generate_summary(prepared_content, context)
            
            # Post-process summary
            processed_summary = self._post_process_summary(summary)
            
            # Update article
            article.summary = processed_summary
            
            self.logger.debug(f"Generated summary for: {article.title[:50]}...")
            return article
            
        except LLMError as e:
            self.logger.error(f"LLM error for article '{article.title[:30]}...': {e}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error processing article '{article.title[:30]}...': {e}")
            raise
    
    def _prepare_content(self, article: Article) -> str:
        """Prepare article content for summarization."""
        # Combine title and content
        content_parts = [article.title]
        
        if article.raw_content:
            # Clean and truncate content
            cleaned_content = self._clean_content(article.raw_content)
            content_parts.append(cleaned_content)
        
        # Join parts
        full_content = "\n\n".join(content_parts)
        
        # Truncate to reasonable length for LLM processing
        max_length = 3000  # Approximate token limit
        if len(full_content) > max_length:
            full_content = full_content[:max_length] + "..."
        
        return full_content
    
    def _clean_content(self, content: str) -> str:
        """Clean raw content for better processing."""
        if not content:
            return ""
        
        # Remove excessive whitespace
        content = re.sub(r'\s+', ' ', content)
        
        # Remove HTML-like tags if any
        content = re.sub(r'<[^>]+>', '', content)
        
        # Remove URLs (keep the content more focused)
        content = re.sub(r'http[s]?://\S+', '[URL]', content)
        
        # Remove email addresses
        content = re.sub(r'\S+@\S+', '[EMAIL]', content)
        
        # Clean up punctuation spacing
        content = re.sub(r'\s+([,.!?;:])', r'\1', content)
        
        return content.strip()
    
    def _generate_context(self, article: Article) -> str:
        """Generate context information for better summarization."""
        context_parts = []
        
        # Source context
        source_contexts = {
            'hackernews': 'This is from Hacker News, a tech community discussion platform',
            'lwn': 'This is from LWN.net, a Linux and open-source news publication',
            'github': 'This is from GitHub, likely related to code repositories',
            'arxiv': 'This is from arXiv, an academic preprint repository'
        }
        
        if article.source in source_contexts:
            context_parts.append(source_contexts[article.source])
        
        # Topic context
        if article.related_topics:
            topics_str = ', '.join(article.related_topics)
            context_parts.append(f"Related topics: {topics_str}")
        
        return '. '.join(context_parts)
    
    def _post_process_summary(self, summary: str) -> str:
        """Post-process the generated summary."""
        if not summary:
            return "No summary available"
        
        # Clean up the summary
        summary = summary.strip()
        
        # Remove common prefixes that LLMs might add
        prefixes_to_remove = [
            'Summary: ',
            'Article Summary: ',
            'This article ',
            'The article ',
            'In summary, '
        ]
        
        for prefix in prefixes_to_remove:
            if summary.startswith(prefix):
                summary = summary[len(prefix):]
                break
        
        # Ensure summary ends with proper punctuation
        if summary and not summary[-1] in '.!?':
            summary += '.'
        
        # Limit summary length
        max_summary_length = 500
        if len(summary) > max_summary_length:
            # Try to cut at sentence boundary
            sentences = summary.split('. ')
            truncated = ''
            for sentence in sentences:
                if len(truncated + sentence + '. ') <= max_summary_length:
                    truncated += sentence + '. '
                else:
                    break
            
            if truncated:
                summary = truncated.rstrip()
            else:
                summary = summary[:max_summary_length] + '...'
        
        return summary
    
    def generate_batch_summary(self, articles: List[Article]) -> str:
        """Generate a summary of multiple articles."""
        if not articles:
            return "No articles to summarize"
        
        # Prepare combined content
        articles_content = []
        for i, article in enumerate(articles[:20], 1):  # Limit to top 20 articles
            article_summary = f"{i}. {article.title}"
            if article.summary:
                article_summary += f": {str(article.summary)}"
            articles_content.append(article_summary)
        
        combined_content = "\n".join(articles_content)
        
        try:
            # Generate weekly summary
            weekly_summary = self.llm_client.generate_weekly_summary(combined_content)
            return weekly_summary
        except Exception as e:
            self.logger.error(f"Failed to generate batch summary: {e}")
            return f"Failed to generate summary: {e}"
    
    def get_processing_stats(self, articles: List[Article]) -> Dict[str, Any]:
        """Get statistics about content processing."""
        total_articles = len(articles)
        articles_with_summaries = len([a for a in articles if a.summary and a.summary != "Summary generation failed"])
        articles_failed = len([a for a in articles if a.summary == "Summary generation failed"])
        
        if articles_with_summaries > 0:
            avg_summary_length = sum(len(a.summary) for a in articles if a.summary) / articles_with_summaries
        else:
            avg_summary_length = 0
        
        return {
            'total_articles': total_articles,
            'articles_with_summaries': articles_with_summaries,
            'articles_failed': articles_failed,
            'success_rate': articles_with_summaries / total_articles if total_articles > 0 else 0,
            'avg_summary_length': round(avg_summary_length, 1)
        }
    
    def retry_failed_summaries(self, articles: List[Article]) -> List[Article]:
        """Retry generating summaries for failed articles."""
        failed_articles = [a for a in articles if a.summary == "Summary generation failed"]
        
        if not failed_articles:
            self.logger.info("No failed summaries to retry")
            return articles
        
        self.logger.info(f"Retrying {len(failed_articles)} failed summaries")
        
        # Clear failed summaries and reprocess
        for article in failed_articles:
            article.summary = ""
        
        # Process failed articles
        reprocessed = self._process_articles_parallel(failed_articles)
        
        # Update the articles list
        article_dict = {a.id: a for a in articles}
        for article in reprocessed:
            article_dict[article.id] = article
        
        return list(article_dict.values())