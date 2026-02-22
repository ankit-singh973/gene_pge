"""
Input validation & sanitization for gene symbols.

Valid HGNC gene symbols:
  - 1–20 alphanumeric characters + hyphens/underscores
  - Must NOT be purely numeric
  - Must NOT contain whitespace or special characters
"""
from __future__ import annotations
import re


# Matches valid gene symbols: letters/digits/hyphens, starts with a letter
_VALID_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9\-_]{0,19}$")
_NUMERIC_ONLY_RE = re.compile(r"^\d+$")


def sanitize_and_validate(raw: str) -> tuple[str, str | None]:
    """
    Returns (normalized_symbol, error_message).
    error_message is None if valid.
    """
    if not isinstance(raw, str):
        return "", "Invalid HGNC gene symbol"

    # Strip whitespace and uppercase
    symbol = raw.strip().upper()

    if not symbol:
        return "", "Invalid HGNC gene symbol"

    # Reject purely numeric
    if _NUMERIC_ONLY_RE.match(symbol):
        return "", "Invalid HGNC gene symbol"

    # Check format
    if not _VALID_SYMBOL_RE.match(symbol):
        return "", "Invalid HGNC gene symbol"

    return symbol, None
