"""Stress test: generate a 5000-line synthetic C++ file and benchmark.

Validates:
  - cold parse completes in reasonable time (< 30s on a generic dev box)
  - warm parse hits the LRU cache (< 1ms)
  - all analyzers return sane counts on the generated file
  - mtime guard: touching the file forces a re-parse (cache miss)

Run:
    .venv/bin/python tests/stress_test.py
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))

for _name in list(sys.modules):
    if _name.startswith("clang_ast_mcp"):
        del sys.modules[_name]
importlib.invalidate_caches()

from clang_ast_mcp.ast_engine import get_engine
from clang_ast_mcp.analyzers.list_functions import list_functions
from clang_ast_mcp.analyzers.globals_finder import globals_in_file
from clang_ast_mcp.analyzers.virtual_calls import virtual_calls
from clang_ast_mcp.analyzers.macro_jungle import macro_jungle


N_FUNCS = 500           # → ~5000 lines
COLD_PARSE_BUDGET = 30  # seconds (generous: libclang on ~5k lines should take 1-2s)
WARM_PARSE_BUDGET = 0.01  # seconds (LRU lookup, basically dict access)


def generate_source(n_funcs: int) -> str:
    """Generate a single C++ source file with n_funcs functions, plus a few
    classes with virtual methods and some #ifdef noise."""
    lines = [
        "// Auto-generated stress fixture",
        "#include <vector>",
        "#include <string>",
        "",
        "extern int g_extern_counter;",
        "static int g_file_static = 0;",
        "namespace { int g_anon = 1; }",
        "",
        "class Base {",
        "public:",
        "    virtual ~Base() {}",
        "    virtual int compute(int x) const { return x; }",
        "};",
        "",
        "class Derived : public Base {",
        "public:",
        "    int compute(int x) const override { return x * 2; }",
        "};",
        "",
        "static int s_local_state = 0;",
        "",
        "#define LOG(msg) ((void)(msg))",
        "",
    ]
    for i in range(n_funcs):
        # Each function ~9 lines, with a virtual call sprinkled in every 50th.
        if i % 50 == 0:
            lines.extend([
                f"int func_{i}(Base* b, int x) {{",
                f"    LOG(\"func_{i}\");",
                f"    int r = b->compute(x);",  # virtual call OUTSIDE ifdef
                f"#ifdef FEATURE_EXTRA",
                f"    r += {i};",
                f"#else",
                f"    r -= {i};",
                f"#endif",
                f"    return r + s_local_state;",
                f"}}",
                "",
            ])
        else:
            lines.extend([
                f"int func_{i}(int x) {{",
                f"    int r = x;",
                f"    for (int i = 0; i < {(i % 5) + 1}; ++i) {{",
                f"        r += i * {i % 11};",
                f"    }}",
                f"    if (r > {i * 13}) {{ r = {i * 13}; }}",
                f"    return r;",
                f"}}",
                "",
            ])
    return "\n".join(lines) + "\n"


def main():
    tmp = Path(tempfile.mkdtemp(prefix="clang_ast_stress_"))
    try:
        src_path = tmp / "stress.cpp"
        src_path.write_text(generate_source(N_FUNCS))
        line_count = src_path.read_text().count("\n")
        print(f"Generated {src_path} — {line_count} lines, {N_FUNCS} funcs")

        # Build a one-entry compile_commands.json
        db_path = tmp / "compile_commands.json"
        db_path.write_text(
            json.dumps(
                [{
                    "directory": str(tmp),
                    "command": f"clang++ -std=c++17 -c {src_path.name}",
                    "file": src_path.name,
                }]
            )
        )

        eng = get_engine()

        # ---- Cold parse ----
        t0 = time.perf_counter()
        tu = eng.get_tu(str(src_path), str(db_path), full_bodies=True)
        t_cold = time.perf_counter() - t0
        print(f"\n[cold parse]   {t_cold * 1000:8.1f} ms  (budget {COLD_PARSE_BUDGET * 1000:.0f} ms)")
        assert t_cold < COLD_PARSE_BUDGET, f"Cold parse too slow: {t_cold:.2f}s"

        # ---- Warm parse (LRU hit) ----
        t0 = time.perf_counter()
        tu2 = eng.get_tu(str(src_path), str(db_path), full_bodies=True)
        t_warm = time.perf_counter() - t0
        print(f"[warm parse]   {t_warm * 1000:8.3f} ms  (budget {WARM_PARSE_BUDGET * 1000:.0f} ms)")
        assert tu is tu2, "warm parse should return the cached TU object"
        assert t_warm < WARM_PARSE_BUDGET, f"Warm parse too slow: {t_warm:.4f}s"

        # ---- Analyzer sanity ----
        t0 = time.perf_counter()
        funcs = list_functions(tu, str(src_path))
        t_lf = time.perf_counter() - t0
        print(f"[list_funcs]   {t_lf * 1000:8.1f} ms  → {len(funcs)} functions")
        # +3 classes' methods (Base ctor not present; dtor + compute + Derived::compute)
        assert len(funcs) >= N_FUNCS, f"expected >= {N_FUNCS} funcs, got {len(funcs)}"

        t0 = time.perf_counter()
        gs = globals_in_file(tu, str(src_path))
        t_g = time.perf_counter() - t0
        print(f"[globals]      {t_g * 1000:8.1f} ms  → {len(gs)} globals")
        kinds = {g["kind"] for g in gs}
        assert {"extern", "file_static", "anon_ns"} <= kinds, (
            f"missing global kinds (got {kinds})"
        )

        t0 = time.perf_counter()
        vcs = virtual_calls(tu, str(src_path))
        t_v = time.perf_counter() - t0
        print(f"[virt_calls]   {t_v * 1000:8.1f} ms  → {len(vcs)} virtual call sites")
        # roughly N_FUNCS / 50 virtual call sites
        assert len(vcs) >= N_FUNCS // 50 - 1, f"expected ~{N_FUNCS // 50} vcs, got {len(vcs)}"

        t0 = time.perf_counter()
        mj = macro_jungle(tu, str(src_path))
        t_m = time.perf_counter() - t0
        n_with_branches = sum(
            1 for f in mj["functions"] if f["preprocessor"]["branch_count"] > 0
        )
        print(f"[macro_jungle] {t_m * 1000:8.1f} ms  → {n_with_branches} funcs with #ifdef")
        assert n_with_branches >= N_FUNCS // 50 - 1

        # ---- mtime invalidation ----
        os.utime(src_path, None)  # touch
        t0 = time.perf_counter()
        tu3 = eng.get_tu(str(src_path), str(db_path), full_bodies=True)
        t_invalidated = time.perf_counter() - t0
        print(f"[after touch]  {t_invalidated * 1000:8.1f} ms  (re-parse expected)")
        assert tu3 is not tu, "touch should force re-parse (cache miss)"
        assert t_invalidated > t_warm * 5, (
            f"expected cold-ish re-parse, got {t_invalidated * 1000:.2f}ms vs "
            f"warm {t_warm * 1000:.3f}ms"
        )

        print(f"\n\033[1;32m  STRESS PASSED — {N_FUNCS} funcs, {line_count} lines\033[0m")
        print(f"  cache: {eng.cache_stats()}")
    finally:
        # Clean up temp dir
        for p in tmp.iterdir():
            p.unlink()
        tmp.rmdir()


if __name__ == "__main__":
    main()
