"""Analyzer: macro_jungle — measure preprocessor complexity per function.

Counts:
  - #ifdef/#if/#ifndef/#elif branches inside each function body
  - Function-like and object-like macro invocations
  - The cyclomatic-equivalent "preprocessor complexity"
"""
from __future__ import annotations

import os
import re
from typing import Iterable

from clang import cindex


_PP_DIRECTIVE = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b")


def _walk(cursor: cindex.Cursor) -> Iterable[cindex.Cursor]:
    yield cursor
    for c in cursor.get_children():
        yield from _walk(c)


def _read_lines(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()
    except OSError:
        return []


def _count_pp_branches(lines: list[str], start: int, end: int) -> dict:
    """Count preprocessor directives in [start, end] (1-indexed line numbers)."""
    counts = {"if": 0, "ifdef": 0, "ifndef": 0, "elif": 0, "else": 0, "endif": 0}
    for ln in range(start - 1, min(end, len(lines))):
        m = _PP_DIRECTIVE.match(lines[ln])
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    branches = counts["if"] + counts["ifdef"] + counts["ifndef"] + counts["elif"]
    return {"directive_counts": counts, "branch_count": branches}


def _collect_macros_by_line(
    tu: cindex.TranslationUnit, target_abs: str
) -> list[tuple[int, str]]:
    """Single pass: collect (line, macro_name) for every macro instantiation in target file.

    Sorted by line so we can binary-search a [start, end] window per function.
    """
    out: list[tuple[int, str]] = []
    for node in _walk(tu.cursor):
        if node.kind != cindex.CursorKind.MACRO_INSTANTIATION:
            continue
        loc = node.location
        if loc.file is None:
            continue
        if os.path.realpath(str(loc.file.name)) != target_abs:
            continue
        out.append((loc.line, node.spelling))
    out.sort(key=lambda t: t[0])
    return out


def _macros_in_window(
    macros_by_line: list[tuple[int, str]], start: int, end: int
) -> list[str]:
    """Binary-search the sorted list for macros whose line is in [start, end]."""
    import bisect
    lines = [m[0] for m in macros_by_line]
    lo = bisect.bisect_left(lines, start)
    hi = bisect.bisect_right(lines, end)
    return sorted({macros_by_line[i][1] for i in range(lo, hi)})


_FUNCTION_KINDS = {
    cindex.CursorKind.FUNCTION_DECL,
    cindex.CursorKind.CXX_METHOD,
    cindex.CursorKind.CONSTRUCTOR,
    cindex.CursorKind.DESTRUCTOR,
    cindex.CursorKind.FUNCTION_TEMPLATE,
}


def macro_jungle(tu: cindex.TranslationUnit, target_file: str) -> dict:
    """Per-function preprocessor complexity report."""
    target_abs = os.path.realpath(target_file)
    lines = _read_lines(target_abs)
    if not lines:
        return {"file": target_abs, "error": "could not read source", "functions": []}

    functions: list[dict] = []
    seen: set[tuple] = set()

    # Single-pass macro indexing — O(N_AST) instead of O(N_funcs * N_AST).
    macros_by_line = _collect_macros_by_line(tu, target_abs)

    for node in _walk(tu.cursor):
        if node.kind not in _FUNCTION_KINDS:
            continue
        if not node.is_definition():
            continue
        loc = node.location
        if loc.file is None or os.path.realpath(str(loc.file.name)) != target_abs:
            continue

        ext = node.extent
        start, end = ext.start.line, ext.end.line
        key = (node.spelling, start, end)
        if key in seen:
            continue
        seen.add(key)

        pp = _count_pp_branches(lines, start, end)
        macros = _macros_in_window(macros_by_line, start, end)
        # Complexity score: branches * 2 + unique macros
        score = pp["branch_count"] * 2 + len(macros)

        functions.append(
            {
                "name": node.spelling,
                "qualified_name": node.displayname or node.spelling,
                "start_line": start,
                "end_line": end,
                "line_count": end - start + 1,
                "preprocessor": pp,
                "macros_used": macros,
                "complexity_score": score,
            }
        )

    functions.sort(key=lambda x: -x["complexity_score"])

    # File-level summary
    total_branches = sum(f["preprocessor"]["branch_count"] for f in functions)
    total_macros = len({m for f in functions for m in f["macros_used"]})

    return {
        "file": target_abs,
        "summary": {
            "total_functions": len(functions),
            "total_pp_branches": total_branches,
            "unique_macros_in_function_bodies": total_macros,
            "top_5_complex": [f["name"] for f in functions[:5]],
        },
        "functions": functions,
    }
