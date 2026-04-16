from __future__ import annotations

import re


_VALID_COLLECTION_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_NON_WORD_RE = re.compile(r"[^A-Za-z0-9_]")
_MULTI_UNDERSCORE_RE = re.compile(r"_+")


def is_valid_collection_name(value: str) -> bool:
    return bool(_VALID_COLLECTION_RE.match(str(value or "").strip()))


def normalize_collection_name(
    value: str,
    *,
    fallback: str = "text2sql_kb",
    prefix: str = "kb",
    max_length: int = 128,
) -> str:
    text = _NON_WORD_RE.sub("_", str(value or "").strip())
    text = _MULTI_UNDERSCORE_RE.sub("_", text).strip("_").lower()

    if not text:
        text = _NON_WORD_RE.sub("_", str(fallback or "").strip())
        text = _MULTI_UNDERSCORE_RE.sub("_", text).strip("_").lower()

    if not text:
        text = "text2sql_kb"

    if not re.match(r"^[A-Za-z_]", text):
        safe_prefix = _NON_WORD_RE.sub("_", str(prefix or "kb")).strip("_").lower() or "kb"
        text = f"{safe_prefix}_{text}"

    text = text[:max_length].strip("_")
    if not text:
        text = "text2sql_kb"

    if not re.match(r"^[A-Za-z_]", text):
        text = f"kb_{text}"
        text = text[:max_length]

    return text
