# Corpus4_2 Gold Set Spec

## Scope

- Source PDFs: `data/corpus_4_2/*.pdf`
- Working text views: `data/dev/gold/corpus4_2-100/text_views/*.md`
- Candidate question bundles: `data/dev/gold/corpus4_2-100/candidates/*.json`
- Selected questions: `data/dev/gold/corpus4_2-100/selected.questions.json`
- Question manifest: `data/dev/gold/corpus4_2-100/question_manifest.json`
- Shards: `data/dev/gold/corpus4_2-100/shards/part_01.questions.json` ... `part_05.questions.json`
- Draft outputs: `data/dev/gold/corpus4_2-100/drafts/part_XX.bundle.json`
- Review outputs: `data/dev/gold/corpus4_2-100/reviews/part_XX.bundle.json`

## Question Set Policy

- Build exactly `100` English questions from the 4-source corpus.
- Difficulty targets:
  - `easy = 50`
  - `medium = 35`
  - `hard = 15`
- Hard questions must be cross-document.
- Supported schema answer types remain:
  - `boolean`
  - `number`
  - `name`
  - `names`
  - `date`
  - `free_text`
- Maintain the user's requested answer-type mix as a bounded target:
  - `boolean = 18..22`
  - `number = 15..19`
  - `name = 13..17`
  - `names = 7..9`
  - `date = 7..9`
  - `free_text = 23..27`
- Include exactly `8` negative / unanswerable questions.
- Negative questions remain schema-compatible:
  - deterministic answer types: `answer = null`, `gold_retrieval = []`
  - `free_text`: use the canonical no-information sentence and `gold_retrieval = []`

## Stream Allocation

- `23` single-document questions from `3fa59589a91bf4913703ba0eedd08faa128948285b8a9d085bd7422248abe6c5` (`Securities Regulations`)
  - `13 easy`
  - `10 medium`
- `22` single-document questions from `536bbce854b9406cc22697e04fcdabd645e030c0e55b918252643b00e0b2b25f` (`Personal Property Law`)
  - `12 easy`
  - `10 medium`
- `20` single-document questions from `437568a801115019fe8278385c0484bdf07ab86f9a499ecaba2b7969b37c764b` (`CA 005/2025`)
  - `13 easy`
  - `7 medium`
- `20` single-document questions from `5d3df6d69fac3ef91e13ac835b43a35e9e434fbc7e72ea5c01e288d69b66e6a2` (`ENF 269/2023`)
  - `12 easy`
  - `8 medium`
- `15` hard cross-document questions:
  - `8` statute/regulation comparative questions across the two legal texts
  - `7` case-comparative questions across the two case files

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
