# About This Directory
Purpose: Local validation, scoring, goldset, and dev benchmark logic.
Contains: Submission contracts, scoring code, validator code, goldset helpers, and the `dev_benchmark/` package.
Start Here: `contracts.py` for types, `validator.py` for schema checks, `scorer.py` for score math.
Key Files/Dirs: `contracts.py`, `validator.py`, `scorer.py`, `goldset.py`, `dev_benchmark/`.
Notes: This directory backs several CLI commands from `src/main.py`, so it is both a library layer and an operator workflow layer.
