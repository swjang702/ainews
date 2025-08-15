"""Weekly report generation logic."""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import Counter, defaultdict

from ..models import Article, WeeklyReport
from ..storage.datastore import JSONDataStore
from ..summarizer.content_processor import ContentProcessor
from ..logger import get_logger


class ReportGenerator:
    """Generates weekly reports from collected articles."""
    
    def __init__(self, datastore: JSONDataStore, content_processor: ContentProcessor):
        self.datastore = datastore
        self.content_processor = content_processor
        self.logger = get_logger()
    
    def generate_weekly_report(self, week_start: str = None, week_end: str = None) -> WeeklyReport:
        """Generate a comprehensive weekly report."""
        # Calculate week boundaries if not provided
        if not week_start or not week_end:
            week_start, week_end = self._get_current_week_boundaries()
        
        self.logger.info(f"Generating weekly report for {week_start} to {week_end}")
        
        # Get articles for the week
        articles = self.datastore.get_articles_in_range(week_start, week_end)
        
        if not articles:
            self.logger.warning(f"No articles found for week {week_start} to {week_end}")
            return WeeklyReport.create(week_start, week_end, [], "No articles found for this week.")
        
        # Analyze and organize articles
        analysis = self._analyze_articles(articles)
        
        # Generate comprehensive summary
        summary = self._generate_comprehensive_summary(articles, analysis)
        
        # Create report
        report = WeeklyReport.create(week_start, week_end, articles, summary)
        
        # Enhance report with additional data
        report = self._enhance_report_with_analysis(report, analysis)
        
        self.logger.info(f"Generated weekly report with {len(articles)} articles")
        return report
    
    def _get_current_week_boundaries(self) -> tuple[str, str]:
        """Get the start and end dates for the current week."""
        today = datetime.now()
        
        # Get Monday of current week
        days_since_monday = today.weekday()
        monday = today - timedelta(days=days_since_monday)
        
        # Get Sunday of current week
        sunday = monday + timedelta(days=6)
        
        return monday.strftime('%Y-%m-%d'), sunday.strftime('%Y-%m-%d')
    
    def _analyze_articles(self, articles: List[Article]) -> Dict[str, Any]:
        """Analyze articles for trends and insights."""
        analysis = {
            'topic_distribution': self._analyze_topic_distribution(articles),
            'source_distribution': self._analyze_source_distribution(articles),
            'daily_distribution': self._analyze_daily_distribution(articles),
            'top_articles': self._get_top_articles(articles),
            'trending_topics': self._identify_trending_topics(articles),
            'article_quality_stats': self._analyze_article_quality(articles)
        }
        
        return analysis
    
    def _analyze_topic_distribution(self, articles: List[Article]) -> Dict[str, Any]:
        """Analyze how articles are distributed across topics."""
        topic_counts = Counter()
        topic_relevance = defaultdict(list)
        
        for article in articles:
            for topic in article.related_topics:
                topic_counts[topic] += 1
                topic_relevance[topic].append(article.relevance_score)
        
        # Calculate average relevance per topic
        topic_avg_relevance = {}
        for topic, scores in topic_relevance.items():
            topic_avg_relevance[topic] = sum(scores) / len(scores) if scores else 0
        
        return {
            'counts': dict(topic_counts.most_common()),
            'average_relevance': topic_avg_relevance,
            'total_unique_topics': len(topic_counts),
            'most_popular_topic': topic_counts.most_common(1)[0] if topic_counts else None
        }
    
    def _analyze_source_distribution(self, articles: List[Article]) -> Dict[str, Any]:
        """Analyze article distribution by source."""
        source_counts = Counter(article.source for article in articles)
        
        source_quality = defaultdict(list)
        for article in articles:
            source_quality[article.source].append(article.relevance_score)
        
        source_avg_quality = {}
        for source, scores in source_quality.items():
            source_avg_quality[source] = sum(scores) / len(scores) if scores else 0
        
        return {
            'counts': dict(source_counts),
            'average_quality': source_avg_quality,
            'total_sources': len(source_counts)
        }
    
    def _analyze_daily_distribution(self, articles: List[Article]) -> Dict[str, Any]:
        """Analyze article distribution by day."""
        daily_counts = Counter()
        
        for article in articles:
            try:
                date = datetime.fromisoformat(article.discovered_date).date()
                daily_counts[date.strftime('%Y-%m-%d')] += 1
            except (ValueError, TypeError):
                daily_counts['unknown'] += 1
        
        # Calculate peak and quiet days
        if daily_counts:
            max_day = max(daily_counts.items(), key=lambda x: x[1])
            min_day = min(daily_counts.items(), key=lambda x: x[1])
        else:
            max_day = min_day = None
        
        return {
            'daily_counts': dict(daily_counts),
            'peak_day': max_day,
            'quiet_day': min_day,
            'average_per_day': sum(daily_counts.values()) / len(daily_counts) if daily_counts else 0
        }
    
    def _get_top_articles(self, articles: List[Article], count: int = 10) -> List[Article]:
        """Get top articles by relevance score."""
        return sorted(articles, key=lambda a: a.relevance_score, reverse=True)[:count]
    
    def _identify_trending_topics(self, articles: List[Article]) -> List[Dict[str, Any]]:
        """Identify trending topics based on frequency and recency."""
        # Group articles by topic and date
        topic_timeline = defaultdict(list)
        
        for article in articles:
            for topic in article.related_topics:
                try:
                    date = datetime.fromisoformat(article.discovered_date).date()
                    topic_timeline[topic].append(date)
                except (ValueError, TypeError):
                    continue
        
        # Calculate trend scores
        trending_topics = []
        today = datetime.now().date()
        
        for topic, dates in topic_timeline.items():
            if len(dates) < 2:  # Need at least 2 articles to identify trend
                continue
            
            # Calculate recency score (more recent = higher score)
            recency_scores = []
            for date in dates:
                days_ago = (today - date).days
                recency_score = max(0, 7 - days_ago) / 7  # Score decreases over 7 days
                recency_scores.append(recency_score)
            
            avg_recency = sum(recency_scores) / len(recency_scores)
            frequency = len(dates)
            
            # Combined trend score
            trend_score = (frequency * 0.6) + (avg_recency * 0.4)
            
            trending_topics.append({
                'topic': topic,
                'frequency': frequency,
                'recency_score': avg_recency,
                'trend_score': trend_score,
                'latest_date': max(dates).strftime('%Y-%m-%d')
            })
        
        # Sort by trend score
        trending_topics.sort(key=lambda x: x['trend_score'], reverse=True)
        
        return trending_topics[:5]  # Top 5 trending topics
    
    def _analyze_article_quality(self, articles: List[Article]) -> Dict[str, Any]:
        """Analyze overall article quality metrics."""
        scores = [article.relevance_score for article in articles]
        
        if not scores:
            return {'error': 'No articles to analyze'}
        
        # Quality distribution
        high_quality = len([s for s in scores if s >= 0.7])
        medium_quality = len([s for s in scores if 0.4 <= s < 0.7])
        low_quality = len([s for s in scores if s < 0.4])
        
        return {
            'total_articles': len(articles),
            'average_score': sum(scores) / len(scores),
            'highest_score': max(scores),
            'lowest_score': min(scores),
            'high_quality_count': high_quality,
            'medium_quality_count': medium_quality,
            'low_quality_count': low_quality,
            'quality_distribution': {
                'high': high_quality / len(articles),
                'medium': medium_quality / len(articles),
                'low': low_quality / len(articles)
            }
        }
    
    def _generate_comprehensive_summary(self, articles: List[Article], analysis: Dict[str, Any]) -> str:
        """Generate a comprehensive summary using LLM."""
        try:
            # Prepare summary of key insights
            insights_summary = self._prepare_insights_summary(analysis)
            
            # Get top articles for detailed summary
            top_articles = analysis['top_articles'][:10]
            
            # Generate LLM summary
            summary = self.content_processor.generate_batch_summary(top_articles)
            
            # Combine with insights
            full_summary = f"{insights_summary}\n\n{summary}"
            
            return full_summary
            
        except Exception as e:
            self.logger.error(f"Failed to generate comprehensive summary: {e}")
            return self._generate_fallback_summary(articles, analysis)
    
    def _prepare_insights_summary(self, analysis: Dict[str, Any]) -> str:
        """Prepare a summary of key insights."""
        insights = []
        
        # Topic insights
        topic_dist = analysis['topic_distribution']
        if topic_dist['most_popular_topic']:
            insights.append(f"Most discussed topic: {topic_dist['most_popular_topic'][0]} ({topic_dist['most_popular_topic'][1]} articles)")
        
        # Source insights
        source_dist = analysis['source_distribution']
        total_articles = sum(source_dist['counts'].values())
        insights.append(f"Total articles collected: {total_articles}")
        
        # Quality insights
        quality_stats = analysis['article_quality_stats']
        if 'average_score' in quality_stats:
            insights.append(f"Average relevance score: {quality_stats['average_score']:.2f}")
        
        # Trending insights
        trending = analysis['trending_topics']
        if trending:
            top_trend = trending[0]
            insights.append(f"Top trending topic: {top_trend['topic']} (trend score: {top_trend['trend_score']:.2f})")
        
        return "## Weekly Insights\n" + "\n".join(f"- {insight}" for insight in insights)
    
    def _generate_fallback_summary(self, articles: List[Article], analysis: Dict[str, Any]) -> str:
        """Generate a fallback summary without LLM."""
        summary_parts = []
        
        # Basic stats
        total_articles = len(articles)
        summary_parts.append(f"This week we collected {total_articles} relevant articles.")
        
        # Topic distribution
        topic_dist = analysis['topic_distribution']
        if topic_dist['most_popular_topic']:
            topic, count = topic_dist['most_popular_topic']
            summary_parts.append(f"The most discussed topic was '{topic}' with {count} articles.")
        
        # Quality assessment
        quality_stats = analysis['article_quality_stats']
        if 'high_quality_count' in quality_stats:
            high_quality = quality_stats['high_quality_count']
            summary_parts.append(f"{high_quality} articles were rated as high quality (relevance score ≥ 0.7).")
        
        # Sources
        source_dist = analysis['source_distribution']
        sources = list(source_dist['counts'].keys())
        summary_parts.append(f"Articles were collected from {len(sources)} sources: {', '.join(sources)}.")
        
        return "\n\n".join(summary_parts)
    
    def _enhance_report_with_analysis(self, report: WeeklyReport, analysis: Dict[str, Any]) -> WeeklyReport:
        """Enhance the report with additional analysis data."""
        # This could be extended to add more detailed analysis to the report
        # For now, the analysis is used in summary generation
        return report
    
    def generate_topic_focused_report(self, topic: str, days: int = 7) -> Dict[str, Any]:
        """Generate a focused report on a specific topic."""
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        articles = self.datastore.get_articles_in_range(start_date, end_date)
        
        # Filter articles for the specific topic
        topic_articles = [article for article in articles if topic.lower() in [t.lower() for t in article.related_topics]]
        
        if not topic_articles:
            return {'error': f'No articles found for topic: {topic}'}
        
        # Analyze topic-specific articles
        analysis = self._analyze_articles(topic_articles)
        
        return {
            'topic': topic,
            'period': f"{start_date} to {end_date}",
            'article_count': len(topic_articles),
            'articles': [article.to_dict() for article in topic_articles[:10]],
            'analysis': analysis,
            'summary': self.content_processor.generate_batch_summary(topic_articles[:5])
        }