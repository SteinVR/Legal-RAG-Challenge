from __future__ import annotations

import json

import httpx
import pytest

from src.providers.codex_provider import CodexFreeTextProvider


def _json_request(request: httpx.Request) -> dict[str, object]:
    body = request.content.decode("utf-8")
    return json.loads(body)


def test_codex_provider_parses_structured_json_answer_payload() -> None:
    captured_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/responses")
        captured_payloads.append(_json_request(request))
        return httpx.Response(
            status_code=200,
            json={
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": '{"answer": "Payment must be made within 10 days.", "confidence": 0.82}',
                            }
                        ]
                    }
                ]
            },
        )

    provider = CodexFreeTextProvider(
        api_key="test-token",
        transport=httpx.MockTransport(handler),
    )
    result = provider.generate(
        question="When is payment due?",
        evidence_pages=[
            {
                "doc_id": "alpha",
                "page_number": 2,
                "page_numbers": [2],
                "text": "Payment must be made within 10 days.",
            }
        ],
        max_chars=280,
    )

    assert result == {
        "answer": "Payment must be made within 10 days.",
        "confidence": pytest.approx(0.82),
    }
    assert captured_payloads
    assert captured_payloads[0]["model"] == provider.model
    assert "input" in captured_payloads[0]


def test_codex_provider_falls_back_to_plain_text_with_default_confidence() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={
                "output_text": "The tribunal dismissed the claim and ordered payment within 14 days.",
            },
        )

    provider = CodexFreeTextProvider(
        api_key="test-token",
        transport=httpx.MockTransport(handler),
    )
    result = provider.generate(
        question="Summarize the order.",
        evidence_pages=[],
        max_chars=40,
    )

    assert result["answer"] == "The tribunal dismissed the claim and ord"
    assert result["confidence"] == pytest.approx(0.5)
    assert len(result["answer"]) <= 40


def test_codex_provider_accepts_chat_completions_style_response_shape() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"choices": [{"message": {"content": "Grounded answer from evidence."}}]},
        )

    provider = CodexFreeTextProvider(
        api_key="test-token",
        transport=httpx.MockTransport(handler),
    )
    result = provider.generate(
        question="Summarize outcome.",
        evidence_pages=[],
        max_chars=280,
    )

    assert result == {
        "answer": "Grounded answer from evidence.",
        "confidence": pytest.approx(0.5),
    }


def test_codex_provider_requires_auth_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEX_OAUTH_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_API_KEY", raising=False)

    with pytest.raises(ValueError, match="token"):
        CodexFreeTextProvider(api_key=None)
