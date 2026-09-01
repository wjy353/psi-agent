"""Diff tool — compare a file against another file or against expected content."""

from __future__ import annotations

import difflib

import anyio

_MAX_OUTPUT_CHARS = 4000


async def diff(
    file_path: str,
    path_b: str | None = None,
    expected_content: str | None = None,
) -> str:
    """Show a unified diff between a file and a second file or expected content.

    Use it to inspect what changed after edits, or to compare a deliverable
    against content you expect it to contain. Exactly one of path_b and
    expected_content must be provided.

    Args:
        file_path: Path of the file to compare (left side of the diff).
        path_b: Path of a second file to compare against. Omit if using
            expected_content.
        expected_content: Inline text to compare against. Omit if using path_b.

    Returns:
        Unified diff with line numbers, or an error message.
    """
    if (path_b is None) == (expected_content is None):
        return "[Error] Provide exactly one of path_b or expected_content"

    left_path = anyio.Path(file_path)
    if not await left_path.exists():
        return f"[Error] File not found: {file_path}"
    if not await left_path.is_file():
        return f"[Error] Not a file: {file_path}"

    try:
        left_text = await left_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"[Error] Cannot read {file_path}: {exc}"

    if path_b is not None:
        right_path = anyio.Path(path_b)
        if not await right_path.exists():
            return f"[Error] File not found: {path_b}"
        if not await right_path.is_file():
            return f"[Error] Not a file: {path_b}"
        try:
            right_text = await right_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"[Error] Cannot read {path_b}: {exc}"
        right_label = path_b
    else:
        right_text = expected_content or ""
        right_label = "expected_content"

    if left_text == right_text:
        return f"[OK] No differences between {file_path} and {right_label}"

    diff_lines = list(
        difflib.unified_diff(
            left_text.splitlines(keepends=True),
            right_text.splitlines(keepends=True),
            fromfile=file_path,
            tofile=right_label,
            lineterm="",
        )
    )
    result = "\n".join(diff_lines)
    if len(result) > _MAX_OUTPUT_CHARS:
        result = result[:_MAX_OUTPUT_CHARS] + f"\n[... diff truncated at {_MAX_OUTPUT_CHARS} characters]"
    return result
