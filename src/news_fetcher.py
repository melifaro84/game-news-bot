"""
News fetcher module - handles fetching and parsing news from RSS feeds
"""
import feedparser
import httpx
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from dateutil import parser as date_parser
import logging

from config import config
from web_parser import WebParser

logger = logging.getLogger(__name__)


@dataclass
class NewsItem:
    """Single news article"""
    title: str
    link: str
    source: str
    category: str
    published: Optional[datetime] = None
    description: str = ""
    image_url: Optional[str] = None


@dataclass
class FetchResult:
    """Result of fetching news from a source"""
    source_name: str
    category: str
    news: list = field(default_factory=list)
    error: Optional[str] = None
    fetched_at: datetime = field(default_factory=datetime.now)


class NewsFetcher:
    """Fetches news from configured RSS sources and web pages"""

    def __init__(self, lookback_hours: int = 12):
        """
        Initialize fetcher.

        Args:
            lookback_hours: How many hours back to look for news (default: 12 - covers overnight)
        """
        self.lookback_hours = lookback_hours
        self.cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
        self.web_parser = WebParser()

    def fetch_rss_feed(self, source: dict) -> FetchResult:
        """
        Fetch a single RSS feed.

        Args:
            source: Source configuration dict with name, url, category, enabled

        Returns:
            FetchResult with news items or error
        """
        if not source.get("enabled", True):
            return FetchResult(
                source_name=source["name"],
                category=source["category"],
                news=[],
                error="Source disabled"
            )

        try:
            logger.info(f"Fetching RSS: {source['name']} ({source['url']})")
            
            # Check if source has custom lookback period
            lookback = source.get('lookback_hours', self.lookback_hours)
            cutoff = datetime.now() - timedelta(hours=lookback)

            # Parse RSS feed
            feed = feedparser.parse(source["url"])

            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS parse warning for {source['name']}: {feed.bozo_exception}")

            news_items = []

            for entry in feed.entries[:20]:  # Limit to 20 latest entries
                # Parse publication date
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6])
                    except Exception:
                        pass

                if published and published < cutoff:
                    continue

                # Extract description
                description = ""
                if hasattr(entry, 'summary'):
                    description = self._clean_html(entry.summary)
                elif hasattr(entry, 'description'):
                    description = self._clean_html(entry.description)

                # Try to extract image from content or media
                image_url = self._extract_image(entry)

                news_item = NewsItem(
                    title=self._clean_text(entry.title),
                    link=entry.link,
                    source=source["name"],
                    category=source["category"],
                    published=published,
                    description=description[:200] + "..." if len(description) > 200 else description,
                    image_url=image_url
                )

                news_items.append(news_item)

            logger.info(f"Fetched {len(news_items)} news from {source['name']}")

            return FetchResult(
                source_name=source["name"],
                category=source["category"],
                news=news_items
            )

        except Exception as e:
            logger.error(f"Error fetching {source['name']}: {e}")
            return FetchResult(
                source_name=source["name"],
                category=source["category"],
                error=str(e)
            )

    def fetch_all_sources(self) -> list[FetchResult]:
        """
        Fetch all enabled sources (RSS and web).

        Returns:
            List of FetchResult objects
        """
        results = []

        for source in config.sources.sources:
            if source.get('type') == 'web':
                result = self.fetch_web_source(source)
            else:
                result = self.fetch_rss_feed(source)
            results.append(result)

        return results

    def fetch_web_source(self, source: dict) -> FetchResult:
        """
        Fetch news from a web page source.

        Args:
            source: Source configuration dict

        Returns:
            FetchResult with news items
        """
        if not source.get("enabled", True):
            return FetchResult(
                source_name=source["name"],
                category=source["category"],
                news=[],
                error="Source disabled"
            )

        try:
            logger.info(f"Fetching web: {source['name']} ({source['url']})")

            if source['name'] == 'ixbt.games':
                keywords = source.get('keywords', None)
                news_data = self.web_parser.parse_ixbt_games(self.lookback_hours, keywords)
            elif source['name'] == 'RetroDrom':
                news_data = self.web_parser.parse_retrodrom()
            else:
                # Generic web parser
                news_data = self.web_parser.parse_generic(
                    url=source['url'],
                    source_name=source['name'],
                    category=source['category']
                )
            
            # Convert dicts to NewsItem
            news_items = []
            for item in news_data:
                news_items.append(NewsItem(
                    title=item['title'],
                    link=item['link'],
                    source=item['source'],
                    category=item['category'],
                    published=item['published'],
                    description=item['description'],
                    image_url=item.get('image_url', '')
                ))

            logger.info(f"Fetched {len(news_items)} news from {source['name']}")

            return FetchResult(
                source_name=source["name"],
                category=source["category"],
                news=news_items
            )

        except Exception as e:
            logger.error(f"Error fetching {source['name']}: {e}")
            return FetchResult(
                source_name=source["name"],
                category=source["category"],
                error=str(e)
            )

    def get_all_news(self, max_per_source: int = 5) -> list[NewsItem]:
        """
        Get all news from all sources, sorted by date.

        Args:
            max_per_source: Maximum news per source to include

        Returns:
            Sorted list of NewsItem objects
        """
        results = self.fetch_all_sources()
        all_news = []

        for result in results:
            if result.error:
                logger.warning(f"Skipping {result.source_name}: {result.error}")
                continue

            # Take only recent news
            recent_news = [
                item for item in result.news
                if item.published is None or item.published > self.cutoff_time
            ][:max_per_source]

            all_news.extend(recent_news)

        # Sort by publication date (newest first)
        all_news.sort(
            key=lambda x: x.published if x.published else datetime.min,
            reverse=True
        )

        return all_news

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text"""
        if not text:
            return ""
        soup = BeautifulSoup(text, 'html.parser')
        return soup.get_text(separator=' ').strip()

    def _clean_text(self, text: str) -> str:
        """Basic text cleaning"""
        if not text:
            return ""
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text

    def _extract_image(self, entry) -> Optional[str]:
        """Extract image URL from RSS entry"""
        # Try media_content
        if hasattr(entry, 'media_content') and entry.media_content:
            for media in entry.media_content:
                if 'url' in media and any(
                    img_type in media.get('type', '')
                    for img_type in ['image/jpeg', 'image/png', 'image/webp']
                ):
                    return media['url']

        # Try enclosures
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enclosure in entry.enclosures:
                if 'url' in enclosure and 'image' in enclosure.get('type', ''):
                    return enclosure['url']

        # Try to find image in content
        content = getattr(entry, 'content', [{}])[0].get('value', '') if hasattr(entry, 'content') else ''
        if content:
            soup = BeautifulSoup(content, 'html.parser')
            img_tag = soup.find('img')
            if img_tag and img_tag.get('src'):
                return img_tag['src']

        return None
