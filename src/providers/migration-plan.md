# Migration Plan: `src/providers`

## Goal and non-goals

### Goal
- Harden `src/providers` into a clean provider abstraction layer with explicit separation between protocol surface, transport/client behavior, prompt/schema preparation, retry policy, and response parsing.
- Keep the provider boundary hot-swappable so answering and submission depend on protocols, not a single hardcoded implementation shape.
- Preserve fail-fast behavior for provider/schema contract breaks.

### Non-goals
- Do not embed answering-specific business rules inside providers.
- Do not let provider retries become silent quality degradation.
- Do not preserve one large mixed implementation file if responsibilities can be cleanly separated.

## Current boundary map
- `base.py` defines the main protocols and is already the right abstraction seam.
- `codex_provider.py` currently mixes free-text generation, structured generation, HTTP client construction, prompt building, schema strictness adjustment, retry policy, response parsing, and confidence normalization.
- `main.py` and submission wiring still know too much about the concrete Codex provider class.

## Target module split
- `base.py`: keep protocol definitions only.
- `transport.py`: HTTP client construction, auth/token resolution, request execution.
- `prompts.py`: free-text and structured prompt assembly.
- `schema_adapter.py`: strict OpenAI schema conversion and schema-shape validation.
- `response_parser.py`: response-text extraction, structured payload parsing, confidence normalization.
- `retry.py`: bounded retry policy and retryable error classification.
- `codex_free_text.py`: concrete free-text provider implementation using the shared modules.
- `codex_structured.py`: concrete structured provider implementation using the shared modules.
- `__init__.py`: export protocols and stable provider implementations only.

## Migration steps
1. Leave `base.py` unchanged except for any type tightening needed to support the extracted modules.
2. Move HTTP/auth logic into `transport.py`.
3. Move prompt-building helpers into `prompts.py`.
4. Move `_strict_openai_schema` and related schema handling into `schema_adapter.py`.
5. Move response parsing and confidence coercion into `response_parser.py`.
6. Move retry policy into `retry.py`.
7. Split concrete free-text and structured implementations into dedicated modules and reduce `codex_provider.py` to a temporary façade if needed during the migration window.
8. Update downstream wiring so answering and submission depend on provider protocols or provider factory injection instead of directly knowing Codex internals.

## Contracts to preserve and change

### Preserve
- `FreeTextProvider` and `StructuredOutputProvider` remain the public protocol contracts.
- Structured output generation, schema strictness, and confidence normalization behavior remain semantically stable.
- Provider errors continue to surface clearly and fail fast when schema or transport contracts are broken.

### Change
- `codex_provider.py` no longer owns every concern inline.
- Concrete provider implementations become smaller and built from shared provider infrastructure modules.
- Downstream code should stop instantiating concrete provider classes deep inside orchestration code.

## Logging and typing checklist
- Mandatory non-debug logs: `provider.request.start`, `provider.request.complete`, `provider.retry`, `provider.parse.complete`, `provider.schema.validation_failed`, `provider.failed`.
- Keep protocol signatures narrow and typed.
- Do not return ambiguous partially parsed payloads; parsing either succeeds into a typed mapping contract or raises an explicit error.

## Verification
- Run provider unit coverage for free-text and structured calls.
- Execute one answering smoke path using structured generation and inspect runtime logs and parsed outputs.
- Confirm schema strictness and retry behavior match current challenge-facing expectations.

## Acceptance criteria
- Provider protocols remain stable and concrete provider implementations are split by responsibility.
- Transport, prompts, schema adaptation, retry, and parsing are independent modules.
- Downstream stages depend on provider protocols or factories instead of concrete inlined provider knowledge.

## Risks and rollback
- The main risk is changing request/response semantics while extracting helpers. Roll back by replaying existing provider tests and restoring the previous concrete implementation only until the extracted helpers match current behavior.
- The second risk is duplicated logic between free-text and structured implementations. Keep shared modules authoritative rather than copying helper code into both classes.
