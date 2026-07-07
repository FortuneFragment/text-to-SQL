from __future__ import annotations

import re


_VALID_INDEX_RE = re.compile(r"^(?![-_+])(?!(?:\.|\.\.)$)[a-z0-9][a-z0-9._-]{0,127}$")
_INVALID_INDEX_CHARS_RE = re.compile(r'[^a-z0-9._-]+')
_MULTI_SEPARATOR_RE = re.compile(r"[_-]{2,}")


def is_valid_index_name(value: str) -> bool:
    return bool(_VALID_INDEX_RE.match(str(value or "").strip()))


def normalize_index_name(
    value: str,
    *,
    fallback: str = "text2sql-kb",
    prefix: str = "kb",
    max_length: int = 128,
) -> str:
    text = str(value or "").strip().lower()
    text = _INVALID_INDEX_CHARS_RE.sub("-", text)
    text = _MULTI_SEPARATOR_RE.sub("-", text).strip(".-_+")

    if not text:
        text = str(fallback or "").strip().lower()
        text = _INVALID_INDEX_CHARS_RE.sub("-", text)
        text = _MULTI_SEPARATOR_RE.sub("-", text).strip(".-_+")

    if not text or text in {".", ".."}:
        text = "text2sql-kb"

    if text[0] in {"-", "_", "+"}:
        safe_prefix = _INVALID_INDEX_CHARS_RE.sub("-", str(prefix or "kb").lower()).strip(".-_+")
        text = f"{safe_prefix or 'kb'}-{text.strip('-_+')}"

    text = text[:max_length].strip(".-_+")
    if not text or text in {".", ".."}:
        text = "text2sql-kb"

    if text[0] in {"-", "_", "+"}:
        text = f"kb-{text.strip('-_+')}"[:max_length].strip(".-_+")

    return text or "text2sql-kb"
