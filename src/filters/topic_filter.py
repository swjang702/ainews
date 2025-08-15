"""Topic-based filtering for articles."""

import re
from typing import List, Dict, Set, Tuple
from collections import Counter

from ..models import Article
from ..logger import get_logger


class TopicFilter:
    """Filters articles based on interest topics using keyword matching."""
    
    def __init__(self, interest_topics: List[str], min_relevance_score: float = 0.3):
        self.interest_topics = interest_topics
        self.min_relevance_score = min_relevance_score
        self.logger = get_logger()
        
        # Preprocess topics for better matching
        self.processed_topics = self._preprocess_topics(interest_topics)
        
    def _preprocess_topics(self, topics: List[str]) -> Dict[str, Dict[str, any]]:
        """Preprocess topics to extract keywords and create matching patterns."""
        processed = {}
        
        for topic in topics:
            # Extract individual keywords
            keywords = self._extract_keywords(topic)
            
            # Create regex patterns for flexible matching
            patterns = self._create_patterns(topic, keywords)
            
            processed[topic] = {
                'keywords': keywords,
                'patterns': patterns,
                'exact_phrase': topic.lower(),
                'weight': self._calculate_topic_weight(topic)
            }
        
        return processed
    
    def _extract_keywords(self, topic: str) -> List[str]:
        """Extract meaningful keywords from a topic."""
        # Split on common separators and clean
        words = re.split(r'[,;\s]+', topic.lower())
        
        # Remove common stop words that don't add meaning
        stop_words = {'and', 'or', 'the', 'a', 'an', 'in', 'on', 'at', 'for', 'with', 'by'}
        keywords = [word.strip() for word in words if word.strip() and word.strip() not in stop_words]
        
        # Filter out very short words (unless they're acronyms)
        keywords = [kw for kw in keywords if len(kw) >= 2 or kw.isupper()]
        
        return keywords
    
    def _create_patterns(self, topic: str, keywords: List[str]) -> List[re.Pattern]:
        """Create regex patterns for matching."""
        patterns = []
        
        # Exact phrase pattern (case insensitive)
        exact_pattern = re.compile(re.escape(topic.lower()), re.IGNORECASE)
        patterns.append(exact_pattern)
        
        # Individual keyword patterns
        for keyword in keywords:
            # Word boundary pattern to avoid partial matches
            pattern = re.compile(r'\b' + re.escape(keyword) + r'\b', re.IGNORECASE)
            patterns.append(pattern)
        
        # Acronym patterns (look for capital letters)
        acronym_words = [word for word in keywords if len(word) <= 5 and word.isupper()]
        for acronym in acronym_words:
            # More flexible acronym matching
            pattern = re.compile(r'\b' + re.escape(acronym) + r'\b', re.IGNORECASE)
            patterns.append(pattern)
        
        return patterns
    
    def _calculate_topic_weight(self, topic: str) -> float:
        """Calculate weight for a topic based on its specificity."""
        # More specific topics get higher weights
        word_count = len(topic.split())
        
        if word_count == 1:
            return 0.8  # Single words are less specific
        elif word_count == 2:
            return 1.0  # Two words are well balanced
        else:
            return 1.2  # Longer phrases are more specific
    
    def filter_articles(self, articles: List[Article]) -> List[Article]:
        """Filter articles based on topic relevance."""
        relevant_articles = []
        
        for article in articles:
            relevance_data = self.calculate_relevance(article)
            
            if relevance_data['score'] >= self.min_relevance_score:
                # Update article with relevance information
                article.relevance_score = relevance_data['score']
                article.related_topics = relevance_data['matched_topics']
                relevant_articles.append(article)
        
        self.logger.info(f"Filtered {len(relevant_articles)} relevant articles from {len(articles)} total")
        return relevant_articles
    
    def calculate_relevance(self, article: Article) -> Dict[str, any]:
        """Calculate relevance score and matched topics for an article."""
        # Combine title and content for analysis
        text_to_analyze = f"{article.title} {article.raw_content or ''}"
        text_lower = text_to_analyze.lower()
        
        matched_topics = []
        total_score = 0.0
        match_details = {}
        
        for topic, topic_data in self.processed_topics.items():
            topic_score = self._score_topic_match(text_to_analyze, text_lower, topic_data)
            
            if topic_score > 0:
                matched_topics.append(topic)
                total_score += topic_score
                match_details[topic] = topic_score
        
        # Normalize score based on number of topics
        if len(self.interest_topics) > 0:
            normalized_score = min(total_score / len(self.interest_topics), 1.0)
        else:
            normalized_score = 0.0
        
        return {
            'score': normalized_score,
            'matched_topics': matched_topics,
            'match_details': match_details
        }
    
    def _score_topic_match(self, text: str, text_lower: str, topic_data: Dict) -> float:
        """Score how well a topic matches the given text."""
        score = 0.0
        
        # Check for exact phrase match (highest weight)
        if topic_data['exact_phrase'] in text_lower:
            score += 0.8 * topic_data['weight']
        
        # Check individual keyword matches
        keyword_matches = 0
        for pattern in topic_data['patterns'][1:]:  # Skip exact phrase pattern
            if pattern.search(text):
                keyword_matches += 1
        
        # Score based on keyword coverage
        if len(topic_data['keywords']) > 0:
            coverage = keyword_matches / len(topic_data['keywords'])
            score += coverage * 0.6 * topic_data['weight']
        
        # Bonus for multiple keyword matches in proximity
        if keyword_matches >= 2:
            score += 0.2 * topic_data['weight']
        
        return min(score, 1.0)  # Cap at 1.0
    
    def get_topic_statistics(self, articles: List[Article]) -> Dict[str, any]:
        """Get statistics about topic matching across articles."""
        topic_counts = Counter()
        total_articles = len(articles)
        
        for article in articles:
            for topic in article.related_topics:
                topic_counts[topic] += 1
        
        # Calculate coverage for each interest topic
        topic_coverage = {}
        for topic in self.interest_topics:
            count = topic_counts.get(topic, 0)
            coverage = count / total_articles if total_articles > 0 else 0
            topic_coverage[topic] = {
                'count': count,
                'coverage': coverage
            }
        
        return {
            'total_articles': total_articles,
            'topics_with_matches': len(topic_counts),
            'topic_coverage': topic_coverage,
            'most_common_topics': topic_counts.most_common(10)
        }
    
    def suggest_new_topics(self, articles: List[Article], min_frequency: int = 3) -> List[str]:
        """Suggest new topics based on frequently occurring terms in articles."""
        # Extract common terms from article titles and content
        all_text = " ".join([f"{article.title} {article.raw_content or ''}" 
                           for article in articles])
        
        # Simple term extraction (could be enhanced with NLP)
        words = re.findall(r'\b[A-Za-z]{3,}\b', all_text.lower())
        word_counts = Counter(words)
        
        # Filter out existing topic keywords
        existing_keywords = set()
        for topic_data in self.processed_topics.values():
            existing_keywords.update(topic_data['keywords'])
        
        # Suggest new terms that appear frequently but aren't in existing topics
        suggestions = []
        for word, count in word_counts.most_common(20):
            if count >= min_frequency and word not in existing_keywords:
                suggestions.append(f"{word} ({count} occurrences)")
        
        return suggestions
    
    def update_topics(self, new_topics: List[str]) -> None:
        """Update the interest topics list."""
        self.interest_topics = new_topics
        self.processed_topics = self._preprocess_topics(new_topics)
        self.logger.info(f"Updated topic filter with {len(new_topics)} topics")