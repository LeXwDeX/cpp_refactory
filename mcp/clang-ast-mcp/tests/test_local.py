"""Local smoke tests — run analyzers directly without MCP layer.

Covers:
  - sample.cpp baseline (functions, globals, virtual calls, macro jungle)
  - complex.cpp advanced (templates, multi-inheritance, namespaces)
  - error paths (missing file, missing compile entry, bad args)
  - cache behavior (hit on repeated parse)

Run:
    .venv/bin/python tests/test_local.py
"""
from __future__ import annotations

import importlib
import json
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

# Drop any pre-imported analyzer module versions (avoid stale .pyc shadows)
for _name in list(sys.modules):
    if _name.startswith("clang_ast_mcp"):
        del sys.modules[_name]
importlib.invalidate_caches()

from clang_ast_mcp.ast_engine import get_engine
from clang_ast_mcp.analyzers.list_functions import list_functions
from clang_ast_mcp.analyzers.globals_finder import globals_in_file
from clang_ast_mcp.analyzers.virtual_calls import virtual_calls
from clang_ast_mcp.analyzers.macro_jungle import macro_jungle


SAMPLE = HERE / "fixtures" / "sample.cpp"
COMPLEX = HERE / "fixtures" / "complex.cpp"
DB = HERE / "fixtures" / "compile_commands.json"


def _color(s, c):
    return f"\033[{c}m{s}\033[0m"


def ok(msg):
    print(_color("  ✓ ", 32) + msg)


def fail(msg):
    print(_color("  ✗ ", 31) + msg)


def section(title):
    print(_color(f"\n=== {title} ===", "1;36"))


passed = 0
failed = 0


def assert_true(cond, msg):
    global passed, failed
    if cond:
        passed += 1
        ok(msg)
    else:
        failed += 1
        fail(msg)


def assert_raises(exc_type, fn, msg):
    global passed, failed
    try:
        fn()
    except exc_type as e:
        passed += 1
        ok(f"{msg} (raised {type(e).__name__}: {str(e)[:60]})")
        return
    except Exception as e:  # noqa: BLE001
        failed += 1
        fail(f"{msg} (wrong type: {type(e).__name__}: {e})")
        return
    failed += 1
    fail(f"{msg} (no exception)")


# ============================================================================
# Phase 1: sample.cpp baseline (the original 16 assertions)
# ============================================================================
def test_sample(eng):
    section("sample.cpp — Loading TU")
    tu = eng.get_tu(str(SAMPLE), str(DB), full_bodies=True)
    print(f"  TU loaded: {tu.spelling}")

    section("sample.cpp — list_functions")
    funcs = list_functions(tu, str(SAMPLE))
    print(f"  Found {len(funcs)} functions")
    assert_true(len(funcs) >= 6, f"function count >= 6 (got {len(funcs)})")
    names = {f["name"] for f in funcs}
    for required in ("process", "LongFunction", "Compute"):
        assert_true(required in names, f"must include function '{required}'")
    long_funcs = list_functions(tu, str(SAMPLE), min_lines=10)
    assert_true(
        all(f["line_count"] >= 10 for f in long_funcs),
        f"min_lines=10 filter respected ({len(long_funcs)} funcs)",
    )

    section("sample.cpp — globals_finder")
    gs = globals_in_file(tu, str(SAMPLE))
    print(f"  Found {len(gs)} globals")
    assert_true(len(gs) >= 4, f"globals count >= 4 (got {len(gs)})")
    kinds = {g["kind"] for g in gs}
    for k in ("extern", "file_static", "anon_ns", "class_static"):
        assert_true(k in kinds, f"must include kind '{k}' (got {sorted(kinds)})")

    section("sample.cpp — virtual_calls")
    vcs = virtual_calls(tu, str(SAMPLE))
    print(f"  Found {len(vcs)} virtual call sites")
    assert_true(len(vcs) >= 1, f"virtual calls >= 1 (got {len(vcs)})")
    if vcs:
        v0 = vcs[0]
        assert_true(v0["caller"] == "process", f"caller is 'process' (got {v0['caller']})")
        assert_true(
            len(v0["candidate_overrides"]) >= 1,
            "candidate_overrides found (Derived::Compute)",
        )

    section("sample.cpp — macro_jungle")
    mj = macro_jungle(tu, str(SAMPLE))
    proc = next((f for f in mj["functions"] if f["name"] == "process"), None)
    assert_true(proc is not None, "macro_jungle includes 'process'")
    if proc:
        assert_true(
            proc["preprocessor"]["branch_count"] >= 2,
            f"process has >=2 pp branches (got {proc['preprocessor']['branch_count']})",
        )
        assert_true("LOG_INFO" in proc["macros_used"], "process invokes LOG_INFO")


