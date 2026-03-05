from __future__ import annotations

import re
from typing import Any

import numpy as np


class TextPreprocessor:
    """Text preprocessing for sports NLP.

    Handles:
    - URL removal
    - Mention/hashtag handling
    - HTML entity decoding
    - Emoji removal
    - Tokenization
    - Lowercasing
    """

    def __init__(
        self,
        remove_urls: bool = True,
        remove_mentions: bool = True,
        remove_hashtags: bool = False,
        remove_emoji: bool = True,
        lowercase: bool = True,
        keep_team_mentions: bool = True,
    ) -> None:
        self.remove_urls = remove_urls
        self.remove_mentions = remove_mentions
        self.remove_hashtags = remove_hashtags
        self.remove_emoji = remove_emoji
        self.lowercase = lowercase
        self.keep_team_mentions = keep_team_mentions

        self._url_pattern = re.compile(
            r"https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+"
        )
        self._mention_pattern = re.compile(r"@\w+")
        self._hashtag_pattern = re.compile(r"#\w+")
        self._emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE,
        )
        self._html_pattern = re.compile(r"&[#\w]+;")
        self._whitespace_pattern = re.compile(r"\s+")

    def clean(self, text: str) -> str:
        """Clean raw text.

        Args:
            text: Raw input text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        cleaned = text

        if self.remove_urls:
            cleaned = self._url_pattern.sub("", cleaned)

        if self.remove_mentions:
            if self.keep_team_mentions:
                cleaned = re.sub(r"@(?!\w{2,4})", "", cleaned)
            else:
                cleaned = self._mention_pattern.sub("", cleaned)

        if self.remove_hashtags:
            cleaned = self._hashtag_pattern.sub("", cleaned)

        if self.remove_emoji:
            cleaned = self._emoji_pattern.sub("", cleaned)

        cleaned = self._html_pattern.sub(" ", cleaned)

        if self.lowercase:
            cleaned = cleaned.lower()

        cleaned = self._whitespace_pattern.sub(" ", cleaned)
        cleaned = cleaned.strip()

        return cleaned

    def tokenize(self, text: str) -> list[str]:
        """Tokenize text into words.

        Args:
            text: Input text (will be cleaned first)

        Returns:
            List of tokens
        """
        cleaned = self.clean(text)

        tokens = re.findall(r"\b[\w']+\b", cleaned)

        return tokens

    def preprocess(self, text: str) -> dict[str, Any]:
        """Full preprocessing pipeline.

        Args:
            text: Raw input text

        Returns:
            Dict with cleaned text, tokens, and metadata
        """
        cleaned = self.clean(text)
        tokens = self.tokenize(cleaned)

        return {
            "original": text,
            "cleaned": cleaned,
            "tokens": tokens,
            "token_count": len(tokens),
            "has_url": bool(self._url_pattern.search(text)),
            "has_mention": bool(self._mention_pattern.search(text)),
            "has_hashtag": bool(self._hashtag_pattern.search(text)),
            "has_emoji": bool(self._emoji_pattern.search(text)),
        }

    def preprocess_batch(self, texts: list[str]) -> list[dict[str, Any]]:
        """Preprocess multiple texts.

        Args:
            texts: List of raw input texts

        Returns:
            List of preprocessed dicts
        """
        return [self.preprocess(text) for text in texts]


class POS Tagger:
    """Simple POS tagger using rule-based patterns.

    For production, would use spaCy or NLTK.
    """

    SPORTS_ENTITIES = {
        "noun": ["team", "player", "coach", "match", "game", "season", "score", "goal"],
        "verb": ["win", "lose", "play", "score", "beat", "lose", "train", "injure"],
        "adj": ["good", "bad", "great", "terrible", "excellent", "poor", "strong", "weak"],
    }

    def __init__(self) -> None:
        self._word_tag_map: dict[str, str] = {}
        self._build_map()

    def _build_map(self) -> None:
        """Build word to POS mapping."""
        for pos, words in self.SPORTS_ENTITIES.items():
            for word in words:
                self._word_tag_map[word] = pos

    def tag(self, tokens: list[str]) -> list[tuple[str, str]]:
        """Tag tokens with POS labels.

        Args:
            tokens: List of tokens

        Returns:
            List of (token, tag) tuples
        """
        tagged = []
        for token in tokens:
            tag = self._word_tag_map.get(token.lower(), "unknown")
            tagged.append((token, tag))
        return tagged

    def extract_entities(
        self,
        tokens: list[str],
    ) -> dict[str, list[str]]:
        """Extract named entities by POS pattern.

        Args:
            tokens: List of tokens

        Returns:
            Dict of entity type to list of entities
        """
        tagged = self.tag(tokens)

        entities: dict[str, list[str]] = {
            "players": [],
            "teams": [],
            "actions": [],
        }

        for i, (token, tag) in enumerate(tagged):
            if tag == "noun" and token[0].isupper():
                entities["players"].append(token)
            elif tag == "verb":
                entities["actions"].append(token)

        return entities


def clean_text(text: str) -> str:
    """Convenience function for text cleaning."""
    preprocessor = TextPreprocessor()
    return preprocessor.clean(text)


def tokenize_text(text: str) -> list[str]:
    """Convenience function for tokenization."""
    preprocessor = TextPreprocessor()
    return preprocessor.tokenize(text)
