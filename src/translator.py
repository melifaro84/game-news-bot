"""
Translation module using Google Translate (via deep-translator)
"""
import logging
from deep_translator import GoogleTranslator
from typing import Optional

logger = logging.getLogger(__name__)


class Translator:
    """Translate text using Google Translate"""
    
    def __init__(self, source_lang: str = "en", target_lang: str = "ru"):
        self.source_lang = source_lang
        self.target_lang = target_lang
        self._translator = GoogleTranslator(source=source_lang, target=target_lang)
    
    def translate(self, text: str) -> Optional[str]:
        """
        Translate text from source language to target language.
        
        Args:
            text: Text to translate
            
        Returns:
            Translated text or None if failed
        """
        if not text or not text.strip():
            return text
        
        try:
            # Google Translate has limits, so we split long texts
            if len(text) > 4500:
                return self._translate_long(text)
            
            result = self._translator.translate(text)
            logger.debug(f"Translated: {text[:50]}... -> {result[:50]}...")
            return result
            
        except Exception as e:
            logger.warning(f"Translation error: {e}")
            return None
    
    def _translate_long(self, text: str) -> Optional[str]:
        """Translate long text by splitting into chunks"""
        # Split by sentences or paragraphs
        chunks = []
        current = ""
        
        # Split by double newlines first (paragraphs)
        paragraphs = text.split('\n\n')
        
        for para in paragraphs:
            if len(current) + len(para) < 4000:
                current += para + "\n\n"
            else:
                if current.strip():
                    chunks.append(current.strip())
                # Split long paragraph by sentences
                if len(para) > 4000:
                    sentences = para.split('. ')
                    current_chunk = ""
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) < 4000:
                            current_chunk += sentence + ". "
                        else:
                            if current_chunk:
                                chunks.append(current_chunk.strip())
                            current_chunk = sentence + ". "
                    if current_chunk:
                        current = current_chunk
                else:
                    current = para + "\n\n"
        
        if current.strip():
            chunks.append(current.strip())
        
        # Translate each chunk
        translated_chunks = []
        for chunk in chunks:
            try:
                result = self._translator.translate(chunk)
                translated_chunks.append(result)
            except Exception as e:
                logger.warning(f"Failed to translate chunk: {e}")
                translated_chunks.append(chunk)  # Keep original if fails
        
        return "\n\n".join(translated_chunks)
    
    def translate_batch(self, texts: list[str]) -> list[str]:
        """Translate multiple texts"""
        results = []
        for text in texts:
            translated = self.translate(text)
            results.append(translated if translated else text)
        return results
