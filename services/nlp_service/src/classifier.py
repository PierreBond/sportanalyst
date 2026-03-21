from __future__ import annotations

from typing import Any

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from sports_common.logging import get_logger
from .preprocessing import TextPreprocessor

logger = get_logger(__name__)

DEFAULT_MODEL = "nlptown/bert-base-multilingual-uncased-sentiment"


class SentimentClassifier:
    """BERT-based sentiment classifier for sports text.

    Uses nlptown/bert-base-multilingual-uncased-sentiment model
    which outputs 1-5 star ratings, converted to [-1, 1] scale.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        device: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._tokenizer = None
        self._model = None
        self._preprocessor = TextPreprocessor()

    @property
    def tokenizer(self) -> AutoTokenizer:
        if self._tokenizer is None:
            logger.info("loading_tokenizer", model=self._model_name)
            self._tokenizer = AutoTokenizer.from_pretrained(self._model_name)
        return self._tokenizer

    @property
    def model(self) -> AutoModelForSequenceClassification:
        if self._model is None:
            logger.info("loading_model", model=self._model_name, device=self._device)
            self._model = AutoModelForSequenceClassification.from_pretrained(self._model_name)
            self._model.to(self._device)
            self._model.eval()
        return self._model

    def predict(self, texts: list[str]) -> list[float]:
        """Return sentiment scores in [-1.0, 1.0] for each text.

        -1.0 = very negative, 0.0 = neutral, 1.0 = very positive.

        Args:
            texts: List of text strings to classify

        Returns:
            List of sentiment scores
        """
        if not texts:
            return []

        cleaned_texts = [self._preprocessor.clean(text) for text in texts]

        inputs = self.tokenizer(
            cleaned_texts,
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt",
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)

        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)

        stars = torch.arange(1, 6, dtype=torch.float32, device=self._device)
        weighted = (probs * stars).sum(dim=-1)

        normalized = (weighted - 3.0) / 2.0

        return normalized.cpu().tolist()

    def predict_single(self, text: str) -> float:
        """Predict sentiment for a single text.

        Args:
            text: Text string to classify

        Returns:
            Sentiment score in [-1.0, 1.0]
        """
        return self.predict([text])[0]

    def predict_with_confidence(
        self,
        texts: list[str],
    ) -> list[dict[str, Any]]:
        """Predict sentiment with confidence scores.

        Args:
            texts: List of text strings to classify

        Returns:
            List of dicts with score, confidence, and label
        """
        if not texts:
            return []

        cleaned_texts = [self._preprocessor.clean(text) for text in texts]

        inputs = self.tokenizer(
            cleaned_texts,
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors="pt",
        )
        inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)

        logits = outputs.logits
        probs = torch.softmax(logits, dim=-1)

        stars = torch.arange(1, 6, dtype=torch.float32, device=self._device)
        weighted = (probs * stars).sum(dim=-1)
        normalized = (weighted - 3.0) / 2.0

        confidence = probs.max(dim=-1).values

        results = []
        for i, text in enumerate(texts):
            score = normalized[i].item()
            conf = confidence[i].item()

            if score > 0.3:
                label = "positive"
            elif score < -0.3:
                label = "negative"
            else:
                label = "neutral"

            results.append(
                {
                    "text": text[:100],
                    "score": round(score, 4),
                    "confidence": round(conf, 4),
                    "label": label,
                }
            )

        return results

    def predict_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> list[float]:
        """Predict sentiment for large batches.

        Args:
            texts: List of text strings
            batch_size: Batch size for processing

        Returns:
            List of sentiment scores
        """
        results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_results = self.predict(batch)
            results.extend(batch_results)
        return results


class SentimentAggregator:
    """Aggregate sentiment scores from multiple sources."""

    def __init__(
        self,
        twitter_weight: float = 0.3,
        reddit_weight: float = 0.3,
        news_weight: float = 0.4,
    ) -> None:
        self.weights = {
            "twitter": twitter_weight,
            "reddit": reddit_weight,
            "news": news_weight,
        }

    def aggregate(
        self,
        sentiments: dict[str, list[float]],
    ) -> dict[str, float]:
        """Aggregate sentiments from different sources.

        Args:
            sentiments: Dict of source -> list of sentiment scores

        Returns:
            Dict with aggregated stats
        """
        results = {}

        for source, scores in sentiments.items():
            if not scores:
                continue

            weight = self.weights.get(source, 0.25)

            results[f"{source}_mean"] = sum(scores) / len(scores)
            results[f"{source}_count"] = len(scores)

            positive = sum(1 for s in scores if s > 0.1)
            negative = sum(1 for s in scores if s < -0.1)
            results[f"{source}_positive_pct"] = positive / len(scores)
            results[f"{source}_negative_pct"] = negative / len(scores)

        total_weighted = 0.0
        total_count = 0
        for source, scores in sentiments.items():
            if not scores:
                continue
            weight = self.weights.get(source, 0.25)
            avg = sum(scores) / len(scores)
            total_weighted += avg * weight
            total_count += len(scores)

        if total_count > 0:
            results["overall_weighted"] = total_weighted

        return results


def classify_sentiment(texts: list[str]) -> list[float]:
    """Convenience function for sentiment classification."""
    classifier = SentimentClassifier()
    return classifier.predict(texts)