# ============================================================================
# Phase 2: complex.cpp advanced patterns
# ============================================================================
def test_complex(eng):
    section("complex.cpp — Loading TU")
    tu = eng.get_tu(str(COMPLEX), str(DB), full_bodies=True)
    print(f"  TU loaded: {tu.spelling}")

    section("complex.cpp — list_functions (templates, multi-inheritance)")
    funcs = list_functions(tu, str(COMPLEX))
    print(f"  Found {len(funcs)} functions")
    names = {f["name"] for f in funcs}
    print(f"  Names sample: {sorted(names)[:15]}")
    # Templates count as function definitions
    assert_true("add_one" in names, "function template 'add_one' detected")
    assert_true("mul" in names, "function template 'mul' detected")
    assert_true("process_complex" in names, "process_complex detected")
    assert_true("square" in names, "constexpr 'square' detected")
    assert_true("cube" in names, "inline 'cube' detected")
    # Operator overload should appear (clang names them operator+, operator==)
    op_names = {n for n in names if n.startswith("operator")}
    assert_true(len(op_names) >= 2, f"operators detected (got {sorted(op_names)})")

    section("complex.cpp — globals across linkages")
    gs = globals_in_file(tu, str(COMPLEX))
    print(f"  Found {len(gs)} globals")
    for g in gs[:15]:
        print(
            f"    L{g['line']:>3} {g['kind']:<14} {g['type']:<25} {g['name']}"
        )
    kinds = {g["kind"] for g in gs}
    for k in ("extern", "file_static", "anon_ns", "class_static"):
        assert_true(k in kinds, f"must include kind '{k}' (got {sorted(kinds)})")
    # Named-namespace globals + tls should map to extern linkage
    g_names = {g["name"] for g in gs}
    assert_true("g_in_named_ns" in g_names, "named-namespace global captured")
    assert_true("g_deep" in g_names, "nested namespace global captured")

    section("complex.cpp — virtual_calls across hierarchy")
    vcs = virtual_calls(tu, str(COMPLEX))
    print(f"  Found {len(vcs)} virtual call sites")
    for v in vcs:
        print(
            f"    L{v['line']:>3} caller={v['caller']!s:<18} "
            f"callee={v['callee_class']}::{v['callee']} "
            f"overrides={len(v['candidate_overrides'])}"
        )
    assert_true(len(vcs) >= 2, f"virtual calls >= 2 (got {len(vcs)})")
    # Every call should have a non-None caller (process_complex is the only one
    # that issues virtual calls in this fixture)
    callers = {v["caller"] for v in vcs}
    assert_true(
        callers == {"process_complex"},
        f"all callers == process_complex (got {callers})",
    )
    # At least one of the Compute calls should resolve overrides through
    # Grandparent → Parent → Child chain
    compute_calls = [v for v in vcs if "Compute" in v["callee"]]
    if compute_calls:
        ov_classes = {
            o["class"] for v in compute_calls for o in v["candidate_overrides"]
        }
        assert_true(
            "Parent" in ov_classes or "Child" in ov_classes,
            f"override chain detected (Parent or Child) — got {ov_classes}",
        )

    section("complex.cpp — macro_jungle nested #ifdef")
    mj = macro_jungle(tu, str(COMPLEX))
    pc = next(
        (f for f in mj["functions"] if f["name"] == "process_complex"), None
    )
    assert_true(pc is not None, "macro_jungle includes process_complex")
    if pc:
        assert_true(
            pc["preprocessor"]["branch_count"] >= 4,
            f"process_complex has >=4 pp branches (got {pc['preprocessor']['branch_count']})",
        )


