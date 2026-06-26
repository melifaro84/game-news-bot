"""
Image extractor for news articles
Extracts preview images from article pages
"""
import httpx
from bs4 import BeautifulSoup
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ImageExtractor:
    """Extract preview images from news articles"""
    
    def __init__(self):
        self.client = httpx.Client(timeout=10)
    
    def extract_image(self, url: str) -> Optional[str]:
        """
        Extract preview image URL from article page.
        
        Args:
            url: Article URL
            
        Returns:
            Image URL or None if not found
        """
        try:
            response = self.client.get(url, follow_redirects=True)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try different meta tags in order of preference
            image_url = None
            
            # 1. og:image (Open Graph)
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                image_url = og_image['content']
            
            # 2. twitter:image
            if not image_url:
                twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
                if twitter_image and twitter_image.get('content'):
                    image_url = twitter_image['content']
            
            # 3. twitter:image:src
            if not image_url:
                twitter_image_src = soup.find('meta', attrs={'name': 'twitter:image:src'})
                if twitter_image_src and twitter_image_src.get('content'):
                    image_url = twitter_image_src['content']
            
            # 4. article.image
            if not image_url:
                article_image = soup.find('meta', property='article:image')
                if article_image and article_image.get('content'):
                    image_url = article_image['content']
            
            # Make relative URLs absolute
            if image_url and image_url.startswith('/'):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                image_url = f"{parsed.scheme}://{parsed.netloc}{image_url}"
            
            if image_url:
                logger.debug(f"Extracted image from {url}: {image_url[:80]}...")
            
            return image_url
            
        except Exception as e:
            logger.warning(f"Failed to extract image from {url}: {e}")
            return None
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
