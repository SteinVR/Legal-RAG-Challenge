# Evaluation Ambiguities

## Unanswerable Retrieval

The public starter kit is internally inconsistent:

- `about_challenge_EVALUATION.md` says unanswerable questions should return `retrieved_chunk_pages: []`.
- The same file also says telemetry validation requires `retrieved_chunk_pages` to be present and non-empty.

Local baseline policy:

- Default policy: `allow_empty`
- Config key: `evaluation.unanswerable_retrieval_policy`
- Env override: `COMPETITION_UNANSWERABLE_RETRIEVAL_POLICY`

Allowed values:

- `allow_empty`: treats empty retrieval as valid for unanswerable cases and emits a warning.
- `require_non_empty`: treats empty retrieval as malformed telemetry.

## TTFT > 3000 ms

The public rules expose only a range (`0.85-0.99`) for TTFT above 3000 ms.
The local scorer uses a linear proxy:

- `3000 ms` -> `0.99`
- `10000 ms` -> `0.85`
- values above `10000 ms` clamp to `0.85`

This is a local approximation, not an organizer-confirmed formula.
