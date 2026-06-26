"""
AI summarizer using DeepSeek API for generating news summaries
"""
import logging
from openai import OpenAI
from typing import Optional

from news_fetcher import NewsItem

logger = logging.getLogger(__name__)


class AISummarizer:
    """Generate AI-powered summaries for news using DeepSeek"""
    
    def __init__(self, api_key: str):
        self.client = OpenAI(
            api_key=api_key,
            base_url='https://api.deepseek.com'
        )
        self.model = 'deepseek-chat'
    
    def generate_summary(self, news_item: NewsItem, max_length: int = 200) -> str:
        """
        Generate a 2-paragraph Russian summary of a news item.
        
        Args:
            news_item: News item to summarize
            max_length: Maximum character length for summary
            
        Returns:
            AI-generated summary in Russian
        """
        # Build the prompt
        prompt = f"""Summarize this news article in exactly 2 short paragraphs in Russian.
Rules:
- First paragraph: main news headline and key facts
- Second paragraph: context and significance
- Keep total under {max_length} characters
- Use simple language
- Do not add titles like "Новость:" or "Статья:"

Title: {news_item.title}
Description: {news_item.description or 'No description available'}
Source: {news_item.source}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are a professional news translator and summarizer. Always respond in Russian.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            summary = response.choices[0].message.content.strip()
            logger.debug(f"Generated summary for: {news_item.title[:30]}...")
            return summary
            
        except Exception as e:
            logger.error(f"AI summarization error: {e}")
            # Fallback to simple translation
            return self._fallback_summary(news_item)
    
    def _fallback_summary(self, news_item: NewsItem) -> str:
        """Fallback summary using simple translation"""
        from translator import Translator
        
        translator = Translator()
        title = translator.translate(news_item.title) or news_item.title
        desc = translator.translate(news_item.description[:300]) if news_item.description else ""
        
        return f"📰 {title}\n\n{desc}"

    def summarize_batch(self, news_items: list[NewsItem]) -> dict[int, str]:
        """
        Generate summaries for multiple news items.
        
        Returns:
            Dictionary mapping news item index to summary
        """
        summaries = {}
        
        for i, item in enumerate(news_items):
            summary = self.generate_summary(item)
            summaries[i] = summary
            
            # Small delay to avoid rate limiting
            import time
            time.sleep(0.5)
        
        return summaries