# ============================================================================
# Phase 3: error paths (must raise, not crash)
# ============================================================================
def test_errors(eng):
    section("error paths")
    assert_raises(
        FileNotFoundError,
        lambda: eng.get_tu("/nonexistent/path.cpp", str(DB)),
        "missing source raises FileNotFoundError",
    )
    assert_raises(
        FileNotFoundError,
        lambda: eng.get_tu(str(SAMPLE), "/nonexistent/compile_commands.json"),
        "missing compile_db raises FileNotFoundError",
    )
    # Source not in DB
    assert_raises(
        KeyError,
        lambda: eng.get_tu(__file__, str(DB)),
        "source absent from compile_db raises KeyError",
    )


# ============================================================================
# Phase 4: cache hit behavior (re-parse should be fast)
# ============================================================================
def test_cache(eng):
    section("cache hit behavior")
    t0 = time.perf_counter()
    tu1 = eng.get_tu(str(SAMPLE), str(DB), full_bodies=True)
    t_cold = time.perf_counter() - t0

    t0 = time.perf_counter()
    tu2 = eng.get_tu(str(SAMPLE), str(DB), full_bodies=True)
    t_warm = time.perf_counter() - t0

    print(f"  cold parse: {t_cold * 1000:.1f}ms")
    print(f"  warm parse: {t_warm * 1000:.3f}ms")
    print(f"  cache stats: {eng.cache_stats()}")

    assert_true(tu1 is tu2, "warm parse returns same TU object (LRU hit)")
    assert_true(
        t_warm < t_cold / 5 if t_cold > 0.001 else True,
        f"warm parse much faster (cold={t_cold*1000:.1f}ms, warm={t_warm*1000:.3f}ms)",
    )


# ============================================================================
# Phase 5: server-layer smoke (structured-error wrapping)
# ============================================================================
def test_server_layer():
    section("server-layer error wrapping")
    # Re-import to avoid namespace pollution
    from clang_ast_mcp import server  # noqa: WPS433

    res = server.tool_list_functions("/nonexistent.cpp")
    assert_true(
        isinstance(res, dict) and res.get("ok") is False,
        f"missing file → structured error (got ok={res.get('ok')})",
    )
    assert_true(
        res.get("error", {}).get("kind") == "FileNotFound",
        f"error kind=FileNotFound (got {res.get('error')})",
    )

    res2 = server.tool_list_functions(str(SAMPLE), min_lines=-5, compile_db=str(DB))
    assert_true(
        res2.get("ok") is False and res2["error"]["kind"] == "BadArgument",
        f"negative min_lines → BadArgument (got {res2.get('error')})",
    )

    # Happy path through server layer
    res3 = server.tool_list_functions(str(SAMPLE), compile_db=str(DB))
    assert_true(
        res3.get("ok") is True and res3.get("count", 0) >= 6,
        f"server happy-path returns functions (got count={res3.get('count')})",
    )


def main():
    eng = get_engine()
    test_sample(eng)
    test_complex(eng)
    test_errors(eng)
    test_cache(eng)
    test_server_layer()

    section("Result")
    total = passed + failed
    if failed == 0:
        print(_color(f"  ALL {total} ASSERTIONS PASSED", "1;32"))
        sys.exit(0)
    else:
        print(_color(f"  {failed} of {total} FAILED", "1;31"))
        sys.exit(1)


if __name__ == "__main__":
    main()
