# Answering LLM Input: Full Concrete Example

This file shows one concrete answering request assembled by the current code. The LLM-visible prompt text is separated from the Responses API envelope because `model`, `reasoning`, and `max_output_tokens` are provider/API parameters, not prompt text.

## Request Assembly Diagram

`QuestionRecord(id, question, answer_type)` -> `AnsweringService.answer_question(question, allow_decomposition=False)` -> `extract_query_metadata(question)` -> `retriever.retrieve(question, query_metadata)` -> `_coerce_retrieval_payload(retrieval_output)` -> `_PageCandidate(doc_id, page_numbers, text)` -> `_pass_a_pages_from_retrieval_payload(retrieval_output, pages, config)` -> `_provider_evidence_page(page)` -> `evidence_pages[]`

`src/resources/prompts/answering/system.md` -> `_load_structured_system_prompt()` -> `_STRUCTURED_SYSTEM_PROMPT`

`answer_type` -> `ANSWER_SCHEMA_REGISTRY[answer_type]` -> `answer_schema.model_json_schema()` -> `_strict_openai_schema(answer_schema.model_json_schema())` -> `text.format.json_schema`

`config.answering.reasoning_effort_by_type[answer_type]` -> `reasoning.effort`

`CodexAnsweringProvider.model` + `reasoning.effort` + `_STRUCTURED_SYSTEM_PROMPT` + `_build_structured_user_prompt(question, answer_type, evidence_pages)` + `text.format.json_schema` + `max_output_tokens` -> `POST /v1/responses` request body

## Exact LLM-Visible Input

API message field: `role = system` (not prompt text). Exact `content[0].text`:

```text
You are the answering specialist in a legal RAG pipeline. Think of yourself as joining a careful legal research team: your role is to turn the provided evidence into one concise, schema-valid answer, not to chat or speculate.

Context:
- The Evidence list in the user message is your complete candidate set for answering and page attribution.
- Each Evidence item has a 1-based index, document id, page reference, and extracted text.
- Return exactly one JSON object that follows the supplied schema.

Answering rules:
- Answer strictly from Evidence; do not use outside knowledge.
- Every claim in final_answer must be directly supported by Evidence.
- Do not reference pages outside the Evidence list.
- Support may be distributed across multiple Evidence items or pages; that is still valid support.
- Set is_answerable=false only when no Evidence item directly supports any defensible answer.
- If at least one Evidence item supports a defensible answer, set is_answerable=true.
- Use null only when the schema permits null and the evidence is insufficient.
- For free_text with is_answerable=false, use this exact final_answer: "There is no information on this question in the provided documents."
- For non-free_text with is_answerable=false, final_answer must be null.
- For dates, always use ISO-8601 format: YYYY-MM-DD.

Evidence selection:
- relevant_evidence_indices must contain the 1-based indices of every Evidence item that directly supports the answer.
- relevant_pages must contain the page numbers corresponding to the selected supporting Evidence.
- If no Evidence item explicitly supports the answer, set relevant_evidence_indices=[] and relevant_pages=[].
- Prioritize evidence recall: include every directly supporting Evidence item.
- When uncertain between a narrower and broader supporting set, choose the broader supported set.

Final self-review:
- Draft the answer.
- Verify that final_answer is directly supported by the selected Evidence.
- Verify that relevant_evidence_indices and relevant_pages align with that support.
- Then finalize the JSON object.
```

API message field: `role = user` (not prompt text). Exact `content[0].text`:

```text
Answer type: number
Question: How many days are allowed to file the notice?
Evidence:
[1] doc_id=synthetic_law; pages=2; text=Under Article 8 of the law, the notice must be filed within 30 days.
```

## Exact Model-Facing Output Constraint

This JSON schema is not prompt text. It is sent through Responses API structured-output controls and constrains the model output.

```json
{
  "additionalProperties": false,
  "properties": {
    "is_answerable": {
      "title": "Is Answerable",
      "type": "boolean"
    },
    "relevant_evidence_indices": {
      "items": {
        "type": "integer"
      },
      "title": "Relevant Evidence Indices",
      "type": "array"
    },
    "relevant_pages": {
      "items": {
        "type": "integer"
      },
      "title": "Relevant Pages",
      "type": "array"
    },
    "reasoning_summary": {
      "title": "Reasoning Summary",
      "type": "string"
    },
    "confidence": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Confidence"
    },
    "final_answer": {
      "anyOf": [
        {
          "type": "integer"
        },
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "title": "Final Answer"
    }
  },
  "required": [
    "confidence",
    "final_answer",
    "is_answerable",
    "reasoning_summary",
    "relevant_evidence_indices",
    "relevant_pages"
  ],
  "title": "NumberAnswerSchema",
  "type": "object"
}
```

