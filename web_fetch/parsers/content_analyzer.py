"""
Content analysis and summarization utilities.

This module provides text analysis capabilities including summarization,
key phrase extraction, readability metrics, and language detection.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

try:
    import nltk
    from nltk.corpus import stopwords
    from nltk.stem import PorterStemmer
    from nltk.tokenize import sent_tokenize, word_tokenize

    HAS_NLTK = True
except ImportError:
    HAS_NLTK = False

try:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

from ..exceptions import ContentError
from ..models.base import ContentSummary

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """Content analyzer for text summarization and analysis."""

    def __init__(self):
        """Initialize content analyzer."""
        self._ensure_nltk_data()
        self.stemmer = PorterStemmer() if HAS_NLTK else None

        # Common stop words if NLTK is not available
        self.fallback_stopwords = {
            "a",
            "an",
            "and",
            "are",
            "as",
            "at",
            "be",
            "by",
            "for",
            "from",
            "has",
            "he",
            "in",
            "is",
            "it",
            "its",
            "of",
            "on",
            "that",
            "the",
            "to",
            "was",
            "will",
            "with",
            "would",
            "you",
            "your",
            "have",
            "had",
            "this",
            "these",
            "they",
            "were",
            "been",
            "their",
            "said",
            "each",
            "which",
            "she",
            "do",
            "how",
            "his",
            "or",
            "if",
            "about",
            "who",
            "get",
            "go",
            "me",
            "when",
            "make",
            "can",
            "like",
            "time",
            "no",
            "just",
            "him",
            "know",
            "take",
            "people",
            "into",
            "year",
            "good",
            "some",
            "could",
            "them",
            "see",
            "other",
            "than",
            "then",
            "now",
            "look",
            "only",
            "come",
            "its",
            "over",
            "think",
            "also",
            "back",
            "after",
            "use",
            "two",
            "way",
            "even",
            "new",
            "want",
            "because",
            "any",
            "these",
            "give",
            "day",
            "most",
            "us",
        }

    def _ensure_nltk_data(self):
        """Ensure required NLTK data is downloaded."""
        if not HAS_NLTK:
            logger.warning("NLTK not available, using fallback methods")
            return

        try:
            # Try to use punkt tokenizer
            nltk.data.find("tokenizers/punkt")
        except LookupError:
            try:
                nltk.download("punkt", quiet=True)
            except Exception as e:
                logger.warning(f"Failed to download NLTK punkt data: {e}")

        try:
            # Try to use stopwords
            nltk.data.find("corpora/stopwords")
        except LookupError:
            try:
                nltk.download("stopwords", quiet=True)
            except Exception as e:
                logger.warning(f"Failed to download NLTK stopwords: {e}")

    def analyze_content(
        self, text: str, summary_length: int = 3, extract_phrases: bool = True
    ) -> ContentSummary:
        """
        Analyze text content and generate summary with metrics.

        Args:
            text: Text content to analyze
            summary_length: Number of sentences for summary
            extract_phrases: Whether to extract key phrases

        Returns:
            ContentSummary object with analysis results
        """
        if not text or not text.strip():
            return ContentSummary()

        # Clean text
        cleaned_text = self._clean_text(text)

        # Basic metrics
        word_count = len(cleaned_text.split())
        sentences = self._tokenize_sentences(cleaned_text)
        sentence_count = len(sentences)
        paragraph_count = len([p for p in text.split("\n\n") if p.strip()])

        # Reading time (average 200 words per minute)
        reading_time = word_count / 200.0

        # Generate summary
        summary_text = self._generate_summary(sentences, summary_length)

        # Extract key phrases
        key_phrases = []
        if extract_phrases:
            key_phrases = self._extract_key_phrases(cleaned_text)

        # Calculate readability score
        readability_score = self._calculate_readability(cleaned_text, sentences)

        # Detect language (basic heuristic)
        language = self._detect_language(cleaned_text)

        return ContentSummary(
            word_count=word_count,
            sentence_count=sentence_count,
            paragraph_count=paragraph_count,
            reading_time_minutes=reading_time,
            key_phrases=key_phrases,
            summary_text=summary_text,
            language=language,
            readability_score=readability_score,
        )

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text)

        # Remove special characters but keep punctuation
        text = re.sub(r"[^\w\s\.\!\?\,\;\:\-\(\)]", " ", text)

        # Remove extra spaces
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def _tokenize_sentences(self, text: str) -> List[str]:
        """Tokenize text into sentences."""
        if HAS_NLTK:
            try:
                return sent_tokenize(text)
            except Exception as e:
                logger.warning(f"NLTK sentence tokenization failed: {e}")

        # Fallback sentence tokenization
        sentences = re.split(r"[.!?]+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _tokenize_words(self, text: str) -> List[str]:
        """Tokenize text into words."""
        if HAS_NLTK:
            try:
                return word_tokenize(text.lower())
            except Exception as e:
                logger.warning(f"NLTK word tokenization failed: {e}")

        # Fallback word tokenization
        words = re.findall(r"\b\w+\b", text.lower())
        return words

    def _get_stopwords(self) -> set:
        """Get stopwords set."""
        if HAS_NLTK:
            try:
                return set(stopwords.words("english"))
            except Exception as e:
                logger.warning(f"NLTK stopwords failed: {e}")

        return self.fallback_stopwords

    def _generate_summary(self, sentences: List[str], length: int) -> str:
        """Generate extractive summary using sentence ranking."""
        if not sentences or length <= 0:
            return ""

        if len(sentences) <= length:
            return " ".join(sentences)

        if HAS_SKLEARN:
            return self._generate_tfidf_summary(sentences, length)
        else:
            return self._generate_frequency_summary(sentences, length)

    def _generate_tfidf_summary(self, sentences: List[str], length: int) -> str:
        """Generate summary using TF-IDF scoring."""
        try:
            # Create TF-IDF vectorizer
            vectorizer = TfidfVectorizer(
                stop_words="english", lowercase=True, max_features=1000
            )

            # Fit and transform sentences
            tfidf_matrix = vectorizer.fit_transform(sentences)

            # Calculate sentence scores (sum of TF-IDF values)
            sentence_scores = np.array(tfidf_matrix.sum(axis=1)).flatten()

            # Get top sentences
            top_indices = sentence_scores.argsort()[-length:][::-1]
            top_indices = sorted(top_indices)  # Maintain original order

            summary_sentences = [sentences[i] for i in top_indices]
            return " ".join(summary_sentences)

        except Exception as e:
            logger.warning(f"TF-IDF summarization failed: {e}")
            return self._generate_frequency_summary(sentences, length)

    def _generate_frequency_summary(self, sentences: List[str], length: int) -> str:
        """Generate summary using word frequency scoring."""
        # Get word frequencies
        all_words = []
        for sentence in sentences:
            words = self._tokenize_words(sentence)
            all_words.extend(words)

        # Remove stopwords
        stopwords_set = self._get_stopwords()
        filtered_words = [word for word in all_words if word not in stopwords_set]

        # Calculate word frequencies
        word_freq = Counter(filtered_words)

        # Score sentences based on word frequencies
        sentence_scores = []
        for sentence in sentences:
            words = self._tokenize_words(sentence)
            score = sum(
                word_freq.get(word, 0) for word in words if word not in stopwords_set
            )
            sentence_scores.append(score)

        # Get top sentences
        indexed_scores = list(enumerate(sentence_scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        top_indices = [i for i, _ in indexed_scores[:length]]
        top_indices.sort()  # Maintain original order

        summary_sentences = [sentences[i] for i in top_indices]
        return " ".join(summary_sentences)

    def _extract_key_phrases(self, text: str, max_phrases: int = 10) -> List[str]:
        """Extract key phrases from text."""
        words = self._tokenize_words(text)
        stopwords_set = self._get_stopwords()

        # Filter out stopwords and short words
        filtered_words = [
            word for word in words if word not in stopwords_set and len(word) > 2
        ]

        # Get word frequencies
        word_freq = Counter(filtered_words)

        # Extract n-grams (2-3 word phrases)
        phrases = []

        # Bigrams
        for i in range(len(words) - 1):
            if (
                words[i] not in stopwords_set
                and words[i + 1] not in stopwords_set
                and len(words[i]) > 2
                and len(words[i + 1]) > 2
            ):
                phrase = f"{words[i]} {words[i+1]}"
                phrases.append(phrase)

        # Trigrams
        for i in range(len(words) - 2):
            if all(word not in stopwords_set for word in words[i : i + 3]) and all(
                len(word) > 2 for word in words[i : i + 3]
            ):
                phrase = f"{words[i]} {words[i+1]} {words[i+2]}"
                phrases.append(phrase)

        # Count phrase frequencies
        phrase_freq = Counter(phrases)

        # Combine single words and phrases
        all_candidates = []

        # Add top single words
        for word, freq in word_freq.most_common(max_phrases):
            all_candidates.append((word, freq))

        # Add top phrases
        for phrase, freq in phrase_freq.most_common(max_phrases):
            all_candidates.append((phrase, freq * 2))  # Weight phrases higher

        # Sort by frequency and return top phrases
        all_candidates.sort(key=lambda x: x[1], reverse=True)
        return [phrase for phrase, _ in all_candidates[:max_phrases]]

    def _calculate_readability(self, text: str, sentences: List[str]) -> float:
        """Calculate readability score (Flesch Reading Ease approximation)."""
        if not sentences:
            return 0.0

        words = self._tokenize_words(text)

        if not words:
            return 0.0

        # Count syllables (approximation)
        total_syllables = sum(self._count_syllables(word) for word in words)

        # Calculate metrics
        avg_sentence_length = len(words) / len(sentences)
        avg_syllables_per_word = total_syllables / len(words)

        # Flesch Reading Ease formula (approximation)
        score = (
            206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_syllables_per_word)
        )

        # Clamp score between 0 and 100
        return max(0.0, min(100.0, score))

    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word (approximation)."""
        word = word.lower()
        vowels = "aeiouy"
        syllable_count = 0
        prev_was_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not prev_was_vowel:
                syllable_count += 1
            prev_was_vowel = is_vowel

        # Handle silent 'e'
        if word.endswith("e") and syllable_count > 1:
            syllable_count -= 1

        return max(1, syllable_count)

    def _detect_language(self, text: str) -> str:
        """Detect language using basic heuristics."""
        # This is a very basic language detection
        # In a production system, you'd use a proper language detection library

        words = self._tokenize_words(text)
        if not words:
            return "unknown"

        # Check for common English words
        english_indicators = {
            "the",
            "and",
            "or",
            "but",
            "in",
            "on",
            "at",
            "to",
            "for",
            "of",
            "with",
            "by",
            "from",
            "up",
            "about",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "among",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
        }

        english_count = sum(1 for word in words[:100] if word in english_indicators)

        if english_count > len(words[:100]) * 0.1:  # If >10% are English indicators
            return "en"

        return "unknown"

    def get_text_statistics(self, text: str) -> Dict[str, Any]:
        """Get detailed text statistics."""
        if not text:
            return {}

        words = self._tokenize_words(text)
        sentences = self._tokenize_sentences(text)

        # Character statistics
        char_count = len(text)
        char_count_no_spaces = len(text.replace(" ", ""))

        # Word statistics
        word_count = len(words)
        unique_words = len(set(words))
        avg_word_length = sum(len(word) for word in words) / len(words) if words else 0

        # Sentence statistics
        sentence_count = len(sentences)
        avg_sentence_length = word_count / sentence_count if sentence_count else 0

        # Paragraph statistics
        paragraphs = [p for p in text.split("\n\n") if p.strip()]
        paragraph_count = len(paragraphs)

        return {
            "characters": char_count,
            "characters_no_spaces": char_count_no_spaces,
            "words": word_count,
            "unique_words": unique_words,
            "sentences": sentence_count,
            "paragraphs": paragraph_count,
            "avg_word_length": round(avg_word_length, 2),
            "avg_sentence_length": round(avg_sentence_length, 2),
            "lexical_diversity": (
                round(unique_words / word_count, 3) if word_count else 0
            ),
            "reading_time_minutes": round(word_count / 200.0, 1),
        }
