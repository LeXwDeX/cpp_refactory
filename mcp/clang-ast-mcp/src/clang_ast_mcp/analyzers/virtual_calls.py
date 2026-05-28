"""Analyzer: virtual call sites within a function or file.

For each CallExpr in scope, determine whether the callee is a virtual method,
and (if so) collect candidate overrides from the project's class hierarchy.
"""
from __future__ import annotations

import os
from typing import Iterable, Optional

from clang import cindex


_FUNC_KINDS = (
    cindex.CursorKind.FUNCTION_DECL,
    cindex.CursorKind.CXX_METHOD,
    cindex.CursorKind.CONSTRUCTOR,
    cindex.CursorKind.DESTRUCTOR,
    cindex.CursorKind.FUNCTION_TEMPLATE,
)


def _walk(cursor: cindex.Cursor) -> Iterable[cindex.Cursor]:
    yield cursor
    for c in cursor.get_children():
        yield from _walk(c)


def _virtual_methods_of(class_cursor: cindex.Cursor) -> list[cindex.Cursor]:
    out = []
    for c in class_cursor.get_children():
        if c.kind == cindex.CursorKind.CXX_METHOD:
            try:
                if c.is_virtual_method():
                    out.append(c)
            except Exception:
                pass
    return out


def _all_bases(class_cursor: cindex.Cursor) -> list[cindex.Cursor]:
    """Return transitive base class cursors (CLASS_DECL/STRUCT_DECL)."""
    out: list[cindex.Cursor] = []
    seen: set[str] = set()

    def walk(cls: cindex.Cursor) -> None:
        for c in cls.get_children():
            if c.kind != cindex.CursorKind.CXX_BASE_SPECIFIER:
                continue
            base_def = c.referenced
            if base_def is None:
                # fallback via type
                t = c.type
                base_def = t.get_declaration() if t is not None else None
            if base_def is None:
                continue
            usr = base_def.get_usr()
            if usr in seen:
                continue
            seen.add(usr)
            out.append(base_def)
            walk(base_def)

    walk(class_cursor)
    return out


def _collect_overrides(tu: cindex.TranslationUnit) -> dict:
    """Return two maps:
      by_usr:  USR-of-base-virtual -> list of override info
      by_name: (base_class_spelling, method_displayname) -> list of override info

    Built without `get_overridden_cursors()` (not exposed in some libclang
    Python bindings). Instead: walk every class, then for each virtual method
    in that class, find inherited virtual methods with matching displayname.
    """
    by_usr: dict[str, list[dict]] = {}
    by_name: dict[tuple[str, str], list[dict]] = {}

    class_kinds = (
        cindex.CursorKind.CLASS_DECL,
        cindex.CursorKind.STRUCT_DECL,
        cindex.CursorKind.CLASS_TEMPLATE,
    )
    for cls in _walk(tu.cursor):
        if cls.kind not in class_kinds:
            continue
        if not cls.is_definition():
            continue
        bases = _all_bases(cls)
        if not bases:
            continue
        derived_methods = _virtual_methods_of(cls)
        if not derived_methods:
            continue

        # Collect all candidate base virtual methods
        base_methods: list[cindex.Cursor] = []
        for b in bases:
            base_methods.extend(_virtual_methods_of(b))

        for dm in derived_methods:
            loc = dm.location
            info = {
                "qualified_name": f"{cls.spelling}::{dm.displayname}",
                "class": cls.spelling,
                "file": str(loc.file.name) if loc.file else None,
                "line": loc.line,
            }
            for bm in base_methods:
                if bm.displayname != dm.displayname:
                    continue
                usr = bm.get_usr()
                if usr:
                    by_usr.setdefault(usr, []).append(info)
                base_class = (
                    bm.semantic_parent.spelling if bm.semantic_parent else None
                )
                if base_class:
                    by_name.setdefault(
                        (base_class, bm.displayname), []
                    ).append(info)

    return {"by_usr": by_usr, "by_name": by_name}


def virtual_calls(
    tu: cindex.TranslationUnit,
    target_file: str,
    function_name: Optional[str] = None,
) -> list[dict]:
    """Find virtual call sites in target_file (optionally inside a specific function).

    Uses an explicit top-down traversal that maintains a stack of enclosing
    function definitions, so each CallExpr knows its lexical caller.
    """
    target_abs = os.path.realpath(target_file)
    overrides = _collect_overrides(tu)
    by_usr = overrides["by_usr"]
    by_name = overrides["by_name"]
    out: list[dict] = []

    def visit(node: cindex.Cursor, fn_stack: list[cindex.Cursor]) -> None:
        pushed = False
        if node.kind in _FUNC_KINDS and node.is_definition():
            fn_stack.append(node)
            pushed = True

        if node.kind == cindex.CursorKind.CALL_EXPR:
            loc = node.location
            if loc.file is not None and os.path.realpath(str(loc.file.name)) == target_abs:
                callee = node.referenced
                if (
                    callee is not None
                    and callee.kind == cindex.CursorKind.CXX_METHOD
                ):
                    try:
                        is_virt = callee.is_virtual_method()
                    except Exception:
                        is_virt = False
                    if is_virt:
                        enc = fn_stack[-1] if fn_stack else None
                        enc_name = enc.spelling if enc is not None else None
                        if function_name is None or enc_name == function_name:
                            usr = callee.get_usr()
                            candidates = list(by_usr.get(usr, []))
                            if not candidates:
                                callee_class = (
                                    callee.semantic_parent.spelling
                                    if callee.semantic_parent
                                    else None
                                )
                                candidates = list(
                                    by_name.get((callee_class, callee.displayname), [])
                                )
                            try:
                                is_pure = callee.is_pure_virtual_method()
                            except Exception:
                                is_pure = False
                            out.append(
                                {
                                    "caller": enc_name,
                                    "callee": callee.displayname,
                                    "callee_class": callee.semantic_parent.spelling
                                    if callee.semantic_parent
                                    else None,
                                    "line": loc.line,
                                    "column": loc.column,
                                    "is_pure": is_pure,
                                    "candidate_overrides": candidates,
                                }
                            )

        for child in node.get_children():
            visit(child, fn_stack)

        if pushed:
            fn_stack.pop()

    visit(tu.cursor, [])
    out.sort(key=lambda x: (x["line"], x["column"]))
    return out
