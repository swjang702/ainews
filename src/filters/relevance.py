"""Advanced relevance scoring algorithms for articles."""

import re
import math
from typing import List, Dict, Any, Set, Tuple
from collections import Counter
from datetime import datetime, timedelta

from ..models import Article
from ..logger import get_logger


class RelevanceScorer:
    """Advanced relevance scoring using multiple algorithms."""
    
    def __init__(self, interest_topics: List[str]):
        self.interest_topics = interest_topics
        self.logger = get_logger()
        
        # Build topic vocabulary
        self.topic_vocabulary = self._build_topic_vocabulary()
        
        # TF-IDF related
        self.document_frequencies = {}
        self.total_documents = 0
    
    def _build_topic_vocabulary(self) -> Set[str]:
        """Build vocabulary from interest topics."""
        vocabulary = set()
        
        for topic in self.interest_topics:
            # Extract words from topic
            words = re.findall(r'\b\w+\b', topic.lower())
            vocabulary.update(words)
        
        return vocabulary
    
    def calculate_comprehensive_score(self, article: Article, all_articles: List[Article] = None) -> float:
        """Calculate comprehensive relevance score using multiple factors."""
        scores = {}
        
        # Topic relevance score (0.4 weight)
        scores['topic'] = self._calculate_topic_relevance(article) * 0.4
        
        # Content quality score (0.2 weight)
        scores['quality'] = self._calculate_content_quality(article) * 0.2
        
        # Freshness score (0.1 weight)
        scores['freshness'] = self._calculate_freshness_score(article) * 0.1
        
        # Source credibility score (0.1 weight)
        scores['source'] = self._calculate_source_score(article) * 0.1
        
        # TF-IDF score if corpus available (0.2 weight)
        if all_articles:
            scores['tfidf'] = self._calculate_tfidf_score(article, all_articles) * 0.2
        else:
            # Redistribute TF-IDF weight to topic score
            scores['topic'] += 0.2
        
        total_score = sum(scores.values())
        
        self.logger.debug(f"Relevance scores for '{article.title[:50]}...': {scores}")
        return min(total_score, 1.0)
    
    def _calculate_topic_relevance(self, article: Article) -> float:
        """Calculate relevance based on topic matching."""
        text = f"{article.title} {article.raw_content or ''}".lower()
        
        # Count topic keyword occurrences
        topic_matches = 0
        total_possible_matches = 0
        
        for topic in self.interest_topics:
            topic_words = re.findall(r'\b\w+\b', topic.lower())
            total_possible_matches += len(topic_words)
            
            for word in topic_words:
                if re.search(r'\b' + re.escape(word) + r'\b', text):
                    topic_matches += 1
        
        if total_possible_matches == 0:
            return 0.0
        
        return topic_matches / total_possible_matches
    
    def _calculate_content_quality(self, article: Article) -> float:
        """Calculate content quality score based on various factors."""
        score = 0.0
        
        # Title quality (length, structure)
        title_score = self._score_title_quality(article.title)
        score += title_score * 0.4
        
        # Content length and structure
        content_score = self._score_content_quality(article.raw_content or "")
        score += content_score * 0.6
        
        return score
    
    def _score_title_quality(self, title: str) -> float:
        """Score title quality."""
        score = 0.0
        
        # Length score (prefer moderate length titles)
        title_length = len(title.split())
        if 5 <= title_length <= 15:
            score += 0.5
        elif 3 <= title_length <= 20:
            score += 0.3
        else:
            score += 0.1
        
        # Technical keywords bonus
        tech_keywords = ['new', 'release', 'update', 'security', 'performance', 
                        'analysis', 'research', 'study', 'development']
        
        for keyword in tech_keywords:
            if keyword in title.lower():
                score += 0.1
                break
        
        # Avoid clickbait patterns
        clickbait_patterns = [r'\d+\s+(things|ways|reasons)', r'you won\'t believe',
                             r'shocking', r'amazing', r'incredible']
        
        for pattern in clickbait_patterns:
            if re.search(pattern, title.lower()):
                score -= 0.2
                break
        
        return max(0.0, min(1.0, score))
    
    def _score_content_quality(self, content: str) -> float:
        """Score content quality."""
        if not content.strip():
            return 0.2  # Some penalty for no content
        
        score = 0.0
        
        # Length score
        word_count = len(content.split())
        if word_count >= 100:
            score += 0.5
        elif word_count >= 50:
            score += 0.3
        else:
            score += 0.1
        
        # Technical vocabulary
        tech_terms = len([word for word in content.lower().split() 
                         if word in self.topic_vocabulary])
        if tech_terms > 0:
            score += min(0.3, tech_terms * 0.05)
        
        # Code or technical indicators
        if any(indicator in content for indicator in ['()', '{}', '[]', 'function', 'class', 'def ', 'import ']):
            score += 0.2
        
        return min(1.0, score)
    
    def _calculate_freshness_score(self, article: Article) -> float:
        """Calculate freshness score based on discovery date."""
        try:
            discovered = datetime.fromisoformat(article.discovered_date)
            now = datetime.now()
            age_hours = (now - discovered).total_seconds() / 3600
            
            # Score decreases with age
            if age_hours <= 24:
                return 1.0
            elif age_hours <= 72:  # 3 days
                return 0.8
            elif age_hours <= 168:  # 1 week
                return 0.6
            elif age_hours <= 720:  # 1 month
                return 0.4
            else:
                return 0.2
                
        except (ValueError, TypeError):
            return 0.5  # Default for unparseable dates
    
    def _calculate_source_score(self, article: Article) -> float:
        """Calculate source credibility score."""
        source_scores = {
            'hackernews': 0.9,  # High quality tech community
            'lwn': 0.95,        # Very high quality Linux/tech news
            'github': 0.8,      # Good for code-related content
            'arxiv': 1.0,       # Academic papers
            'unknown': 0.5      # Default
        }
        
        return source_scores.get(article.source, 0.5)
    
    def _calculate_tfidf_score(self, article: Article, all_articles: List[Article]) -> float:
        """Calculate TF-IDF based relevance score."""
        # Build corpus vocabulary if not exists
        if not self.document_frequencies:
            self._build_corpus_stats(all_articles)
        
        article_text = f"{article.title} {article.raw_content or ''}".lower()
        article_words = re.findall(r'\b\w+\b', article_text)
        
        # Calculate TF-IDF for topic-relevant words
        tfidf_score = 0.0
        
        for word in self.topic_vocabulary:
            if word in article_words:
                tf = article_words.count(word) / len(article_words) if article_words else 0
                idf = self._calculate_idf(word)
                tfidf_score += tf * idf
        
        # Normalize by vocabulary size
        return min(1.0, tfidf_score / len(self.topic_vocabulary) if self.topic_vocabulary else 0)
    
    def _build_corpus_stats(self, articles: List[Article]) -> None:
        """Build corpus statistics for TF-IDF."""
        self.total_documents = len(articles)
        word_doc_count = Counter()
        
        for article in articles:
            text = f"{article.title} {article.raw_content or ''}".lower()
            words = set(re.findall(r'\b\w+\b', text))
            
            for word in words:
                word_doc_count[word] += 1
        
        self.document_frequencies = dict(word_doc_count)
    
    def _calculate_idf(self, word: str) -> float:
        """Calculate inverse document frequency for a word."""
        if word not in self.document_frequencies or self.total_documents == 0:
            return 0.0
        
        df = self.document_frequencies[word]
        return math.log(self.total_documents / df)
    
    def score_articles_batch(self, articles: List[Article]) -> List[Article]:
        """Score a batch of articles and update their relevance scores."""
        # Build corpus stats for TF-IDF
        self._build_corpus_stats(articles)
        
        for article in articles:
            score = self.calculate_comprehensive_score(article, articles)
            article.relevance_score = score
        
        # Sort by relevance score
        articles.sort(key=lambda a: a.relevance_score, reverse=True)
        
        self.logger.info(f"Scored {len(articles)} articles (top score: {articles[0].relevance_score:.3f})")
        return articles
    
    def get_top_articles(self, articles: List[Article], count: int = 10) -> List[Article]:
        """Get top articles by relevance score."""
        sorted_articles = sorted(articles, key=lambda a: a.relevance_score, reverse=True)
        return sorted_articles[:count]
    
    def analyze_score_distribution(self, articles: List[Article]) -> Dict[str, Any]:
        """Analyze the distribution of relevance scores."""
        scores = [article.relevance_score for article in articles]
        
        if not scores:
            return {'error': 'No articles to analyze'}
        
        return {
            'count': len(scores),
            'mean': sum(scores) / len(scores),
            'min': min(scores),
            'max': max(scores),
            'median': sorted(scores)[len(scores) // 2],
            'high_relevance_count': len([s for s in scores if s >= 0.7]),
            'medium_relevance_count': len([s for s in scores if 0.3 <= s < 0.7]),
            'low_relevance_count': len([s for s in scores if s < 0.3])
        }
    
    def suggest_score_threshold(self, articles: List[Article], target_count: int = 50) -> float:
        """Suggest a relevance score threshold to get approximately target_count articles."""
        scores = sorted([article.relevance_score for article in articles], reverse=True)
        
        if len(scores) <= target_count:
            return 0.0
        
        return scores[target_count - 1]