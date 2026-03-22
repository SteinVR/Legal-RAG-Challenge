# About This Directory
Purpose: Packaged configuration mirror used when repo-level configs are unavailable.
Contains: The same config family structure exposed under `configs/`.
Start Here: Compare this tree to the repo-level `configs/` tree if you are debugging config resolution.
Key Files/Dirs: `baseline/`.
Notes: `src/common/config.py` prefers the repo copy first and falls back to this packaged copy.
