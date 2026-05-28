"""Analyzer: globals — find non-local variable declarations.

Distinguishes:
  - extern (linked across TUs)
  - file-scope static
  - anonymous-namespace internal linkage
  - class static members (definition site)
  - constexpr / const (typically benign)
  - dynamic-init globals (the dangerous ones)
"""
from __future__ import annotations

import os
from typing import Iterable

from clang import cindex


def _walk(cursor: cindex.Cursor) -> Iterable[cindex.Cursor]:
    yield cursor
    for c in cursor.get_children():
        yield from _walk(c)


def _is_in_anonymous_namespace(cursor: cindex.Cursor) -> bool:
    parent = cursor.semantic_parent
    while parent is not None and parent.kind != cindex.CursorKind.TRANSLATION_UNIT:
        if parent.kind == cindex.CursorKind.NAMESPACE and not parent.spelling:
            return True
        parent = parent.semantic_parent
    return False


def _classify_linkage(cursor: cindex.Cursor) -> str:
    try:
        linkage = cursor.linkage
    except Exception:
        return "unknown"
    if linkage == cindex.LinkageKind.EXTERNAL:
        return "extern"
    if linkage == cindex.LinkageKind.INTERNAL:
        return "internal"
    if linkage == cindex.LinkageKind.NO_LINKAGE:
        return "no_linkage"
    return str(linkage)


def _has_dynamic_init(cursor: cindex.Cursor) -> bool:
    """Heuristic: if the var has an initializer that's a CALL_EXPR or
    references non-constexpr objects, treat as dynamic-init.
    """
    for child in cursor.get_children():
        if child.kind in (
            cindex.CursorKind.CALL_EXPR,
            cindex.CursorKind.CXX_NEW_EXPR,
            cindex.CursorKind.CXX_DELETE_EXPR,
        ):
            return True
        # Recurse one level — nested init expressions
        for grand in child.get_children():
            if grand.kind == cindex.CursorKind.CALL_EXPR:
                return True
    return False


def globals_in_file(tu: cindex.TranslationUnit, target_file: str) -> list[dict]:
    """Find all non-local variable declarations originating in target_file."""
    target_abs = os.path.realpath(target_file)
    out: list[dict] = []
    seen: set[tuple] = set()

    for node in _walk(tu.cursor):
        if node.kind != cindex.CursorKind.VAR_DECL:
            continue
        # Only definitions/declarations at file/namespace scope
        sem_parent = node.semantic_parent
        if sem_parent is None:
            continue
        if sem_parent.kind not in (
            cindex.CursorKind.TRANSLATION_UNIT,
            cindex.CursorKind.NAMESPACE,
        ):
            # class static members: include if parent is CLASS_DECL/STRUCT_DECL
            if sem_parent.kind not in (
                cindex.CursorKind.CLASS_DECL,
                cindex.CursorKind.STRUCT_DECL,
                cindex.CursorKind.CLASS_TEMPLATE,
            ):
                continue

        loc = node.location
        if loc.file is None:
            continue
        if os.path.realpath(str(loc.file.name)) != target_abs:
            continue

        key = (node.spelling, loc.line, loc.column)
        if key in seen:
            continue
        seen.add(key)

        linkage = _classify_linkage(node)
        anon_ns = _is_in_anonymous_namespace(node)

        # Classification order: class_static > anon_ns > file_static > extern.
        # Class statics typically have EXTERNAL linkage too, so we must check
        # the semantic parent BEFORE deciding by linkage.
        if sem_parent.kind in (
            cindex.CursorKind.CLASS_DECL,
            cindex.CursorKind.STRUCT_DECL,
            cindex.CursorKind.CLASS_TEMPLATE,
        ):
            kind = "class_static"
        elif anon_ns:
            kind = "anon_ns"
        elif linkage == "internal":
            kind = "file_static"
        elif linkage == "extern":
            kind = "extern"
        else:
            kind = "unknown"

        # Detect the out-of-class static member definition pattern
        # (e.g. `int Base::s_instance_count = 0;` written at TU scope).
        # Such a VarDecl is at TU scope but its qualified name contains "::".
        if (
            kind == "extern"
            and "::" in (node.displayname or node.spelling or "")
            and node.is_definition()
        ):
            kind = "class_static"

        is_const = False
        try:
            is_const = node.type.is_const_qualified()
        except Exception:
            pass

        out.append(
            {
                "name": node.spelling,
                "qualified_name": node.displayname or node.spelling,
                "kind": kind,
                "type": node.type.spelling if node.type else "?",
                "line": loc.line,
                "column": loc.column,
                "is_const": is_const,
                "has_dynamic_init": _has_dynamic_init(node),
                "is_definition": node.is_definition(),
            }
        )

    out.sort(key=lambda x: x["line"])
    return out
