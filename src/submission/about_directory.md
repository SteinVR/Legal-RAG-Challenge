# About This Directory
Purpose: End-to-end execution, packaging, and platform interaction layer.
Contains: Phase sync helpers, build-submission orchestration, telemetry packing, packager, submit gate, and API client.
Start Here: `pipeline.py` for the full run, `sync.py` for phase-local paths, and `packager.py` plus `submit_gate.py` for final bundle logic.
Key Files/Dirs: `pipeline.py`, `sync.py`, `telemetry_packer.py`, `packager.py`, `submit_gate.py`, `api_client.py`.
Notes: If a task spans multiple components, this directory usually shows how they are wired together.
