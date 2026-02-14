"""modules/playbook/condition_evaluator.py — Safe playbook branching evaluator.

NEVER uses eval(). Parses conditions into simple rules with field/op/value.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Supported operators
_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: _to_num(a) > _to_num(b),
    "<": lambda a, b: _to_num(a) < _to_num(b),
    ">=": lambda a, b: _to_num(a) >= _to_num(b),
    "<=": lambda a, b: _to_num(a) <= _to_num(b),
    "in": lambda a, b: a in b if isinstance(b, (list, tuple, set)) else str(a) in str(b),
    "contains": lambda a, b: b in a if isinstance(a, (list, tuple, set, str)) else False,
}

# Pattern: field op value, with optional AND joins
_CONDITION_PATTERN = re.compile(
    r"(\w+(?:\.\w+)*)\s*(==|!=|>=|<=|>|<|in|contains)\s*(.+?)(?:\s+AND\s+|$)",
    re.IGNORECASE,
)


def _to_num(val: Any) -> float:
    """Convert to number for comparison."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _parse_value(raw: str) -> Any:
    """Parse a value string into a Python value."""
    raw = raw.strip().strip("'\"")
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    # Check for list: [a, b, c]
    if raw.startswith("[") and raw.endswith("]"):
        items = [s.strip().strip("'\"") for s in raw[1:-1].split(",")]
        return items
    return raw


def _get_nested(context: dict, key: str) -> Any:
    """Get a value from context using dot notation (e.g., 'payload.outcome')."""
    parts = key.split(".")
    current = context
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def evaluate_condition(condition: str, context: dict) -> bool:
    """Evaluate a condition string against a context dict.

    Supported formats:
        "outcome == answered"
        "quiz_score >= 60"
        "outcome == answered AND sentiment == positive"
        "default"  (always True)

    Returns True if ALL parts of the condition match.
    """
    condition = condition.strip()

    # Special cases
    if condition.lower() == "default":
        return True
    if not condition:
        return True

    matches = _CONDITION_PATTERN.findall(condition)
    if not matches:
        logger.warning("Could not parse condition: %s", condition)
        return False

    for field, op, raw_value in matches:
        actual = _get_nested(context, field)
        expected = _parse_value(raw_value)
        op_func = _OPS.get(op.lower())
        if op_func is None:
            logger.warning("Unknown operator '%s' in condition: %s", op, condition)
            return False
        try:
            if not op_func(actual, expected):
                return False
        except (TypeError, ValueError):
            return False

    return True


def resolve_next_step(
    rules: list[dict],
    context: dict,
) -> dict | None:
    """Evaluate branching rules and return the first matching rule.

    Each rule: {"condition": str, "go_to_step": int} or {"condition": str, "action": str}

    Returns the first matching rule dict, or None if no rules match.
    """
    for rule in rules:
        condition = rule.get("condition", "default")
        if evaluate_condition(condition, context):
            return rule
    return None
