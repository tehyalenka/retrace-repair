"""Benchmarks for Retrace.

Active benchmark suite:
    benchmarks.v18: Current multi-arm, budget-bounded, leakage-resistant benchmark suite with 22 enterprise tasks.

Historical benchmark iterations:
    Located in `benchmarks/archive/` (v09, v11, v15, v16, v19, v20, v21, v22, v23, v25, v27, v28, v30).
"""
import sys
from pathlib import Path

# Extend package search path so historical suites in archive/ remain directly importable
_ARCHIVE_PATH = str(Path(__file__).parent / "archive")
if _ARCHIVE_PATH not in __path__:
    __path__.append(_ARCHIVE_PATH)
