"""Artifact validation tool — run a generic acceptance checklist on a deliverable."""

from __future__ import annotations

import re

import anyio


async def artifact_validate(
    path: str,
    must_exist: bool = True,
    non_empty: bool = True,
    contains: list[str] | None = None,
    not_contains: list[str] | None = None,
    exact_match: str | None = None,
    regex: str | None = None,
    min_size: int | None = None,
    max_size: int | None = None,
) -> str:
    """Validate a file or directory against a generic acceptance checklist.

    Each criterion provided in the call is checked and reported as PASS/FAIL;
    the final line gives the overall result. For files, contains, not_contains,
    exact_match and regex apply to the file text; for directories, they apply
    to the entry names. min_size and max_size apply to files only.

    Use it to verify the final deliverable against the exact requirements
    stated in the task (paths, expected content, formats), rather than
    inventing your own test cases.

    Args:
        path: Path of the file or directory to validate.
        must_exist: If True (default), the path must exist; if False, the
            check passes only when the path does NOT exist.
        non_empty: For a file, require non-zero size; for a directory,
            require at least one entry.
        contains: List of substrings that must all be present.
        not_contains: List of substrings that must all be absent.
        exact_match: Require the full text to equal this string.
        regex: Require a regex to match somewhere in the text.
        min_size: Require file size in bytes to be at least this value.
        max_size: Require file size in bytes to be at most this value.

    Returns:
        A PASS/FAIL report per check plus an overall result line.
    """
    checks: list[tuple[str, bool]] = []

    target = anyio.Path(path)
    exists = await target.exists()
    if not must_exist:
        if not exists:
            return f"[PASS] path absent: {path}\n[RESULT] ALL PASS (1/1)"
        checks.append((f"path absent: {path}", False))
        return _format_report(checks)
    if not exists:
        return f"[FAIL] path exists: {path}\n[RESULT] FAIL (0/1) - path not found: {path}"

    checks.append((f"path exists: {path}", True))

    is_file = await target.is_file()
    is_dir = await target.is_dir()
    if not is_file and not is_dir:
        checks.append(("path is a file or directory", False))
        return _format_report(checks)

    text = ""
    size: int | None = None
    if is_file:
        try:
            size = (await target.stat()).st_size
            text = await target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return f"[Error] Cannot read {path}: {exc}"
        checks.append(("non-empty", size > 0))
    else:
        entries = sorted([entry.name async for entry in target.iterdir()])
        text = "\n".join(entries)
        checks.append(("non-empty", bool(entries)))

    for sub in contains or []:
        checks.append((f"contains {sub!r}", sub in text))
    for sub in not_contains or []:
        checks.append((f"not_contains {sub!r}", sub not in text))
    if exact_match is not None:
        checks.append(("exact_match", text == exact_match))
    if regex is not None:
        try:
            regex_ok = re.search(regex, text) is not None
        except re.error as exc:
            return f"[Error] Invalid regex {regex!r}: {exc}"
        checks.append((f"regex {regex!r}", regex_ok))
    if min_size is not None and is_file:
        checks.append((f"size >= {min_size} bytes", size is not None and size >= min_size))
    if max_size is not None and is_file:
        checks.append((f"size <= {max_size} bytes", size is not None and size <= max_size))

    return _format_report(checks)


def _format_report(checks: list[tuple[str, bool]]) -> str:
    """Render the PASS/FAIL report and overall result line."""
    lines: list[str] = []
    passed = 0
    for label, ok in checks:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {label}")
        if ok:
            passed += 1
    total = len(checks)
    result = f"[RESULT] {'ALL PASS' if passed == total else 'FAIL'} ({passed}/{total})"
    if passed < total:
        result += f" - {total - passed} check(s) failed"
    lines.append(result)
    return "\n".join(lines)
