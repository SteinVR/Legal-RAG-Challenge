# Corpus4 Gold Set Spec

## Scope

- Source PDFs: `data/corpus_4/*.pdf`
- Candidate question bundles: `data/dev/gold/corpus4-100/candidates/*.json`
- Full question pool: `data/dev/gold/corpus4-100/question_pool.questions.json`
- Pool manifest: `data/dev/gold/corpus4-100/question_pool_manifest.json`
- Selected questions: `data/dev/gold/corpus4-100/selected.questions.json`
- Shards: `data/dev/gold/corpus4-100/shards/part_01.questions.json` ... `part_05.questions.json`
- Draft outputs: `data/dev/gold/corpus4-100/drafts/part_XX.bundle.json`
- Review outputs: `data/dev/gold/corpus4-100/reviews/part_XX.bundle.json`

## Question Pool Policy

- Build `200` English questions from the 4-source corpus.
- Difficulty targets for the pool:
  - `easy = 100`
  - `medium = 70`
  - `hard = 30`
- Supported schema answer types remain:
  - `boolean`
  - `number`
  - `name`
  - `names`
  - `date`
  - `free_text`
- Maintain the user's requested answer-type mix as a soft target.
- Include exactly `15` negative / unanswerable questions in the 200-question pool.
- Negative questions remain schema-compatible:
  - deterministic answer types: `answer = null`, `gold_retrieval = []`
  - `free_text`: use the canonical no-information sentence and `gold_retrieval = []`

## Selection Policy

- Select the strongest `100` questions from the 200-question pool.
- Selection is quality-first, not quota-first.
- Exclude weak, duplicate, ambiguous, or reviewer-disputed questions before final selection.
- Keep minimum diversity floors in the selected 100:
  - all 4 source documents represented
  - all supported answer types represented where available
  - at least `25` medium questions
  - at least `10` hard questions

## Output Contract

Each draft/review file must remain a valid `GoldShardBundle` JSON object with:

- `shard_id`
- `status`: `draft` or `reviewed`
- `question_ids`
- `references`
- `assistant_scores`
- `findings`
- `notes`

For draft bundles:

- fill `references`
- keep `assistant_scores` empty
- keep `status = "draft"`

For reviewed bundles:

- fill corrected `references`
- fill `assistant_scores` for every `free_text` question in the shard
- use `status = "reviewed"`
- record disagreements/fixes in `findings`

## Final Merge Outputs

- Main gold artifact: merged `ReferenceAnswerRecord` benchmark/reference set
- Separate auxiliary artifact: merged review-time `assistant_scores` for `free_text`

Important:

- review `assistant_scores` are proxy evaluations of the reviewed draft answers
- they are not universal gold labels for arbitrary future submissions
- therefore the main merged gold benchmark should stay reference-first; export `assistant_scores` separately unless you explicitly need a fixed local benchmark bundle

## Reference Rules

Each `references[]` row must be a valid `ReferenceAnswerRecord` with:

- `question_id`
- `question`
- `answer_type`
- `answer`
- `gold_retrieval`
- `source_type`
- `difficulty`
- `tags`
- optional `notes`

Allowed `source_type` values:

- `statute`
- `case`
- `cross_case`

Allowed `difficulty` values:

- `easy`
- `medium`
- `hard`

Allowed tags:

- `deterministic`
- `free_text`
- `single_page`
- `multi_page`
- `single_document`
- `multi_document`
- `comparative`
- `negative`
- `table_lookup`
- `title_page`
- `entity_overlap`

## Canonical Answer Policy

For deterministic answer types:

- `number`: JSON number
- `boolean`: JSON boolean
- `name`: string
- `names`: list of strings
- `date`: `YYYY-MM-DD`

For unanswerable deterministic questions:

- `answer = null`
- `gold_retrieval = []`

For `free_text`:

- answer must be a non-empty string
- answer length must be `<= 280`
- answer must be grounded in the cited pages

For unanswerable `free_text` questions, use exactly:

`There is no information on this question in the provided documents.`

and set:

- `gold_retrieval = []`

## Grounding Policy

- `gold_retrieval` must be minimal-complete:
  - include every page needed to prove the answer
  - exclude extra pages that do not add necessary evidence
- For multi-document/comparative questions, cite all necessary documents/pages.
- For no-answer questions, keep retrieval empty.

## Review Policy

Reviewers must verify:

- answer value correctness
- exactness of `gold_retrieval`
- recall of `gold_retrieval`
- `source_type`
- `difficulty`
- `tags`
- `free_text` proxy `assistant_score`

Use `docs/evaluation/free_text_review_template.md` as the rubric for `assistant_scores`.
