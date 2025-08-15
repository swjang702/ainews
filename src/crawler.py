"""Web crawler for HackerNews and LWN.net."""

import time
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
import re
from datetime import datetime

from .models import Article
from .logger import get_logger


class CrawlerError(Exception):
    """Crawler related errors."""
    pass


class BaseCrawler:
    """Base crawler class with common functionality."""
    
    def __init__(self, delay_between_requests: float = 1.0):
        self.delay = delay_between_requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'ainews/1.0 (Educational AI News Curator)'
        })
        self.logger = get_logger()
    
    def _make_request(self, url: str, timeout: int = 30) -> requests.Response:
        """Make HTTP request with error handling."""
        try:
            self.logger.debug(f"Fetching: {url}")
            
            # Check for common invalid URLs
            if not url or not url.startswith(('http://', 'https://')):
                raise CrawlerError(f"Invalid URL format: {url}")
            
            response = self.session.get(url, timeout=timeout, allow_redirects=True)
            
            # Check response size to avoid downloading huge files
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB limit
                raise CrawlerError(f"Content too large: {content_length} bytes")
            
            # Check content type to avoid downloading non-text content
            content_type = response.headers.get('content-type', '').lower()
            if content_type and not any(ct in content_type for ct in ['text/', 'application/json', 'application/xml']):
                if not any(ct in content_type for ct in ['html', 'xml', 'json', 'text']):
                    raise CrawlerError(f"Non-text content type: {content_type}")
            
            response.raise_for_status()
            return response
            
        except requests.exceptions.Timeout:
            self.logger.warning(f"Request timeout for {url}")
            raise CrawlerError(f"Timeout fetching {url}")
        except requests.exceptions.ConnectionError:
            self.logger.warning(f"Connection error for {url}")
            raise CrawlerError(f"Connection failed for {url}")
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else 0
            self.logger.warning(f"HTTP {status_code} error for {url}")
            raise CrawlerError(f"HTTP {status_code} error for {url}")
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed for {url}: {e}")
            raise CrawlerError(f"Failed to fetch {url}: {e}")
    
    def _parse_html(self, html_content: str) -> BeautifulSoup:
        """Parse HTML content."""
        return BeautifulSoup(html_content, 'html.parser')
    
    def _extract_text_content(self, element) -> str:
        """Extract clean text content from HTML element."""
        if element is None:
            return ""
        return ' '.join(element.get_text().split())
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid."""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False


class HackerNewsCrawler(BaseCrawler):
    """Crawler for Hacker News."""
    
    BASE_URL = "https://news.ycombinator.com"
    
    def __init__(self, delay_between_requests: float = 1.0):
        super().__init__(delay_between_requests)
    
    def crawl(self, max_pages: int = 3) -> List[Article]:
        """Crawl Hacker News for articles."""
        articles = []
        
        for page in range(1, max_pages + 1):
            try:
                page_articles = self._crawl_page(page)
                articles.extend(page_articles)
                
                if page < max_pages:
                    time.sleep(self.delay)
                    
            except CrawlerError as e:
                self.logger.error(f"Failed to crawl HN page {page}: {e}")
                continue
        
        self.logger.info(f"Crawled {len(articles)} articles from HackerNews")
        return articles
    
    def _crawl_page(self, page: int = 1) -> List[Article]:
        """Crawl a specific page of Hacker News."""
        if page == 1:
            url = f"{self.BASE_URL}/news"
        else:
            url = f"{self.BASE_URL}/news?p={page}"
        
        response = self._make_request(url)
        soup = self._parse_html(response.text)
        
        articles = []
        
        # Find all story rows
        story_rows = soup.find_all('tr', class_='athing')
        
        for story_row in story_rows:
            try:
                article = self._extract_article_from_row(story_row)
                if article:
                    articles.append(article)
            except Exception as e:
                self.logger.warning(f"Failed to extract HN article: {e}")
                continue
        
        return articles
    
    def _extract_article_from_row(self, row) -> Optional[Article]:
        """Extract article information from a story row."""
        try:
            # Find the title link
            title_link = row.find('span', class_='titleline').find('a')
            if not title_link:
                return None
            
            title = self._extract_text_content(title_link)
            url = title_link.get('href', '')
            
            # Handle relative URLs
            if url.startswith('item?'):
                url = urljoin(self.BASE_URL, url)
            elif not self._is_valid_url(url):
                return None
            
            # Get additional metadata from the next row
            meta_row = row.find_next_sibling('tr')
            if meta_row:
                meta_data = self._extract_metadata(meta_row)
            else:
                meta_data = {}
            
            # Fetch actual article content from the URL
            article_content = self._fetch_article_content(url)
            
            # If we couldn't fetch content, fall back to metadata
            if not article_content:
                article_content = f"{title}\n{meta_data.get('subtext', '')}"
            
            # Create article
            article = Article.create(
                title=title,
                url=url,
                source="hackernews",
                raw_content=article_content
            )
            
            return article
            
        except Exception as e:
            self.logger.warning(f"Error extracting HN article: {e}")
            return None
    
    def _extract_metadata(self, meta_row) -> Dict[str, Any]:
        """Extract metadata from the subtext row."""
        metadata = {}
        
        subtext = meta_row.find('td', class_='subtext')
        if subtext:
            metadata['subtext'] = self._extract_text_content(subtext)
            
            # Extract score
            score_span = subtext.find('span', class_='score')
            if score_span:
                score_text = score_span.get_text()
                metadata['score'] = int(re.findall(r'\d+', score_text)[0]) if re.findall(r'\d+', score_text) else 0
            
            # Extract comment count
            comments_link = subtext.find('a', href=re.compile(r'item\?id='))
            if comments_link and 'comment' in comments_link.get_text():
                comments_text = comments_link.get_text()
                comment_count = re.findall(r'\d+', comments_text)
                metadata['comments'] = int(comment_count[0]) if comment_count else 0
        
        return metadata
    
    def _fetch_article_content(self, url: str) -> str:
        """Fetch actual article content from the URL."""
        try:
            # Skip HackerNews internal URLs
            if url.startswith(self.BASE_URL):
                self.logger.debug(f"Skipping internal HN URL: {url}")
                return ""
            
            self.logger.debug(f"Fetching article content from: {url}")
            
            # Add a small delay to be respectful
            time.sleep(0.5)
            
            # Make request with shorter timeout for individual articles
            response = self._make_request(url, timeout=15)
            soup = self._parse_html(response.text)
            
            # Extract content using common patterns
            content = self._extract_article_text(soup)
            
            # Limit content size to avoid overwhelming the system
            if content and len(content) > 5000:
                content = content[:5000] + "..."
            
            return content
            
        except CrawlerError as e:
            self.logger.warning(f"Failed to fetch content from {url}: {e}")
            return ""
        except Exception as e:
            self.logger.warning(f"Unexpected error fetching content from {url}: {e}")
            return ""
    
    def _extract_article_text(self, soup: BeautifulSoup) -> str:
        """Extract article text from various common HTML structures."""
        # Common article content selectors (in order of preference)
        content_selectors = [
            'article',
            '[role="main"]',
            '.post-content',
            '.entry-content', 
            '.article-content',
            '.content',
            '.post-body',
            '.article-body',
            'main',
            '.container'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # Remove script and style elements
                for script in content_elem.find_all(['script', 'style', 'nav', 'header', 'footer']):
                    script.decompose()
                
                # Extract text content
                text = self._extract_text_content(content_elem)
                if text and len(text.strip()) > 100:  # Minimum content threshold
                    return text.strip()
        
        # Fallback: try to get text from body
        body = soup.find('body')
        if body:
            # Remove common non-content elements
            for elem in body.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                elem.decompose()
            
            text = self._extract_text_content(body)
            if text and len(text.strip()) > 100:
                return text.strip()
        
        return ""


class LWNCrawler(BaseCrawler):
    """Crawler for LWN.net."""
    
    BASE_URL = "https://lwn.net"
    
    def __init__(self, delay_between_requests: float = 2.0):
        super().__init__(delay_between_requests)
    
    def crawl(self, max_articles: int = 50) -> List[Article]:
        """Crawl LWN.net for articles."""
        articles = []
        
        try:
            # Crawl the main archives page
            archive_articles = self._crawl_archives()
            articles.extend(archive_articles[:max_articles])
            
        except CrawlerError as e:
            self.logger.error(f"Failed to crawl LWN archives: {e}")
        
        self.logger.info(f"Crawled {len(articles)} articles from LWN.net")
        return articles
    
    def _crawl_archives(self) -> List[Article]:
        """Crawl the LWN archives page."""
        url = f"{self.BASE_URL}/Archives/"
        response = self._make_request(url)
        soup = self._parse_html(response.text)
        
        articles = []
        
        # Find article links in the archives
        # LWN has a specific structure for archive listings
        article_links = soup.find_all('a', href=re.compile(r'/Articles/\d+/'))
        
        for link in article_links:
            try:
                time.sleep(self.delay)  # Be respectful to LWN
                article = self._extract_article_from_link(link)
                if article:
                    articles.append(article)
            except Exception as e:
                self.logger.warning(f"Failed to extract LWN article: {e}")
                continue
        
        return articles
    
    def _extract_article_from_link(self, link) -> Optional[Article]:
        """Extract article from an archive link."""
        try:
            title = self._extract_text_content(link)
            url = urljoin(self.BASE_URL, link.get('href', ''))
            
            if not title or not self._is_valid_url(url):
                return None
            
            # Try to get article content (only if it's freely available)
            content = self._get_article_content(url)
            
            article = Article.create(
                title=title,
                url=url,
                source="lwn",
                raw_content=content
            )
            
            return article
            
        except Exception as e:
            self.logger.warning(f"Error extracting LWN article: {e}")
            return None
    
    def _get_article_content(self, url: str) -> str:
        """Get article content if freely available."""
        try:
            response = self._make_request(url)
            soup = self._parse_html(response.text)
            
            # Check if article is subscription-only
            if soup.find('div', class_='FeatureByline'):
                # This might be a subscriber-only article
                byline = soup.find('div', class_='FeatureByline')
                if byline and 'subscriber' in byline.get_text().lower():
                    self.logger.debug(f"Skipping subscriber-only article: {url}")
                    return ""
            
            # Extract article content
            content_div = soup.find('div', class_='ArticleText') or soup.find('div', class_='FeatureText')
            if content_div:
                content = self._extract_text_content(content_div)
                return content[:1000]  # Limit content length
            
            return ""
            
        except Exception as e:
            self.logger.warning(f"Failed to get LWN article content for {url}: {e}")
            return ""


class WebCrawler:
    """Main crawler that coordinates different website crawlers."""
    
    def __init__(self, website_configs: Dict[str, Any]):
        self.crawlers = {}
        self.logger = get_logger()
        
        # Initialize crawlers based on configuration
        for name, config in website_configs.items():
            if not config.enabled:
                continue
                
            if name == 'hackernews':
                self.crawlers[name] = HackerNewsCrawler(config.delay_between_requests)
            elif name == 'lwn':
                self.crawlers[name] = LWNCrawler(config.delay_between_requests)
            else:
                self.logger.warning(f"Unknown crawler type: {name}")
    
    def crawl_all(self, website_configs: Dict[str, Any]) -> List[Article]:
        """Crawl all enabled websites."""
        all_articles = []
        
        for name, crawler in self.crawlers.items():
            if name not in website_configs or not website_configs[name].enabled:
                continue
                
            try:
                config = website_configs[name]
                
                if name == 'hackernews':
                    articles = crawler.crawl(max_pages=config.max_pages)
                elif name == 'lwn':
                    articles = crawler.crawl(max_articles=config.max_articles)
                else:
                    continue
                
                all_articles.extend(articles)
                self.logger.info(f"Successfully crawled {len(articles)} articles from {name}")
                
            except Exception as e:
                self.logger.error(f"Failed to crawl {name}: {e}")
                continue
        
        self.logger.info(f"Total articles crawled: {len(all_articles)}")
        return all_articles
    
    def crawl_website(self, website_name: str, config: Any) -> List[Article]:
        """Crawl a specific website."""
        if website_name not in self.crawlers:
            raise CrawlerError(f"No crawler available for {website_name}")
        
        crawler = self.crawlers[website_name]
        
        if website_name == 'hackernews':
            return crawler.crawl(max_pages=config.max_pages)
        elif website_name == 'lwn':
            return crawler.crawl(max_articles=config.max_articles)
        else:
            raise CrawlerError(f"Unknown website configuration for {website_name}")