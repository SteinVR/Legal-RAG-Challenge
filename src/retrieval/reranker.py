"""Qwen3-oriented reranking behavior for retrieval candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.common.schemas import QuestionRecord

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
DEFAULT_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "for",
        "how",
        "in",
        "is",
        "of",
        "or",
        "the",
        "to",
        "what",
        "which",
        "who",
    }
)


class QwenRerankerBackend(Protocol):
    """Backend interface for scoring query/document pairs with a reranker model."""

    def score(self, query: str, documents: list[str]) -> list[float]:
        """Return one rerank score per candidate document."""


class CandidateReranker(Protocol):
    """Fallback interface matching the retrieval-service reranker contract."""

    def rerank(
        self,
        question: QuestionRecord,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Return reranked candidates."""


@dataclass(slots=True)
class TransformersQwenRerankerBackend:
    """Lazy Transformers backend for `Qwen/Qwen3-Reranker-0.6B`."""

    model_name: str = "Qwen/Qwen3-Reranker-0.6B"
    device: str | None = None
    batch_size: int = 8
    max_length: int = 1024
    trust_remote_code: bool = True
    _tokenizer: Any = field(default=None, init=False, repr=False)
    _model: Any = field(default=None, init=False, repr=False)
    _runtime_device: str | None = field(default=None, init=False, repr=False)

    def score(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []

        self._ensure_loaded()

        import torch

        scores: list[float] = []
        for start in range(0, len(documents), self.batch_size):
            batch_documents = documents[start : start + self.batch_size]
            inputs = self._tokenizer(
                [query] * len(batch_documents),
                batch_documents,
                padding=True,
                truncation=True,
                max_length=self.max_length,
                return_tensors="pt",
            )
            model_inputs = {
                key: value.to(self._runtime_device)
                for key, value in inputs.items()
            }

            with torch.no_grad():
                outputs = self._model(**model_inputs)
                logits = _extract_logits(outputs)
                batch_scores = logits.detach().float().cpu().tolist()

            if isinstance(batch_scores, list):
                scores.extend(float(score) for score in batch_scores)
            else:
                scores.append(float(batch_scores))

        return scores

    def _ensure_loaded(self) -> None:
        if self._model is not None and self._tokenizer is not None and self._runtime_device is not None:
            return

        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        runtime_device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
        tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            trust_remote_code=self.trust_remote_code,
        )
        model = AutoModelForSequenceClassification.from_pretrained(
            self.model_name,
            trust_remote_code=self.trust_remote_code,
        )
        model.to(runtime_device)
        model.eval()

        self._tokenizer = tokenizer
        self._model = model
        self._runtime_device = runtime_device


@dataclass(slots=True)
class QwenReranker:
    """Baseline reranker that routes scoring through a Qwen3 model backend."""

    backend: QwenRerankerBackend = field(default_factory=TransformersQwenRerankerBackend)
    fallback_reranker: CandidateReranker | None = None

    def rerank(
        self,
        question: QuestionRecord,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        result_limit = max(int(top_k), 0)
        if result_limit == 0 or not candidates:
            return []

        try:
            scores = self.backend.score(
                question.question,
                [str(candidate.get("text") or "") for candidate in candidates],
            )
            if len(scores) != len(candidates):
                raise ValueError("Qwen reranker backend returned a mismatched number of scores.")
            reranked = [
                {
                    **dict(candidate),
                    "rerank_score": float(score),
                }
                for candidate, score in zip(candidates, scores, strict=True)
            ]
        except Exception:
            if self.fallback_reranker is None:
                raise
            return self.fallback_reranker.rerank(question, candidates, result_limit)

        reranked.sort(
            key=lambda candidate: (
                -candidate["rerank_score"],
                -_score(candidate.get("retrieval_score")),
                str(candidate.get("chunk_id") or ""),
            ),
        )
        return reranked[:result_limit]


@dataclass(slots=True)
class LexicalFallbackReranker:
    """Explicit lightweight fallback for environments without a model backend."""

    lexical_weight: float = 0.7
    retrieval_weight: float = 0.3
    stopwords: frozenset[str] = field(default_factory=lambda: DEFAULT_STOPWORDS)

    def rerank(
        self,
        question: QuestionRecord,
        candidates: list[dict[str, Any]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        result_limit = max(int(top_k), 0)
        query_tokens = self._tokenize(question.question)
        reranked: list[dict[str, Any]] = []

        for candidate in candidates:
            normalized = dict(candidate)
            retrieval_score = _score(candidate.get("retrieval_score"))
            overlap_score = self._overlap_score(query_tokens, self._tokenize(str(candidate.get("text") or "")))
            normalized["rerank_score"] = (overlap_score * self.lexical_weight) + (
                retrieval_score * self.retrieval_weight
            )
            reranked.append(normalized)

        reranked.sort(
            key=lambda candidate: (
                -candidate["rerank_score"],
                -_score(candidate.get("retrieval_score")),
                str(candidate.get("chunk_id") or ""),
            ),
        )
        return reranked[:result_limit]

    def _tokenize(self, text: str) -> set[str]:
        return {
            token
            for token in TOKEN_PATTERN.findall(text.lower())
            if token and token not in self.stopwords
        }

    def _overlap_score(self, query_tokens: set[str], candidate_tokens: set[str]) -> float:
        if not query_tokens or not candidate_tokens:
            return 0.0
        overlap = len(query_tokens & candidate_tokens)
        return overlap / len(query_tokens)


def _extract_logits(outputs: Any) -> Any:
    logits = getattr(outputs, "logits", outputs)
    if isinstance(logits, (tuple, list)):
        logits = logits[0]
    if hasattr(logits, "squeeze"):
        logits = logits.squeeze(-1)
    return logits


def _score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
