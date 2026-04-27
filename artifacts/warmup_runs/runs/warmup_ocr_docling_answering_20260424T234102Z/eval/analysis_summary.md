# Warmup OCR Docling Analysis
Run: `warmup_ocr_docling_answering_20260424T234102Z`
## Status
- Answers: 100; traces: 100; validation valid: `True`; malformed: 0; errors: 0; warnings: 0.
- Build-submission log levels: {'INFO': 24, 'WARNING': 3}; parse retries: 3 warning events, all recovered by successful command completion.
- Stage durations from runtime log: corpus 0.2s, index 160.5s, QA 603.7s.
## Current Metrics
| metric | value |
|---|---:|
| total_score | 0.6946790505691504 |
| deterministic | 0.8857142857142857 |
| assistant | 0.9866666666666667 |
| grounding | 0.8062985975061234 |
| telemetry | 1.0 |
| ttft_multiplier | 0.9405736848917964 |
| ttft_ms | 6031.919395270162 |
| scored_questions | 100 |
| deterministic_questions | 70 |
| free_text_questions | 30 |
## Previous Run Comparison
| run | total | det | asst | ground | telemetry | ttft_mult | ttft_ms | delta_total_vs_ocr |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| submission_e2e_20260408_gen_filter | 0.733242 | 0.942857 | 0.986667 | 0.820187 | 1.000 | 0.935141 | 6246.5 | -0.038563 |
| submission_e2e_20260408_warmup_retry_answering | 0.734217 | 0.942857 | 0.986667 | 0.819053 | 1.000 | 0.937680 | 6224.9 | -0.039538 |
| submission_e2e_20260409_warmup_no_decomposition | 0.718465 | 0.942857 | 0.986667 | 0.788431 | 1.000 | 0.953199 | 5039.4 | -0.023786 |
| submission_e2e_20260409_warmup_no_solver_high | 0.731348 | 0.957143 | 0.986667 | 0.805153 | 1.000 | 0.940305 | 7273.7 | -0.036669 |
| submission_e2e_20260424_solver_narrowing_high | 0.746614 | 0.942857 | 0.986667 | 0.829457 | 1.000 | 0.941552 | 6352.1 | -0.051935 |
| submission_e2e_20260424_solver_narrowing_no_guard | 0.759380 | 0.942857 | 0.986667 | 0.847201 | 1.000 | 0.937594 | 6390.5 | -0.064701 |
| warmup_ocr_docling_answering_20260424T234102Z | 0.694679 | 0.885714 | 0.986667 | 0.806299 | 1.000 | 0.940574 | 6031.9 | 0.000000 |
## Deltas Vs Solver Narrowing No Guard
| component | delta |
|---|---:|
| deterministic | -0.057143 |
| assistant | 0.000000 |
| grounding | -0.040902 |
| telemetry | 0.000000 |
| ttft_multiplier | 0.002979 |
| total_score | -0.064701 |
## Slice Deltas Vs Solver Narrowing No Guard
| slice | questions | total_delta | det_delta | grounding_delta | ttft_mult_delta |
|---|---:|---:|---:|---:|---:|
| answer_type:boolean | 32 | -0.048146 | -0.062500 | -0.022562 | 0.003247 |
| answer_type:date | 1 | -0.003149 | 0.000000 | 0.000000 | -0.004498 |
| answer_type:free_text | 30 | -0.020868 | 0.000000 | -0.076143 | 0.002524 |
| answer_type:name | 15 | 0.010849 | 0.000000 | 0.008545 | 0.014132 |
| answer_type:names | 5 | -0.017900 | 0.000000 | -0.024242 | -0.002267 |
| answer_type:number | 17 | -0.117887 | -0.117647 | -0.064171 | -0.004580 |
| difficulty:easy | 70 | -0.065193 | -0.057692 | -0.037333 | 0.002153 |
| difficulty:hard | 6 | -0.045738 | 0.000000 | -0.043155 | -0.014424 |
| difficulty:medium | 24 | -0.068578 | -0.066667 | -0.050748 | 0.009740 |
## Corpus / Structure
- Corpus: 30 docs, 590 pages, failed docs 0, empty text pages 0.
- Source modes: `{'ocr': 590}`; triage: `{'scan': 590}`; parser provenance: `{'opendataloader:hybrid': 30}`.
- Structural enrichment: heading pages 589, role pages 589, source block ids 7828, blocks {'text': 590, 'table': 4932}, raw ODL nodes sum 7828, tables sum 80.
- Index: 7378 chunks, 590 pages, built_at `2026-04-24T23:43:44.829027+00:00`.
## Deterministic Misses
| type | difficulty | qid | gold | candidate | grounding | question |
|---|---|---|---|---|---:|---|
| boolean | easy | `5cb2e9e63192` | `False` | `None` | 0.878788 | Does the DIFC law numbered DIFC Law No. 7 of 2018 deal with insolvency and preferential debts? |
| boolean | medium | `802d12a65530` | `False` | `None` | 0.000000 | Based on the second page of the document, was the Claimant's application for continuation of the ASI Order granted by the court in case ARB 034/2025? |
| name | easy | `5046b4e3fa11` | `Claim No. ENF-316-2023/2` | `ENF 316/2023` | 0.878788 | According to page 2 of the judgment, from which specific claim number did the appeal in CA 009/2024 originate? |
| name | easy | `6b20dd63f6b2` | `SCT 295/2025` | `Olexa v Odon` | 0.783784 | Which case has an earlier Date of Issue: SCT 169/2025 or SCT 295/2025? |
| name | easy | `8de44b7964cd` | `SCT 169/2025` | `None` | 0.878788 | Identify the case with the higher monetary claim: SCT 169/2025 or SCT 295/2025? |
| number | medium | `6c32a091c710` | `405351504` | `None` | 1.000000 | What was the claim value in AED referenced in the appeal judgment CA 005/2025? |
| number | easy | `922dcd5ae0d2` | `4` | `None` | 0.878788 | What official law number is stated on the cover page of the DIFC Trust Law? |
| number | easy | `ff1b357588e9` | `3` | `None` | 0.878788 | According to the title page of the DIFC Law on the Application of Civil and Commercial Laws, what is its official law number? |
## Lowest Current Grounding
| type | qid | grounding | det | assistant | question |
|---|---|---:|---:|---:|---|
| free_text | `9f48d8eca6d1` | 0.000000 |  | 1.000 | According to Article 2 of the DIFC Personal Property Law 2005, who made this Law? |
| boolean | `802d12a65530` | 0.000000 | 0.000 |  | Based on the second page of the document, was the Claimant's application for continuation of the ASI Order granted by the court in case ARB 034/2025? |
| free_text | `b2fcc22c0bfc` | 0.000000 |  | 1.000 | On what date was the DIFC Personal Property Law 2005 enacted? |
| free_text | `89f4b2e86cf7` | 0.000000 |  | 1.000 | Were the Miranda rights properly administered in case ENF 269/2023? |
| free_text | `0a414e1d999b` | 0.000000 |  | 1.000 | What did the jury decide in case ENF 269/2023? |
| free_text | `84a7c3564026` | 0.000000 |  | 1.000 | What was the plea bargain in case ARB 034/2025? |
| free_text | `84941458c4ad` | 0.000000 |  | 1.000 | Is there any information about parole hearings in case CFI 057/2025? |
| free_text | `cd69f5dfe06d` | 0.000000 |  | 1.000 | What is the purpose of Article 9(1) of the Foundations Law? |
| free_text | `6863a7f4a5e7` | 0.500000 |  | 1.000 | Under the Foundations Law DIFC Law No. 3 of 2018, what is the maximum fine for failing to provide a copy of an assignment of rights to the Registered Agent or R |
| free_text | `a341025df493` | 0.500000 |  | 1.000 | According to Article 12(4) of the Common Reporting Standard Law and Article 18(2)(b) of the General Partnership Law, what are the retention periods for records? |
## Artifact Paths
- run_dir: `artifacts/warmup_runs/runs/warmup_ocr_docling_answering_20260424T234102Z`
- submission: `artifacts/warmup_runs/runs/warmup_ocr_docling_answering_20260424T234102Z/submission/submission.json`
- qa_checkpoint: `artifacts/warmup_runs/runs/warmup_ocr_docling_answering_20260424T234102Z/submission/qa_checkpoint.json`
- trace_manifest: `artifacts/warmup_runs/runs/warmup_ocr_docling_answering_20260424T234102Z/submission/trace_manifest.json`
- traces_dir: `artifacts/warmup_runs/runs/warmup_ocr_docling_answering_20260424T234102Z/submission/traces`
- validation_report: `artifacts/warmup_runs/runs/warmup_ocr_docling_answering_20260424T234102Z/eval/validation_report.json`
- benchmark_report: `artifacts/warmup_runs/runs/warmup_ocr_docling_answering_20260424T234102Z/eval/benchmark_report.json`
- compare_reports.submission_e2e_20260424_solver_narrowing_no_guard: `artifacts/warmup_runs/runs/warmup_ocr_docling_answering_20260424T234102Z/eval/compare_vs_submission_e2e_20260424_solver_narrowing_no_guard.json`
- compare_reports.submission_e2e_20260424_solver_narrowing_high: `artifacts/warmup_runs/runs/warmup_ocr_docling_answering_20260424T234102Z/eval/compare_vs_submission_e2e_20260424_solver_narrowing_high.json`
- compare_reports.submission_e2e_20260408_gen_filter: `artifacts/warmup_runs/runs/warmup_ocr_docling_answering_20260424T234102Z/eval/compare_vs_submission_e2e_20260408_gen_filter.json`
- corpus_manifest: `data/warmup-ocr/corpus/corpus_manifest.json`
- index_manifest: `data/warmup-ocr/index/index_manifest.json`