## Exact Responses API Request Body, Not LLM Prompt Text

```json
{
  "model": "gpt-5.4-mini",
  "reasoning": {
    "effort": "high"
  },
  "input": [
    {
      "role": "system",
      "content": [
        {
          "type": "input_text",
          "text": "You are the answering specialist in a legal RAG pipeline. Think of yourself as joining a careful legal research team: your role is to turn the provided evidence into one concise, schema-valid answer, not to chat or speculate.\n\nContext:\n- The Evidence list in the user message is your complete candidate set for answering and page attribution.\n- Each Evidence item has a 1-based index, document id, page reference, and extracted text.\n- Return exactly one JSON object that follows the supplied schema.\n\nAnswering rules:\n- Answer strictly from Evidence; do not use outside knowledge.\n- Every claim in final_answer must be directly supported by Evidence.\n- Do not reference pages outside the Evidence list.\n- Support may be distributed across multiple Evidence items or pages; that is still valid support.\n- Set is_answerable=false only when no Evidence item directly supports any defensible answer.\n- If at least one Evidence item supports a defensible answer, set is_answerable=true.\n- Use null only when the schema permits null and the evidence is insufficient.\n- For free_text with is_answerable=false, use this exact final_answer: \"There is no information on this question in the provided documents.\"\n- For non-free_text with is_answerable=false, final_answer must be null.\n- For dates, always use ISO-8601 format: YYYY-MM-DD.\n\nEvidence selection:\n- relevant_evidence_indices must contain the 1-based indices of every Evidence item that directly supports the answer.\n- relevant_pages must contain the page numbers corresponding to the selected supporting Evidence.\n- If no Evidence item explicitly supports the answer, set relevant_evidence_indices=[] and relevant_pages=[].\n- Prioritize evidence recall: include every directly supporting Evidence item.\n- When uncertain between a narrower and broader supporting set, choose the broader supported set.\n\nFinal self-review:\n- Draft the answer.\n- Verify that final_answer is directly supported by the selected Evidence.\n- Verify that relevant_evidence_indices and relevant_pages align with that support.\n- Then finalize the JSON object."
        }
      ]
    },
    {
      "role": "user",
      "content": [
        {
          "type": "input_text",
          "text": "Answer type: number\nQuestion: How many days are allowed to file the notice?\nEvidence:\n[1] doc_id=synthetic_law; pages=2; text=Under Article 8 of the law, the notice must be filed within 30 days."
        }
      ]
    }
  ],
  "text": {
    "format": {
      "type": "json_schema",
      "name": "number_answer",
      "schema": {
        "additionalProperties": false,
        "properties": {
          "is_answerable": {
            "title": "Is Answerable",
            "type": "boolean"
          },
          "relevant_evidence_indices": {
            "items": {
              "type": "integer"
            },
            "title": "Relevant Evidence Indices",
            "type": "array"
          },
          "relevant_pages": {
            "items": {
              "type": "integer"
            },
            "title": "Relevant Pages",
            "type": "array"
          },
          "reasoning_summary": {
            "title": "Reasoning Summary",
            "type": "string"
          },
          "confidence": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Confidence"
          },
          "final_answer": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "title": "Final Answer"
          }
        },
        "required": [
          "confidence",
          "final_answer",
          "is_answerable",
          "reasoning_summary",
          "relevant_evidence_indices",
          "relevant_pages"
        ],
        "title": "NumberAnswerSchema",
        "type": "object"
      },
      "strict": true
    }
  },
  "max_output_tokens": 2048
}
```

## Example Valid Model Output For This Request

```json
{
  "is_answerable": true,
  "final_answer": 30,
  "relevant_evidence_indices": [
    1
  ],
  "relevant_pages": [
    2
  ],
  "reasoning_summary": "The evidence states that the notice must be filed within 30 days.",
  "confidence": 0.9
}
```

## Post-LLM Fields Used Downstream

`relevant_evidence_indices` -> `_safe_relevant_evidence_pairs(pages, relevant_evidence_indices)` -> supporting `(doc_id, page_number)` pairs

`relevant_pages` -> `_safe_relevant_page_pairs(pages, relevant_pages)` -> supporting `(doc_id, page_number)` pairs when page numbers are unambiguous

`final_answer` + `confidence` + supporting pages -> typed/free-text guardrails -> `finalize_page_attribution(answer, answer_type, raw_retrieved_chunk_pages, pass_a_pages, solver_reported_pages, supported_page_pairs, answer_supported, is_no_answer, config)` -> final `AnswerResult`
