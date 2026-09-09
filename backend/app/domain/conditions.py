"""Condition evaluation.

Re-exports the evaluator built and tested in `pipeline/lib/conditions.py`.
It is imported rather than reimplemented: a test already pins that module's
`validate()` to the SQL validator `legal.validate_condition_ast`, and a second
implementation here would drift from both.
"""
import sys

from ..config import REPO_ROOT

if str(REPO_ROOT / "pipeline") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "pipeline"))

from lib.conditions import (  # noqa: E402,F401
    COMPARISONS, LOGICAL, OPS, PRESENCE,
    InvalidCondition, UnknownFact,
    evaluate, evaluate_safe, resolve, to_text, validate,
)

__all__ = ["evaluate", "evaluate_safe", "validate", "to_text", "resolve",
           "UnknownFact", "InvalidCondition", "OPS", "COMPARISONS", "LOGICAL", "PRESENCE"]
