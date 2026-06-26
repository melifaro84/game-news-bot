"""
Post publisher - creates rich posts with AI summaries and images
"""
import logging
import httpx
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from urllib.parse import urlparse

from news_fetcher import NewsItem
from ai_summarizer import AISummarizer
from image_extractor import ImageExtractor
from config import config

logger = logging.getLogger(__name__)


@dataclass
class PostContent:
    """Generated post content"""
    title: str
    summary: str
    image_url: Optional[str]
    source_url: str
    source_name: str
    published: Optional[datetime]


class PostPublisher:
    """Generate and publish rich posts to Telegram with AI summaries"""
    
    def __init__(self, api_key: str):
        self.summarizer = AISummarizer(api_key)
        self.image_extractor = ImageExtractor()
    
    async def prepare_post(self, news_item: NewsItem) -> PostContent:
        """
        Prepare a complete post for publication with AI-generated summary.
        
        Args:
            news_item: News item to process
            
        Returns:
            PostContent with AI summary and image
        """
        logger.info(f"Preparing post with AI summary: {news_item.title[:50]}...")
        
        # Generate AI summary
        summary = self.summarizer.generate_summary(news_item)
        
        # Try to extract image
        image_url = None
        if news_item.image_url:
            image_url = news_item.image_url
        else:
            # Try to get image from the article page
            image_url = self.image_extractor.extract_image(news_item.link)
        
        return PostContent(
            title=news_item.title,
            summary=summary,
            image_url=image_url,
            source_url=news_item.link,
            source_name=news_item.source,
            published=news_item.published
        )
    
    def close(self):
        """Clean up resources"""
        self.image_extractor.close()
