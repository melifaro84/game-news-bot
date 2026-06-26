"""
Web parser for sites without RSS feeds
"""
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class WebParser:
    """Parse news from websites without RSS"""
    
    def __init__(self):
        self.client = httpx.Client(timeout=15)
    
    def parse_ixbt_games(self, lookback_hours: int = 24, keywords: list = None) -> list[dict]:
        """
        Parse news from ixbt.games with keyword filtering.
        Returns list of dicts (converted to NewsItem by caller).
        """
        news_data = []
        default_keywords = ["portable", "handheld", "switch", "steam deck", "rog ally", 
                          "ayaneo", "pocket", "legion go", "портативн", "handheld", 
                          "Nintendo Switch", "Switch 2", "PS Portal", "мобильн", "карман",
                          "консоль", "приставк"]
        filter_keywords = keywords if keywords else default_keywords
        
        try:
            response = self.client.get('https://ixbt.games/news')
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all news links
            links = soup.find_all('a', href=lambda x: x and '/news/' in x if x else False)
            
            for link in links[:50]:  # Check first 50 links
                href = link.get('href', '')
                title = link.get_text(strip=True)
                
                # Skip navigation links
                if not href.startswith('http'):
                    href = 'https://ixbt.games' + href
                
                if '/news/' in href and title and len(title) > 10:
                    # Check if title contains any keyword
                    title_lower = title.lower()
                    matches = any(kw.lower() in title_lower for kw in filter_keywords)
                    
                    if matches:
                        news_data.append({
                            'title': title,
                            'link': href,
                            'source': 'ixbt.games',
                            'category': 'Портативные консоли',
                            'published': datetime.now(),
                            'description': ''
                        })
            
            logger.info(f"Parsed {len(news_data)} news from ixbt.games (filtered)")
            
        except Exception as e:
            logger.error(f"Error parsing ixbt.games: {e}")
        
        return news_data
    
    def parse_retrodrom(self) -> list[dict]:
        """
        Parse news from RetroDrom with images.
        """
        news_data = []
        
        try:
            response = self.client.get('https://retrodrom.games/')
            soup = BeautifulSoup(response.text, 'html.parser')
            
            articles = soup.find_all('article')[:30]
            
            for article in articles:
                # Ищу ссылку в thumb-link
                link_tag = article.find('a', class_='thumb-link')
                # Ищу картинку
                img_tag = article.find('img')
                # Ищу заголовок
                title_tag = article.find('h3') or article.find('h2') or article.find('a')
                
                if link_tag and img_tag:
                    href = str(link_tag.get('href', ''))
                    
                    # Get title from multiple sources
                    title = (
                        title_tag.get_text(strip=True) if title_tag else '' or
                        link_tag.get('title', '') or
                        img_tag.get('alt', '') or
                        link_tag.get_text(strip=True)
                    )
                    
                    # Get image URL
                    img_url = str(img_tag.get('src', '') or img_tag.get('data-src', ''))
                    
                    # Extract title from URL if needed
                    if not title or len(title) < 10:
                        # Try to extract from URL path
                        url_parts = href.split('/')
                        for part in reversed(url_parts):
                            if part and len(part) > 5 and 'obzor' not in part.lower():
                                title = part.replace('-', ' ').replace('_', ' ')
                                break
                    
                    if title and len(title) > 5 and href:
                        news_data.append({
                            'title': title,
                            'link': href,
                            'source': 'RetroDrom',
                            'category': 'Ретро-игры',
                            'published': datetime.now(),
                            'description': '',
                            'image_url': img_url if img_url.startswith('http') else ''
                        })
            
            logger.info(f"Parsed {len(news_data)} news from RetroDrom with images")
            
        except Exception as e:
            logger.error(f"Error parsing RetroDrom: {e}")
        
        return news_data

    def parse_generic(self, url: str, source_name: str, category: str,
                      link_selector: str = 'a[href*="/news/"]',
                      title_selector: str = None) -> list[dict]:
        """
        Generic parser with configurable selectors.
        """
        news_data = []
        
        try:
            response = self.client.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            links = soup.select(link_selector)
            
            for link in links[:20]:
                href = str(link.get('href', ''))
                title = link.get_text(strip=True) if not title_selector else \
                        (link.select_one(title_selector).get_text(strip=True) if link.select_one(title_selector) else link.get_text(strip=True))
                
                if href and title and len(title) > 10:
                    if not href.startswith('http'):
                        from urllib.parse import urljoin
                        href = urljoin(url, href)
                    
                    news_data.append({
                        'title': title,
                        'link': href,
                        'source': source_name,
                        'category': category,
                        'published': datetime.now(),
                        'description': ''
                    })
            
            logger.info(f"Parsed {len(news_data)} news from {source_name}")
            
        except Exception as e:
            logger.error(f"Error parsing {source_name}: {e}")
        
        return news_data
    
    def close(self):
        """Close HTTP client"""
        self.client.close()
