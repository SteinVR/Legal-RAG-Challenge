# `scripts/`

Operational helper scripts used for environment bootstrap and smoke/audit workflows.

## File graph

```text
scripts/
├── 01b_install_opendataloader_runtime.sh
├── 02_download_models.sh
├── 06_build_submission.sh
├── audit_challenge_corpus.py
└── smoke_test_w4e.py
```

## File map

- `01b_install_opendataloader_runtime.sh`: Install OpenDataLoader runtime prerequisites.
- `02_download_models.sh`: Pull required local model artifacts for offline execution.
- `06_build_submission.sh`: Run submission build workflow wrapper.
- `audit_challenge_corpus.py`: Corpus audit utility for data/coverage sanity checks.
- `smoke_test_w4e.py`: Smoke test harness for the W4E pipeline flow.
